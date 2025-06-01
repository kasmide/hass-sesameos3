"""The SesameOS 3 integration."""

from __future__ import annotations
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .devices import Sesame5
from .models import SesameConfigEntry

_PLATFORMS: list[Platform] = [Platform.LOCK]

async def async_setup_entry(hass: HomeAssistant, entry: SesameConfigEntry) -> bool:
    """Set up SesameOS 3 from a config entry."""
    entry.runtime_data = Sesame5(entry)
    await entry.runtime_data.initialize()
    await hass.config_entries.async_forward_entry_setups(entry, entry.runtime_data.offers)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: SesameConfigEntry) -> bool:
    """Unload a config entry."""
    if (unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)):
        await entry.runtime_data.disconnect()
    return unload_ok
