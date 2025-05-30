"""The SesameOS 3 integration."""

from __future__ import annotations
import base64
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_MAC
from homeassistant.core import HomeAssistant
from sesameos3client import SesameClient

_PLATFORMS: list[Platform] = [Platform.LOCK]

type SesameConfigEntry = ConfigEntry[SesameClient]


async def async_setup_entry(hass: HomeAssistant, entry: SesameConfigEntry) -> bool:
    """Set up SesameOS 3 from a config entry."""
    entry.runtime_data = SesameClient(entry.data[CONF_MAC], base64.b64decode(entry.data["private_key"]))
    await entry.runtime_data.connect()

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: SesameConfigEntry) -> bool:
    """Unload a config entry."""
    if (unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)):
        await entry.runtime_data.disconnect()
    return unload_ok
