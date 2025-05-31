from typing import Optional
from homeassistant.helpers.device_registry import format_mac, DeviceInfo
from homeassistant.const import CONF_MAC
from homeassistant.components.lock import LockEntity
from propcache.api import cached_property

from sesameos3client import SesameClient, EventData, Event

from .__init__ import SesameConfigEntry


async def async_setup_entry(hass, entry: SesameConfigEntry, async_add_entities):
    async_add_entities(
        [SesameLock(entry)]
    )

class SesameLock(LockEntity):
    _attr_has_entity_name = True # nanikore
    _client: SesameClient
    _last_mechstatus: Optional[EventData.MechStatus]
    _attr_should_poll = False
    def __init__(self, entry: SesameConfigEntry) -> None:
        self._client = entry.runtime_data
        self._client.add_listener(Event.MechStatusEvent, self._on_mech_status)
        self._attr_unique_id = format_mac(entry.data[CONF_MAC])
        self._last_mechstatus = self._client.mech_status
        self._attr_name = None
        self._attr_device_info = DeviceInfo(
            identifiers={(entry.domain, self._attr_unique_id)},
            name=entry.title,
            manufacturer="CANDY HOUSE JAPAN, Inc."
        )

    async def async_lock(self, **kwargs) -> None:
        await self._client.lock("Home Assistant")

    async def async_unlock(self, **kwargs) -> None:
        await self._client.unlock("Home Assistant")

    def _on_mech_status(self, event: Event.MechStatusEvent, metadata) -> None:
        self._last_mechstatus = event.response
        self._attr_is_locked = self._last_mechstatus.lock_range
        self.async_write_ha_state()