import os
import socket
import psutil
import logging
from typing import Callable, Any, Dict
from subprocess import check_output
from re import findall

from vars import DEVICE_NAME

# Configure logging
_LOGGER = logging.getLogger(__name__)

# Paths for Raspberry Pi specific information
MODEL_PATH = '/proc/device-tree/model'
SERIAL_NUMBER_PATH = '/proc/device-tree/serial-number'

# Global memory cache for function results
_function_memory: Dict[str, Any] = {}

def cache(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    A decorator to cache function results to improve performance.

    Caches the result of a function based on its name. Subsequent calls
    with the same arguments will return the cached value.

    Args:
        func (Callable): The function to be cached

    Returns:
        Callable: A wrapped function that caches its results
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Use function name as cache key
        name = func.__name__

        # Return cached result if exists
        if name in _function_memory:
            return _function_memory[name]

        # Compute, cache, and return result
        _function_memory[name] = func(*args, **kwargs)
        return _function_memory[name]
    return wrapper

def strip(func: Callable[..., str]) -> Callable[..., str]:
    """
    A decorator to strip whitespace and null characters from string results.

    Args:
        func (Callable): The function returning a string

    Returns:
        Callable: A wrapped function that cleans the string result
    """
    def wrapper(*args: Any, **kwargs: Any) -> str:
        result: str = func(*args, **kwargs)
        result = result.strip()

        # Remove null character at the end if present
        if result.endswith('\u0000'):
            result = result[:-1]

        return result
    return wrapper

@cache
def is_raspberrypi() -> bool:
    """
    Determine if the current system is a Raspberry Pi.

    Returns:
        bool: True if the system is a Raspberry Pi, False otherwise
    """
    if not os.path.exists(MODEL_PATH):
        return False

    try:
        with open(MODEL_PATH, 'r') as f:
            return f.read().lower().startswith('raspberry pi')
    except IOError as e:
        _LOGGER.error(f"Error reading model path: {e}")
        return False

@strip
@cache
def get_hostname() -> str:
    """
    Get the system's hostname.

    Returns:
        str: The hostname of the system
    """
    try:
        return socket.gethostname()
    except Exception as e:
        _LOGGER.error(f"Error getting hostname: {e}")
        return "unknown_host"

@strip
@cache
def get_device_name() -> str:
    """
    Get the device name, prioritizing DEVICE_NAME from config.

    Returns:
        str: The device name
    """
    return DEVICE_NAME or get_hostname()

@strip
@cache
def get_rpi_model() -> str:
    """
    Get the Raspberry Pi model information.

    Returns:
        str: The Raspberry Pi model or 'No Model' if not a Raspberry Pi
    """
    if not is_raspberrypi():
        return 'No Model'

    try:
        with open(MODEL_PATH, 'r') as f:
            return f.read().strip()
    except IOError as e:
        _LOGGER.error(f"Error reading RPi model: {e}")
        return 'Model Read Error'

@strip
@cache
def get_serial_number() -> str:
    """
    Retrieve the system's serial number across different platforms.

    Returns:
        str: The system's serial number or a hash of the hostname as fallback
    """
    try:
        # First, check Raspberry Pi specific path
        if os.path.exists(SERIAL_NUMBER_PATH):
            with open(SERIAL_NUMBER_PATH, 'r') as f:
                return f.read().strip()

        # Attempt platform-specific serial number retrieval
        if os.name == 'posix':
            return check_output(["sudo", "dmidecode", "-s", "system-serial-number"], text=True).strip()
        elif os.name == 'nt':
            result = check_output(["wmic", "bios", "get", "serialnumber"], text=True)
            return result.splitlines()[1].strip()

        # Fallback to a hash of hostname
        return str(abs(hash(get_hostname())))

    except Exception as e:
        _LOGGER.warning(f"Could not retrieve serial number: {e}")
        return str(abs(hash(get_hostname())))

def get_temp() -> float:
    """
    Retrieve the system temperature across different platforms.

    Returns:
        float: System temperature in Celsius, or 0 if unable to retrieve
    """
    try:
        if is_raspberrypi():
            # Raspberry Pi temperature via vcgencmd
            temp = check_output(["vcgencmd", "measure_temp"], text=True)
            return float(findall(r"\d+\.\d+", temp)[0])

        elif os.name == 'posix':
            # Generic Linux temperature from thermal zone
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                # Convert millidegrees to degrees Celsius
                return int(f.read().strip()) / 1000.0

        elif os.name == 'nt':
            import wmi
            w = wmi.WMI(namespace=r"root\OpenHardwareMonitor")  # ! Requires OHM
            temperature_infos = w.Sensor()
            for sensor in temperature_infos:
                if sensor.Name == 'CPU Package':
                    return sensor.Value

        return 0.0  # Temperature retrieval not supported

    except Exception as e:
        _LOGGER.warning(f"Temperature retrieval failed: {e}")
        return 0.0

def get_disk_usage() -> float:
    """
    Get the current disk usage percentage.

    Returns:
        float: Percentage of disk space used
    """
    try:
        return float(psutil.disk_usage('/').percent)
    except Exception as e:
        _LOGGER.error(f"Disk usage retrieval failed: {e}")
        return 0.0

def get_memory_usage() -> float:
    """
    Get the current memory usage percentage.

    Returns:
        float: Percentage of memory used
    """
    try:
        return float(psutil.virtual_memory().percent)
    except Exception as e:
        _LOGGER.error(f"Memory usage retrieval failed: {e}")
        return 0.0

def get_cpu_usage() -> float:
    """
    Get the current CPU usage percentage.

    Returns:
        float: Percentage of CPU used
    """
    try:
        return float(psutil.cpu_percent(interval=None))
    except Exception as e:
        _LOGGER.error(f"CPU usage retrieval failed: {e}")
        return 0.0

def get_ifaces() -> list[str]:
    """
    Retrieve a list of network interfaces.

    Returns:
        list[str]: List of network interface names
    """
    try:
        return list(psutil.net_if_addrs().keys())
    except Exception as e:
        _LOGGER.error(f"Network interfaces retrieval failed: {e}")
        return []
