import json
import logging
import paho.mqtt.client as mqtt

from typing import Callable, Union
from paho.mqtt.client import ConnectFlags, DisconnectFlags, ReasonCode, Properties
from paho.mqtt.packettypes import PacketTypes

from vars import *
from HAEntities import *
from DiagUtil import get_hostname

_LOGGER = logging.getLogger(__name__)

class HAPublisher:
    def __init__(
        self,
        broker = MQTT_BROKER,
        port = MQTT_PORT,
        username = MQTT_USER,
        password = MQTT_PASS,
    ):
        self.broker = broker
        self.port = port

        # Specify the callback API version
        self.client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            protocol=mqtt.MQTTProtocolVersion.MQTTv5,
        )

        self.client.will_set(f"{MQTT_PYDIAG_PREFIX}avail/{MQTT_CLIENT_ID}", 'offline', 1, retain=True)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.username_pw_set(username, password)

        self.entity_value_getter_map: Dict[BaseEntity, Callable[[], Any]] = {}

    def _on_connect(self, client: mqtt.Client, userdata: any, cf: ConnectFlags, rc: ReasonCode, properties: Union[Properties, None]):
        connection_results = {
            0: "Connection successful",
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorized"
        }

        rm = connection_results.get(rc.value, f"Unknown connection result code: {rc.json()}")
        _LOGGER.debug(f"MQTT Connection Attempt: {rm}")
        _LOGGER.debug(f"Detailed connection flags: {cf}")
        if properties:
            _LOGGER.debug(f"Connection properties: {properties}")
        if rc.is_failure:
            _LOGGER.error("Failed to connect to MQTT broker")
            raise Exception("Failed to connect to MQTT broker")

        self.client.publish(f"{MQTT_PYDIAG_PREFIX}avail/{MQTT_CLIENT_ID}", 'online', 1, retain=True)

    def _on_disconnect(self, client: mqtt.Client, userdata: any, df: DisconnectFlags, rc: ReasonCode, properties: Union[Properties, None]):
        disconnect_reasons = {
            0: "Normal disconnection",
            1: "Disconnected with unspecified error",
        }

        rm = disconnect_reasons.get(rc.value, f"Unknown connection result code: {rc.json()}")
        _LOGGER.debug(f"MQTT Disconnect Attempt: {rm}")
        _LOGGER.debug(f"Detailed disconnect flags: {df}")
        if properties:
            _LOGGER.debug(f"Connection properties: {properties}")
        if rc.is_failure:
            _LOGGER.error("Failed to connect to MQTT broker")
            raise Exception("Failed to connect to MQTT broker")

    async def connect(self):
        try:
            _LOGGER.info(f"Attempting to connect to MQTT broker at {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port)
            _LOGGER.info(f"Connected!")
            self.client.loop_start()
        except Exception as e:
            _LOGGER.error(f"CRITICAL MQTT Connection Error: {e}")
            raise

    async def register_entity(self, entity: BaseEntity, value_getter: Callable[[], Any]):
        _LOGGER.info(f"Registering entity '{entity.name}' [{entity.unique_id}]")

        config_topic = entity.config_topic()
        entity_config = entity.to_dict()

        try:
            self.client.publish(
                config_topic,
                json.dumps(entity_config),
                retain=True,
                properties=Properties(PacketTypes.PUBLISH)
            ).wait_for_publish()

            self.entity_value_getter_map[entity] = value_getter
        except Exception as e:
            _LOGGER.exception(f"Failed to register entity '{entity.name}'")
            raise

    async def publish_entity_state(self, entity: BaseEntity, state_value: Any):
        state_topic = entity.state_topic()

        try:
            value: str
            if type(state_value) is str:
                value = state_value
            else:
                value = json.dumps(state_value)
            _LOGGER.debug(f"Publishing new entity state for '{entity.name}' [{value}]")
            self.client.publish(state_topic, value).wait_for_publish()
        except Exception as e:
            _LOGGER.exception(f"Failed to publish entity state for '{entity.name}' (Value: '{state_value}')")
            raise

    async def publish_all(self):
        for entity, func in self.entity_value_getter_map.items():
            await self.publish_entity_state(entity, func())

    def __del__(self):
        """Ensure clean disconnection when object is destroyed."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            _LOGGER.error(f"Error during cleanup: {e}", e)
            raise
