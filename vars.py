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
    if level_name in logging.getLevelNamesMapping():
        return logging.getLevelNamesMapping()[level_name]
    warnings.warn(f'Logging leve: "{level_name}" level not found!')
    return logging.INFO

# Config
MQTT_USER = os.environ.get('MQTT_USER')
MQTT_PASS = os.environ.get('MQTT_PASS')
MQTT_PORT = os.environ.get('MQTT_PORT')
MQTT_BROKER = os.environ.get('MQTT_BROKER')

NETWORK_SPEED_UNIT = os.environ.get('NETWORK_SPEED_UNIT', 'kB/s')
LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'info')

# Tests
if __name__ == '__main__':
    # Test MQTT configuration
    assert MQTT_USER is not None, "MQTT_USER is not set"
    assert MQTT_PASS is not None, "MQTT_PASS is not set"
    assert MQTT_PORT is not None, "MQTT_PORT is not set"
    assert MQTT_BROKER is not None, "MQTT_BROKER is not set"
    print("MQTT configuration tests passed.")

    # Test network speed unit parsing
    try:
        unit = get_network_unit(NETWORK_SPEED_UNIT)
        print(f"Network speed unit '{NETWORK_SPEED_UNIT}' is valid.")
    except Exception as e:
        print(f"Network speed unit test failed: {e=}")

    # Test logging level parsing
    try:
        level = get_logging_level(LOGGING_LEVEL)
        assert isinstance(level, int), "Logging level should be an integer"
        print(f"Logging level '{LOGGING_LEVEL}' is valid.")
    except Exception as e:
        print(f"Logging level test failed: {e=}")
