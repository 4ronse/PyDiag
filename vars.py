import os
import logging
import warnings

from dotenv import load_dotenv
from NetworkMonitor import NetworkMonitor

# Load .env
load_dotenv()

# Parse values
def get_network_unit(unit_name: str) -> NetworkMonitor.Unit:
    """Get network speed unit by name

    Args:
        unit_name (str): Speed unit name

    Returns:
        NetworkMonitor.Unit: Unit object
    """
    return NetworkMonitor.Unit.get_by_name(unit_name)

def get_logging_level(level_name: str) -> int:
    """ Get logging level for given name

    Args:
        level_name (str): Level name in .env file

    Returns:
        int: Logging level
    """
    level_name = level_name.upper()
    nameToLevel = logging._nameToLevel
    if level_name in nameToLevel:
        return nameToLevel[level_name]
    warnings.warn(f'Logging leve: "{level_name}" level not found!')
    return logging.INFO

def load_dev_device() -> dict[str, any]:
    if not int(os.environ.get('DEV_DEVICE_USE', 0)):
        return {}

    keys = [
        'DEV_DEVICE_IDENTIFIERS',
        'DEV_DEVICE_MANUFACTURER',
        'DEV_DEVICE_MODEL',
        'DEV_DEVICE_CONFIGURATION_URL',
        'DEV_DEVICE_HW_VERSION',
        'DEV_DEVICE_SW_VERSION',
        'DEV_DEVICE_MODEL_ID',
        'DEV_DEVICE_SERIAL_NUMBER',
        'DEV_DEVICE_SUGGESTED_AREA',
        'DEV_DEVICE_VIA_DEVICE',
    ]

    device_data = {}
    for k in keys:
        value = os.environ.get(k, None)
        if value:
            # Convert DEV_DEVICE_IDENTIFIERS to a list (comma-separated)
            if k == 'DEV_DEVICE_IDENTIFIERS':
                device_data['identifiers'] = [item.strip() for item in value.split(',')]
            else:
                device_data[k[11:].lower()] = value

    return device_data

def mqtt_topic_format(value: str) -> str:
    if value.startswith('/'):
        value = value[1:]
    return value

# Config
MQTT_PUBLISH_INTERVAL = int(os.environ.get('MQTT_PUBLISH_INTERVAL', 5))
MQTT_REPUBLISH_INTERVAL = int(os.environ.get('MQTT_REPUBLISH_INTERVAL', 300))
MQTT_USER = os.environ.get('MQTT_USER')
MQTT_PASS = os.environ.get('MQTT_PASS')
MQTT_PORT = int(os.environ.get('MQTT_PORT'))
MQTT_BROKER = os.environ.get('MQTT_BROKER')

MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID")
MQTT_PYDIAG_PREFIX = mqtt_topic_format(os.environ.get('MQTT_PYDIAG_PREFIX', 'pydiag/'))
MQTT_HA_DISCOVERY_PREFIX = mqtt_topic_format(os.environ.get('MQTT_HA_DISCOVERY_PREFIX', 'homeassistant/'))

DEVICE_NAME = os.environ.get('DEVICE_NAME')
NETWORK_SPEED_UNIT = get_network_unit(os.environ.get('NETWORK_SPEED_UNIT', 'kB/s'))
LOGGING_LEVEL = get_logging_level(os.environ.get('LOGGING_LEVEL', 'info'))

DEV_DEVICE_CONFIG = load_dev_device()

# Tests
if __name__ == '__main__':
    # Test MQTT configuration
    assert MQTT_PUBLISH_INTERVAL is not None, "MQTT_PUBLISH_INTERVAL is not set"
    assert MQTT_USER is not None, "MQTT_USER is not set"
    assert MQTT_PASS is not None, "MQTT_PASS is not set"
    assert MQTT_PORT is not None, "MQTT_PORT is not set"
    assert MQTT_BROKER is not None, "MQTT_BROKER is not set"
    assert MQTT_PYDIAG_PREFIX is not None, "MQTT_PYDIAG_PREFIX is not set"
    assert MQTT_HA_DISCOVERY_PREFIX is not None, "MQTT_HA_DISCOVERY_PREFIX is not set"
    print("MQTT configuration tests passed.")

    # Test network speed unit parsing
    try:
        unit = get_network_unit(NETWORK_SPEED_UNIT)
        print(f"Network speed unit '{NETWORK_SPEED_UNIT}' is valid.")
    except Exception as e:
        print(f"Network speed unit test failed: {e}")

    # Test logging level parsing
    try:
        assert isinstance(LOGGING_LEVEL, int), "Logging level should be an integer"
        print(f"Logging level '{LOGGING_LEVEL}' is valid.")
    except Exception as e:
        print(f"Logging level test failed: {e}")

    try:
        dev_device = load_dev_device()
        if dev_device:
            print("Dev device loaded")
            print(dev_device)
        else:
            print("Dev device is disabled")
    except Exception as e:
        print(f"Failed to load dev device {e}")
