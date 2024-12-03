from HAEntities import *
from HAPublisher import HAPublisher
from NetworkMonitor import NetworkMonitor
from DiagUtil import *
from vars import LOGGING_LEVEL, NETWORK_SPEED_UNIT

from typing import List, Callable, Any
from colorlog import ColoredFormatter

import asyncio
import logging

async def main():
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

    pub = HAPublisher()
    await pub.connect()

    monitors: List[NetworkMonitor] = []
    tasks = List[asyncio.Task[Any]] = []

    for iface in get_ifaces():
        monitor = NetworkMonitor(interface=iface)
        monitors.append(monitor)
        tasks.append(asyncio.create_task(monitor.start_monitoring()))

    device_info = DeviceInfoBuilder(
        name=get_hostname(),
        identifiers=[get_serial_number()],
        model=get_rpi_model(),
        serial_number=get_serial_number(),
        manufacturer='Raspberry Pi'
    )

    formatted_name = device_info.name.lower().replace(' ', '_').replace('-', '_')

    def get_network_sensors() -> Dict[Sensor, Callable[[], Any]]:
        dct: Dict[Sensor, Callable[[], Any]] = {}
        for monitor in monitors:
            iface = monitor.interface

            rx_sensor = Sensor(
                name=f'{iface} RX',
                unique_id=f'{formatted_name}_{iface}_rx',
                device=device_info,
                unit_of_measurement=NETWORK_SPEED_UNIT,
                icon=IconEnum.DOWNLOAD
            )

            tx_sensor = Sensor(
                name=f'{iface} TX',
                unique_id=f'{formatted_name}_{iface}_tx',
                device=device_info,
                unit_of_measurement=NETWORK_SPEED_UNIT,
                icon=IconEnum.UPLOAD
            )

            dct[rx_sensor] = lambda: monitor.get_throughput(NETWORK_SPEED_UNIT)['rx']
            dct[tx_sensor] = lambda: monitor.get_throughput(NETWORK_SPEED_UNIT)['tx']
        return dct

    hostname_sensor = Sensor(
        name="Hostname",
        unique_id=f'{formatted_name}_hostname',
        device=device_info,
        entity_category=EntityCategory.DIAGNOSTIC
    )

    temperature_sensor = Sensor(
        name='Temperature',
        unique_id=f'{formatted_name}_temperature',
        device=device_info,
        icon=IconEnum.THERMOMETER,
        unit_of_measurement='\u00b0C',
        device_class=SensorDeviceClass.TEMPERATURE
    )

    cpu_usage_sensor = Sensor(
        name='CPU Usage',
        unique_id=f'{formatted_name}_cpu_usage',
        device=device_info,
        icon=IconEnum.CPU_64_BIT,
        unit_of_measurement='%'
    )

    memory_usage_sensor = Sensor(
        name='Memory Usage',
        unique_id=f'{formatted_name}_memory_usage',
        device=device_info,
        icon=IconEnum.MEMORY,
        unit_of_measurement='%'
    )

    disk_usage_sensor = Sensor(
        name='Disk Usage',
        unique_id=f'{formatted_name}_disk_usage',
        device=device_info,
        icon=IconEnum.HARDDISK,
        unit_of_measurement='%'
    )

    sensorValueMap = {
        hostname_sensor: get_hostname,
        temperature_sensor: get_temp,
        cpu_usage_sensor: get_cpu_usage,
        memory_usage_sensor: get_memory_usage,
        disk_usage_sensor: get_disk_usage
    }

    for sensor, getter in sensorValueMap.items() + get_network_sensors().items():
        await pub.register_entity(sensor, getter)

    try:
        while True:
            await pub.publish_all()
            await asyncio.sleep(5)
    except KeyboardInterrupt:
        print('Stopping...')

        for task in tasks:
            task.cancel()
            await task

if __name__ == '__main__':
    asyncio.run(main())
