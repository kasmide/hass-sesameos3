from abc import ABC, abstractmethod
import asyncio
import base64
import logging
from typing import Optional, TypeAlias, Callable

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
    def __init__(self, entry: SesameConfigEntry) -> None:
        self.hass = entry.hass
        self.client = SesameClient(
            entry.data[CONF_MAC], base64.b64decode(entry.data["private_key"])
        )
        self.device_info = None
        self.entry = entry
        self._unsub_scanner: Optional[Callable[[], None]] = None
        self.client.on_disconnect(self._on_client_disconnect)

    async def _device_present(self) -> bool:
        return bluetooth.async_address_present(self.hass, self.entry.data[CONF_MAC])

    def _on_client_disconnect(self) -> None:
        self._start_scan()

    def _start_scan(self) -> None:
        if self._unsub_scanner is not None:
            return
        self._unsub_scanner = bluetooth.async_register_callback(
            self.hass,
            self._async_device_found,
            {"address": self.entry.data[CONF_MAC]},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

    def _stop_scan(self) -> None:
        if self._unsub_scanner is not None:
            self._unsub_scanner()
            self._unsub_scanner = None

    def _async_device_found(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        self.hass.async_create_task(self._async_connect(service_info.device))

    async def _async_connect(self, ble_device) -> None:
        try:
            await self.client.connect(ble_device)
        except Exception as err:  # pragma: no cover - connection may fail
            _LOGGER.warning("Connect failed: %s", err)
        else:
            self._stop_scan()


    async def initialize(self):
        if await self._device_present():
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.entry.data[CONF_MAC], connectable=True
            )
            if ble_device:
                await self.client.connect(ble_device)

        if not self.client.is_connected:
            _LOGGER.debug(
                "Device %s not found during initialization", self.entry.data[CONF_MAC]
            )
            self._start_scan()
            return
        if self.client.mech_status is None:
            try:
                await self.client.wait_for(Event.MechStatusEvent)
            except TimeoutError:
                pass
        await self.populate_device_info()
        self._start_scan()
        

    async def disconnect(self):
        self._stop_scan()
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
