from abc import ABC, abstractmethod
import base64
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_MAC
from homeassistant.helpers.device_registry import format_mac, DeviceInfo, CONNECTION_BLUETOOTH

from sesameos3client import SesameClient

type SesameConfigEntry = ConfigEntry[SesameDevice]

class SesameDevice(ABC):
    offers: list[Platform] = []
    device_info: Optional[DeviceInfo]
    def __init__(self, entry: SesameConfigEntry) -> None:
        self.client = SesameClient(entry.data[CONF_MAC], base64.b64decode(entry.data["private_key"]))
        self.device_info = None
        self.entry = entry

    async def connect(self):
        await self.client.connect()

    async def disconnect(self):
        await self.client.disconnect()

    async def populate_device_info(self, entry: SesameConfigEntry) -> None:
        self.device_info = DeviceInfo(
            identifiers={(entry.domain, format_mac(entry.data[CONF_MAC]))},
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_MAC])},
            name=entry.title,
            manufacturer="CANDY HOUSE JAPAN, Inc."
        )
    @abstractmethod
    def get_entities(self, entity_type: Platform):
        raise NotImplementedError("Subclasses must implement get_entities method")