import os, socket, psutil

from subprocess import check_output
from re import findall

MODEL_PATH = '/proc/device-tree/model'
SERIAL_NUMBER_PATH = '/proc/device-tree/serial-number'

memory = {}

def cache(f: 'function'):
    name = f.__name__
    def wrapper(*a, **kw):
        if name in memory:
            return memory[name]
        memory[name] = f(*a, **kw)
        return memory[name]
    return wrapper

def strip(f: 'function'):
    def wrapper(*a, **kw):
        result: str = f(*a, **kw)
        result = result.strip()
        if result.endswith('\u0000'):
            result = result[:-1]
        return result
    return wrapper

@cache
def is_raspberrypi():
    if not os.path.exists(MODEL_PATH):
        return False
    with open(MODEL_PATH, 'r') as f:
        return f.read().lower().startswith('raspberry pi')

@strip
@cache
def get_hostname() -> str:
    return socket.gethostname().strip()

@strip
@cache
def get_rpi_model() -> str | None:
    if not is_raspberrypi():
        return None
    with open(MODEL_PATH, 'r') as f:
        return f.read().strip()

@strip
@cache
def get_serial_number() -> str:
    if os.path.exists(SERIAL_NUMBER_PATH):
        # For Raspberry Pi or similar devices with a specific path for the serial number
        with open(SERIAL_NUMBER_PATH, 'r') as f:
            return f.read().strip()
    try:
        if os.name == 'posix':
            # For Linux systems
            return check_output(["sudo", "dmidecode", "-s", "system-serial-number"], text=True).strip()
        elif os.name == 'nt':
            # For Windows systems
            result = check_output(["wmic", "bios", "get", "serialnumber"], text=True)
            return result.splitlines()[1].strip()
        else:
            return str(abs(hash(get_hostname())))
    except Exception as e:
        return str(abs(hash(get_hostname())))

def get_temp() -> float:
    try:
        if is_raspberrypi():
            # For Raspberry Pi, using `vcgencmd`
            temp = check_output(["vcgencmd", "measure_temp"], text=True)
            return float(findall(r"\d+\.\d+", temp)[0])
        elif os.name == 'posix':
            # Generic Linux, reading from thermal zone
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                # Convert millidegrees to degrees Celsius
                return int(f.read().strip()) / 1000.0
        elif os.name == 'nt':
            # On Windows, use WMI or psutil (less common for temperature sensors)
            import wmi
            w = wmi.WMI(namespace="root\\wmi")
            temperature_info = w.MSAcpi_ThermalZoneTemperature()[0]
            # Temperature in tenths of Kelvin
            return (temperature_info.CurrentTemperature / 10) - 273.15
        else:
            return 0  # Temperature retrieval not supported
    except Exception as e:
        return 0  # Return NaN if any error occurs

def get_disk_usage() -> float:
    return float(psutil.disk_usage('/').percent)

def get_memory_usage() -> float:
    return float(psutil.virtual_memory().percent)

def get_cpu_usage() -> float:
    return float(psutil.cpu_percent(interval=None))
