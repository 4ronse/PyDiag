from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, fields

from HATypes import *
from MDIIcons import IconEnum
from vars import MQTT_PYDIAG_PREFIX, MQTT_HA_DISCOVERY_PREFIX, MQTT_CLIENT_ID

@dataclass
class DeviceInfoBuilder:
    name: str
    identifiers: list[str]
    manufacturer: str
    model: str

    configuration_url: Optional[str] = None
    hw_version: Optional[str] = None
    model_id: Optional[str] = None
    serial_number: Optional[str] = None
    suggested_area: Optional[str] = None
    sw_info: Optional[str] = None
    via_device: Optional[str] = None

    @classmethod
    def from_env(cls, dct: dict[str, any]) -> 'DeviceInfoBuilder':
        return cls(**dct)

    def build(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

@dataclass
class BaseEntity:
    # Common attributes across all entities
    name: str
    unique_id: str
    device: DeviceInfoBuilder
    icon: Optional[Union[IconEnum, str]] = None

    # Availability configuration
    availability_mode: Optional[AvailabilityMode] = 'latest'
    availability_template: Optional[str] = None

    # Additional common configurations
    enabled_by_default: bool = True
    entity_category: Optional[EntityCategory] = None
    entity_picture: Optional[str] = None
    qos: int = 0

    # Placeholder for entity_type, to be overridden by class property
    _entity_type: str = 'unknown'

    @property
    def entity_type(self) -> str:
        """Read-only property for entity type."""
        return self._entity_type

    def _build_availability(self) -> Optional[Dict[str, str]]:
        return {
            "topic": f"{MQTT_PYDIAG_PREFIX}avail/{MQTT_CLIENT_ID}",
            "payload_available": "online",
            "payload_not_available": "offline"
        }

    def state_topic(self):
        return f"{MQTT_PYDIAG_PREFIX}{MQTT_CLIENT_ID}/{self.unique_id}"

    def config_topic(self):
        device_name = ''.join(c if c.isalnum() or c in ['_', '-'] else '_' for c in self.device.name.lower())
        sensor_name = ''.join(c if c.isalnum() or c in ['_', '-'] else '_' for c in self.name.lower())

        return f"{MQTT_HA_DISCOVERY_PREFIX}{self.entity_type}/{device_name}/{sensor_name}/config"

    def to_dict(self) -> Dict[str, Any]:
        # Create base dictionary with common fields
        entity_dict = {
            "name": self.name,
            "unique_id": self.unique_id,
            "state_topic": self.state_topic(),
            "qos": self.qos,
            "device": self.device.build(),
        }

        # Get optional fields from the specific entity class
        optional_fields = {}
        for f in fields(self):
            # Skip fields that are always included or part of the base dict
            if f.name in ['name', 'unique_id', 'device', 'qos', '_entity_type']:
                continue

            value = getattr(self, f.name)

            # Special handling for icons from IconEnum
            if f.name == 'icon' and isinstance(value, IconEnum):
                value = value.value

            optional_fields[f.name] = value

        # Add optional fields, filtering out None values
        entity_dict.update({
            k: v for k, v in optional_fields.items()
            if v is not None
        })

        # Add availability information
        avail_info = self._build_availability()
        if avail_info:
            entity_dict.update({
                "availability": avail_info,
                # "availability_mode": self.availability_mode,
                # "availability_template": self.availability_template,
                # "availability_topic": self.availability_topic,
            })

        return entity_dict

    def __hash__(self) -> int:
        return hash(self.unique_id)

    def __eq__(self, o: any) -> bool:
        if not issubclass(type(o), self.__class__):
            return False
        return self.unique_id == o.unique_id

@dataclass
class Sensor(BaseEntity):
    # Sensor-specific attributes
    device_class: Optional[SensorDeviceClass] = None
    state_class: Optional[StateClass] = None
    unit_of_measurement: Optional[str] = None
    value_template: Optional[str] = None

    # Set entity_type at class level
    _entity_type: str = 'sensor'

    # Additional sensor configurations
    encoding: str = 'utf-8'
    expire_after: Optional[int] = None
    force_update: bool = False

    def __hash__(self) -> int:
        return hash(self.unique_id)

    def __eq__(self, o: any) -> bool:
        if not issubclass(type(o), self.__class__):
            return False
        return self.unique_id == o.unique_id

@dataclass
class BinarySensor(BaseEntity):
    # Binary Sensor-specific attributes
    device_class: Optional[BinarySensorDeviceClass] = None
    off_delay: Optional[int] = None
    payload_on: str = 'ON'
    payload_off: str = 'OFF'

    # Set entity_type at class level
    _entity_type: str = 'binary_sensor'

    def __hash__(self) -> int:
        return hash(self.unique_id)

    def __eq__(self, o: any) -> bool:
        if not issubclass(type(o), self.__class__):
            return False
        return self.unique_id == o.unique_id

if __name__ == '__main__':
    device_info = DeviceInfoBuilder(
        name='Agabubu',
        model='Device Model',
        manufacturer='Manufacturer',
        identifiers=[ '00:15:5d:7a:22:a3' ]
    )

    temperature_sensor = Sensor(
        name='Agabubu Internal Temperature',
        unique_id='bubu',
        device=device_info,
        device_class=SensorDeviceClass.TEMPERATURE,
        unit_of_measurement="°C",
        icon=IconEnum.TEMPERATURE_CELSIUS,
    )

    import json

    print(json.dumps(temperature_sensor.to_dict(), indent=2))
    print(f'ConfigTopic: {temperature_sensor.config_topic()}')
