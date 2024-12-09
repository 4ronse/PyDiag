import json
import logging
import paho.mqtt.client as mqtt

from typing import Callable, Union, Dict, Any
from datetime import datetime, timedelta

from paho.mqtt.client import ConnectFlags, DisconnectFlags, ReasonCode, Properties
from paho.mqtt.packettypes import PacketTypes

from vars import *
from HAEntities import BaseEntity

# Configure logger
_LOGGER = logging.getLogger(__name__)

# Memory to cache entity states and prevent unnecessary republishing
class _MemoryCacheDict(dict):
    def __init__(self, *a, **kw) -> None:
        super(*a, **kw)
        self.last_updated_map: Dict[Any, datetime] = {}

    def __setitem__(self, key, value):
        self.last_updated_map[key] = datetime.now()
        return super().__setitem__(key, value)

    def __getitem__(self, key):
        return super().__getitem__(key)

    def when_was_updated(self, key) -> datetime | None:
        if key not in self.last_updated_map:
            return None
        return self.last_updated_map[key]

    def items(self):
        return [(x[0], x[1], self.last_updated_map[x[0]]) for x in super().items()]

_entity_state_memory: _MemoryCacheDict[BaseEntity, Any] = _MemoryCacheDict()

class HAPublisher:
    """
    A class to handle MQTT publication for Home Assistant entities.

    This class manages MQTT connections, entity registration, and state publishing
    for monitoring and diagnostic purposes.

    Attributes:
        broker (str): MQTT broker address
        port (int): MQTT broker port
        client (mqtt.Client): MQTT client instance
        entity_value_getter_map (Dict[BaseEntity, Callable]): Map of entities to their value getters
    """

    def __init__(
        self,
        broker: str = MQTT_BROKER,
        port: int = MQTT_PORT,
        username: str = MQTT_USER,
        password: str = MQTT_PASS,
    ):
        """
        Initialize the HAPublisher with MQTT connection parameters.

        Args:
            broker (str, optional): MQTT broker address. Defaults to MQTT_BROKER.
            port (int, optional): MQTT broker port. Defaults to MQTT_PORT.
            username (str, optional): MQTT username. Defaults to MQTT_USER.
            password (str, optional): MQTT password. Defaults to MQTT_PASS.
        """
        self.broker = broker
        self.port = port

        # Use MQTT v5 with extended callback capabilities
        self.client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            protocol=mqtt.MQTTProtocolVersion.MQTTv5,
        )

        # Set up last will message to indicate device availability
        self.client.will_set(f"{MQTT_PYDIAG_PREFIX}avail/{MQTT_CLIENT_ID}", 'offline', 1, retain=True)

        # Configure connection and authentication
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.username_pw_set(username, password)

        # Map to store entity-specific value getter functions
        self.entity_value_getter_map: Dict[BaseEntity, Callable[[], Any]] = {}

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        cf: ConnectFlags,
        rc: ReasonCode,
        properties: Union[Properties, None]
    ):
        """
        Callback method for handling MQTT connection events.

        Logs connection details and raises an exception if connection fails.

        Args:
            client (mqtt.Client): MQTT client instance
            userdata (Any): User-defined data
            cf (ConnectFlags): Connection flags
            rc (ReasonCode): Connection result code
            properties (Properties, optional): Connection properties
        """
        connection_results = {
            0: "Connection successful",
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorized"
        }

        rm = connection_results.get(rc.value, f"Unknown connection result code: {rc}")
        _LOGGER.debug(f"MQTT Connection Attempt: {rm}")
        _LOGGER.debug(f"Detailed connection flags: {cf}")

        if properties:
            _LOGGER.debug(f"Connection properties: {properties}")

        if rc.is_failure:
            _LOGGER.error("Failed to connect to MQTT broker")
            raise ConnectionError("Failed to connect to MQTT broker")

        # Publish online status
        self.client.publish(f"{MQTT_PYDIAG_PREFIX}avail/{MQTT_CLIENT_ID}", 'online', 1, retain=True)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        df: DisconnectFlags,
        rc: ReasonCode,
        properties: Union[Properties, None]
    ):
        """
        Callback method for handling MQTT disconnection events.

        Logs disconnection details and raises an exception on unexpected disconnects.

        Args:
            client (mqtt.Client): MQTT client instance
            userdata (Any): User-defined data
            df (DisconnectFlags): Disconnection flags
            rc (ReasonCode): Disconnection result code
            properties (Properties, optional): Disconnection properties
        """
        disconnect_reasons = {
            0: "Normal disconnection",
            1: "Disconnected with unspecified error",
        }

        rm = disconnect_reasons.get(rc.value, f"Unknown disconnection result code: {rc}")
        _LOGGER.debug(f"MQTT Disconnect Attempt: {rm}")
        _LOGGER.debug(f"Detailed disconnect flags: {df}")

        if properties:
            _LOGGER.debug(f"Disconnection properties: {properties}")

        if rc.is_failure:
            _LOGGER.error("Unexpected MQTT broker disconnection")
            raise ConnectionError("Unexpected MQTT broker disconnection")

    async def connect(self):
        """
        Establish an asynchronous connection to the MQTT broker.

        Attempts to connect to the broker and start the MQTT client loop.
        Raises an exception if connection fails.
        """
        try:
            _LOGGER.info(f"Attempting to connect to MQTT broker at {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port)
            _LOGGER.info("Connected successfully!")
            self.client.loop_start()
        except Exception as e:
            _LOGGER.error(f"CRITICAL MQTT Connection Error: {e}")
            raise

    async def register_entity(self, entity: BaseEntity, value_getter: Callable[[], Any]):
        """
        Register a new entity with its value getter function.

        Publishes the entity configuration to Home Assistant and stores
        the value getter for future state updates.

        Args:
            entity (BaseEntity): The entity to register
            value_getter (Callable): Function to retrieve the entity's current value

        Raises:
            Exception: If entity registration or configuration publishing fails
        """
        _LOGGER.info(f"Registering entity '{entity.name}' [{entity.unique_id}]")

        config_topic = entity.config_topic()
        entity_config = entity.to_dict()

        try:
            # Publish entity configuration with retained QoS
            self.client.publish(
                config_topic,
                json.dumps(entity_config),
                retain=True,
                properties=Properties(PacketTypes.PUBLISH)
            ).wait_for_publish()

            # Store the value getter for this entity
            self.entity_value_getter_map[entity] = value_getter
        except Exception as e:
            _LOGGER.exception(f"Failed to register entity '{entity.name}'")
            raise

    async def publish_entity_state(self, entity: BaseEntity, state_value: Any):
        """
        Publish the current state of an entity to Home Assistant.

        Skips publishing if the value hasn't changed to reduce unnecessary traffic.

        Args:
            entity (BaseEntity): The entity to update
            state_value (Any): The current state value of the entity

        Raises:
            Exception: If value parsing or publishing fails
        """
        state_topic = entity.state_topic()

        try:
            # Convert value to string, handling different types
            value = state_value if isinstance(state_value, str) else json.dumps(state_value)
        except Exception:
            _LOGGER.exception(f"Failed to parse value (Value: '{state_value}')")
            raise

        # Check if value has changed to prevent unnecessary publishing
        if (entity not in _entity_state_memory) or \
            (_entity_state_memory[entity] != value or datetime.now() - _entity_state_memory.when_was_updated(entity) > timedelta(seconds=MQTT_REPUBLISH_INTERVAL)):
            _entity_state_memory[entity] = value

            try:
                _LOGGER.debug(f"Publishing new entity state for '{entity.name}' [{value}]")
                self.client.publish(state_topic, value).wait_for_publish()
            except Exception:
                _LOGGER.exception(f"Failed to publish value (Value: '{state_value}')")
                raise
        else:
            _LOGGER.debug(f"Skipping sensor {entity.name}. Value unchanged [{value}]")

    async def publish_all(self):
        """
        Publish states for all registered entities.

        Iterates through registered entities and publishes their current states
        by calling their respective value getter functions.
        """
        for entity, getter in self.entity_value_getter_map.items():
            await self.publish_entity_state(entity, getter())

    def __del__(self):
        """
        Ensure clean disconnection when the object is destroyed.

        Stops the MQTT client loop and disconnects gracefully.
        """
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            _LOGGER.error(f"Error during MQTT cleanup: {e}")

if __name__ == '__main__':
    import asyncio

    async def main():
        d = _MemoryCacheDict()
        d['a'] = 'b'

        print(d.items())

        await asyncio.sleep(5)

        print(d, d.when_was_updated('a'))
        print(datetime.now())
        diff = datetime.now() - d.when_was_updated('a')
        print(f"{diff=}")

    asyncio.run(main())
