from HAEntities import *
from HAPublisher import HAPublisher
from NetworkMonitor import NetworkMonitor
from DiagUtil import *
from vars import LOGGING_LEVEL

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
    network_monitor = NetworkMonitor()
    monitoring_task = asyncio.create_task(network_monitor.start_monitoring())
    await pub.connect()

    device_info = DeviceInfoBuilder(
        name=get_hostname(),
        identifiers=[get_serial_number()],
        model=get_rpi_model(),
        serial_number=get_serial_number(),
        manufacturer='Raspberry Pi'
    )

    formatted_name = device_info.name.lower().replace(' ', '_').replace('-', '_')

    hostname_sensor = Sensor(
        name="Hostname",
        unique_id=f'{formatted_name}_hostname',
        device=device_info
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

    network_interface_sensor = Sensor(
        name='Ethernet Interface',
        unique_id=f'{formatted_name}_ethernet_iface',
        device=device_info,
    )

    network_tx_sensor = Sensor(
        name=f'{network_monitor.interface} TX',
        unique_id=f'{formatted_name}_ethernet_iface_tx',
        device=device_info,
        unit_of_measurement='kB/s',
        icon=IconEnum.UPLOAD
    )

    network_rx_sensor = Sensor(
        name=f'{network_monitor.interface} RX',
        unique_id=f'{formatted_name}_ethernet_iface_rx',
        device=device_info,
        unit_of_measurement='kB/s',
        icon=IconEnum.DOWNLOAD
    )

    sensorValueMap = {
        hostname_sensor: get_hostname,
        temperature_sensor: get_temp,
        cpu_usage_sensor: get_cpu_usage,
        memory_usage_sensor: get_memory_usage,
        disk_usage_sensor: get_disk_usage,
        network_interface_sensor: lambda: network_monitor.interface,
        network_tx_sensor: lambda: network_monitor.get_throughput()['tx'],
        network_rx_sensor: lambda: network_monitor.get_throughput()['rx'],
    }

    for sensor in sensorValueMap.keys():
        await pub.register_entity(sensor)

    try:
        while True:
            for sensor, func in sensorValueMap.items():
                await pub.publish_entity_state(sensor, func())
            await asyncio.sleep(5)
    except KeyboardInterrupt:
        print('Stopping...')
        monitoring_task.cancel()
        await monitoring_task



if __name__ == '__main__':
    asyncio.run(main())
