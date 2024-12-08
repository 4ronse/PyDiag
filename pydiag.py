import asyncio
import logging
import sys
from typing import List, Callable, Any, Dict, Literal

# Local imports
from HAEntities import *
from DiagUtil import *
from vars import *
from HAPublisher import HAPublisher
from NetworkMonitor import NetworkMonitor

# Enhanced logging with colorlog
from colorlog import ColoredFormatter

# Configure logger
_LOGGER = logging.getLogger(__name__)

async def setup_logging() -> None:
    """
    Configure a colored logging formatter for improved log readability.

    Sets up logging with color-coded levels and a detailed format.
    """
    colored_formatter = ColoredFormatter(
        fmt='%(log_color)s[%(asctime)s] [%(levelname)s] [%(module)s#%(funcName)s()] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(colored_formatter)

    logging.basicConfig(
        level=LOGGING_LEVEL,
        handlers=[console_handler]
    )

def create_device_info() -> DeviceInfoBuilder:
    """
    Create a device information builder for Home Assistant.

    Detects if running in development mode and creates device info accordingly.

    Returns:
        DeviceInfoBuilder: Configured device information
    """
    try:
        if not DEV_DEVICE_CONFIG:
            return DeviceInfoBuilder(
                name=get_hostname(),
                identifiers=[get_serial_number()],
                model=get_rpi_model(),
                serial_number=get_serial_number(),
                manufacturer='Raspberry Pi'
            )
        else:
            # Use environment or development configuration
            return DeviceInfoBuilder.from_env({
                **{'name': get_device_name()},
                **DEV_DEVICE_CONFIG
            })
    except Exception as e:
        _LOGGER.error(f"Failed to create device info: {e}")
        raise

def create_network_sensors(
    monitors: List[NetworkMonitor],
    device_info: DeviceInfoBuilder
) -> Dict[Sensor, Callable[[], Any]]:
    """
    Generate network-related sensors for all network interfaces.

    Args:
        monitors (List[NetworkMonitor]): List of network monitors
        device_info (DeviceInfoBuilder): Device information for sensor context

    Returns:
        Dict[Sensor, Callable[[], Any]]: Dictionary of network sensors and their value getters
    """
    # Create a sanitized device name for unique ID generation
    formatted_name = device_info.name.lower().replace(' ', '_').replace('-', '_')

    network_sensors: Dict[Sensor, Callable[[], Any]] = {}

    for nm in monitors:
        iface = nm.interface

        # Create RX (download) sensor
        rx_sensor = Sensor(
            name=f'{iface} RX',
            unique_id=f'{formatted_name}_{iface}_rx',
            device=device_info,
            unit_of_measurement=NETWORK_SPEED_UNIT.unit_name,
            icon=IconEnum.DOWNLOAD
        )

        # Create TX (upload) sensor
        tx_sensor = Sensor(
            name=f'{iface} TX',
            unique_id=f'{formatted_name}_{iface}_tx',
            device=device_info,
            unit_of_measurement=NETWORK_SPEED_UNIT.unit_name,
            icon=IconEnum.UPLOAD
        )

        # Create closures for throughput getters to capture current monitor
        def get_throughput(current_monitor, rx_tx: Literal['rx'] | Literal['tx']):
            def inner():
                return current_monitor.get_throughput(NETWORK_SPEED_UNIT)[rx_tx]
            return inner

        network_sensors[rx_sensor] = get_throughput(nm, 'rx')
        network_sensors[tx_sensor] = get_throughput(nm, 'tx')

    return network_sensors

async def main():
    """
    Main asynchronous entry point for the diagnostic monitoring script.

    Establishes MQTT connection, sets up network and system sensors,
    and continuously publishes their states.
    """
    try:
        # Setup logging
        await setup_logging()
        _LOGGER.info("Diagnostic monitoring script starting...")

        # Initialize MQTT publisher
        pub = HAPublisher()
        await pub.connect()

        # Start network monitors
        monitors: List[NetworkMonitor] = []
        for iface in get_ifaces():
            monitor = NetworkMonitor(interface=iface)
            await monitor.start_monitoring()
            monitors.append(monitor)

        # Create device information
        device_info = create_device_info()

        # Create system sensors
        system_sensors = {
            Sensor(
                name="Hostname",
                unique_id=f'{device_info.name.lower().replace(" ", "_")}_hostname',
                device=device_info,
                entity_category=EntityCategory.DIAGNOSTIC
            ): get_hostname,

            Sensor(
                name='Temperature',
                unique_id=f'{device_info.name.lower().replace(" ", "_")}_temperature',
                device=device_info,
                icon=IconEnum.THERMOMETER,
                unit_of_measurement='\u00b0C',
                device_class=SensorDeviceClass.TEMPERATURE
            ): get_temp,

            Sensor(
                name='CPU Usage',
                unique_id=f'{device_info.name.lower().replace(" ", "_")}_cpu_usage',
                device=device_info,
                icon=IconEnum.CPU_64_BIT,
                unit_of_measurement='%'
            ): get_cpu_usage,

            Sensor(
                name='Memory Usage',
                unique_id=f'{device_info.name.lower().replace(" ", "_")}_memory_usage',
                device=device_info,
                icon=IconEnum.MEMORY,
                unit_of_measurement='%'
            ): get_memory_usage,

            Sensor(
                name='Disk Usage',
                unique_id=f'{device_info.name.lower().replace(" ", "_")}_disk_usage',
                device=device_info,
                icon=IconEnum.HARDDISK,
                unit_of_measurement='%'
            ): get_disk_usage
        }

        # Register system sensors
        for sensor, getter in system_sensors.items():
            await pub.register_entity(sensor, getter)

        # Register network sensors
        for sensor, getter in create_network_sensors(monitors, device_info).items():
            await pub.register_entity(sensor, getter)

        # Continuous publishing loop
        try:
            while True:
                await pub.publish_all()
                await asyncio.sleep(MQTT_PUBLISH_INTERVAL)  # Publish every 5 seconds

        except KeyboardInterrupt:
            _LOGGER.info('Monitoring interrupted by user.')

        finally:
            # Cleanup network monitoring tasks
            for nm in monitors:
                task = nm.get_monitoring_task()
                if task:
                    task.cancel()
                    await task

    except Exception as e:
        _LOGGER.critical(f"Critical error in diagnostic monitoring: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
