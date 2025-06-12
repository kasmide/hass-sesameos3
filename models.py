from abc import ABC, abstractmethod
import asyncio
import base64
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_MAC
from homeassistant.helpers import device_registry
from homeassistant.helpers.device_registry import (
    format_mac,
    DeviceInfo,
    CONNECTION_BLUETOOTH,
)
from homeassistant.components import bluetooth

from sesameos3client import Event, SesameClient

type SesameConfigEntry = ConfigEntry[SesameDevice]

class SesameDevice(ABC):
    offers: list[Platform] = []
    device_info: DeviceInfo
    def __init__(self, hass: HomeAssistant, entry: SesameConfigEntry) -> None:
        self.hass = hass
        self.client = SesameClient(
            entry.data[CONF_MAC], base64.b64decode(entry.data["private_key"])
        )
        self.entry = entry
        self.device_info = DeviceInfo(
            identifiers={(self.entry.domain, format_mac(self.entry.data[CONF_MAC]))},
            connections={(CONNECTION_BLUETOOTH, self.entry.data[CONF_MAC])},
            name=self.entry.title,
            manufacturer="CANDY HOUSE JAPAN, Inc.",
        )

    def _async_device_found(self, _service_info, change) -> None:
        self.hass.async_create_task(self._on_found())

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
        self.entry.async_on_unload(
           bluetooth.async_register_callback(
                self.hass,
                self._async_device_found,
                {"address": self.entry.data[CONF_MAC]},
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
        )

    async def _on_found(self):
        if not self.client.is_connected:
            await asyncio.sleep(2)
            await self.client.connect()
        if self.device_info is None:
            await self.populate_device_info()

    async def disconnect(self):
        await self.client.disconnect()

    async def populate_device_info(self) -> None:
        self.device_info["sw_version"] = await self.client.get_version()
        device_registry.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers=self.device_info.get("identifiers"),
            sw_version=self.device_info.get("sw_version"),
        )
    @abstractmethod
    def get_entities(self, entity_type: Platform):
        raise NotImplementedError("Subclasses must implement get_entities method")
