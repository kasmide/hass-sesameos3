from abc import ABC, abstractmethod
import asyncio
import base64
import logging
from typing import Optional, TypeAlias, Callable

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_MAC
from homeassistant.helpers.device_registry import (
    format_mac,
    DeviceInfo,
    CONNECTION_BLUETOOTH,
)
from homeassistant.components import bluetooth

from sesameos3client import Event, SesameClient

SesameConfigEntry: TypeAlias = ConfigEntry

_LOGGER = logging.getLogger(__name__)

class SesameDevice(ABC):
    offers: list[Platform] = []
    device_info: Optional[DeviceInfo]
    def __init__(self, hass: HomeAssistant, entry: SesameConfigEntry) -> None:
        self.hass = hass
        self.client = SesameClient(
            entry.data[CONF_MAC], base64.b64decode(entry.data["private_key"])
        )
        self.device_info = None
        self.entry = entry
        self._unsub_scanner: Optional[Callable[[], None]] = None
        self.client.on_disconnect(self._on_client_disconnect)

    def _on_client_disconnect(self) -> None:
        pass

    def _async_device_found(self, _service_info, change) -> None:
        if not self.client.is_connected:
            self.hass.async_create_task(self.initialize())

    async def initialize(self):
        if bluetooth.async_address_present(self.hass, self.entry.data[CONF_MAC], connectable=True):
            if not self.client.is_connected:
                await self.client.connect()
            if self.client.mech_status is None:
                try:
                    await self.client.wait_for(Event.MechStatusEvent)
                except TimeoutError:
                    pass
            await self.populate_device_info()

    def start_scanning(self) -> None:
        self.entry.async_on_unload(
            bluetooth.async_register_callback(
                self.hass,
                self._async_device_found,
                {"address": self.entry.data[CONF_MAC]},
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
        )

    async def disconnect(self):
        await self.client.disconnect()

    async def populate_device_info(self) -> None:
        self.device_info = DeviceInfo(
            identifiers={(self.entry.domain, format_mac(self.entry.data[CONF_MAC]))},
            connections={(CONNECTION_BLUETOOTH, self.entry.data[CONF_MAC])},
            name=self.entry.title,
            manufacturer="CANDY HOUSE JAPAN, Inc.",
            sw_version=await self.client.get_version()
        )
    @abstractmethod
    def get_entities(self, entity_type: Platform):
        raise NotImplementedError("Subclasses must implement get_entities method")
