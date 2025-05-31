from homeassistant.const import Platform

from .devices import SesameConfigEntry


async def async_setup_entry(hass, entry: SesameConfigEntry, async_add_entities):
    if Platform.SENSOR in entry.runtime_data.offers:
        async_add_entities(
            entry.runtime_data.get_entities(Platform.SENSOR),
        )