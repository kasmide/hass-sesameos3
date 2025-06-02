import asyncio
import copy
from typing import Optional
from homeassistant.const import EntityCategory, Platform, CONF_MAC
from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.components.lock import LockEntity
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.device_registry import format_mac

from sesameos3client import Event, SesameClient, EventData

from .models import SesameDevice, SesameConfigEntry

class Sesame5(SesameDevice):
    class MechStatusSensor(SensorEntity):
        _attr_has_entity_name = True
        _attr_should_poll = False
        _attr_entity_category = EntityCategory.DIAGNOSTIC
        
        def __init__(self, device: "Sesame5",
                     attr_name: str,
                     icon: str = "mdi:information",
                     unit: Optional[str] = None,
                     device_class: Optional[SensorDeviceClass] = None,
                     default_disabled: bool = False) -> None:
            super().__init__()
            self._client = device.client
            self._client.add_listener(Event.MechStatusEvent, self._on_mech_status)
            self._value_name = attr_name
            self._attr_translation_key = attr_name
            self._attr_icon = icon
            self._attr_native_unit_of_measurement = unit
            self._attr_device_class = device_class
            self._attr_unique_id = format_mac(device.entry.data[CONF_MAC]) + "_" + attr_name
            self._attr_device_info = device.device_info
            self._attr_entity_registry_enabled_default = not default_disabled
            if device.client.mech_status is not None:
                self._attr_native_value = getattr(device.client.mech_status, self._value_name)

        def _on_mech_status(self, event: Event.MechStatusEvent, metadata) -> None:
            self._attr_native_value = getattr(event.response, self._value_name)
            self.async_write_ha_state()

    class MechStatusBinarySensor(BinarySensorEntity):
        _attr_has_entity_name = True
        _attr_should_poll = False
        _attr_entity_category = EntityCategory.DIAGNOSTIC
        
        def __init__(self, device: "Sesame5", 
                     attr_name: str,
                     icon: str = "mdi:information",
                     device_class: Optional[BinarySensorDeviceClass] = None,
                     default_disabled: bool = False) -> None:
            super().__init__()
            self._client = device.client
            self._client.add_listener(Event.MechStatusEvent, self._on_mech_status)
            self._value_name = attr_name
            self._attr_translation_key = attr_name
            self._attr_icon = icon
            self._attr_device_class = device_class
            self._attr_unique_id = format_mac(device.entry.data[CONF_MAC]) + "_" + attr_name
            self._attr_device_info = device.device_info
            self._attr_entity_registry_enabled_default = not default_disabled
            if device.client.mech_status is not None:
                self._attr_is_on = getattr(device.client.mech_status, self._value_name)

        def _on_mech_status(self, event: Event.MechStatusEvent, metadata) -> None:
            self._attr_is_on = getattr(event.response, self._value_name)
            self.async_write_ha_state()

    class SesameLock(LockEntity):
        _attr_has_entity_name = True
        _client: SesameClient
        _last_mechstatus: Optional[EventData.MechStatus]
        _attr_should_poll = False
        _attr_translation_key = "sesame_lock"
        def __init__(self, device: "Sesame5") -> None:
            self._client = device.client
            self._client.add_listener(Event.MechStatusEvent, self._on_mech_status)
            self._attr_unique_id = format_mac(device.entry.data[CONF_MAC])
            self._last_mechstatus = self._client.mech_status
            self._attr_name = None
            self._attr_device_info = device.device_info
            if self._last_mechstatus is not None:
                self._attr_is_locked = self._last_mechstatus.lock_range
            asyncio.create_task(self.set_changed_by())

        async def async_lock(self, **kwargs) -> None:
            await self._client.lock("Home Assistant")

        async def async_unlock(self, **kwargs) -> None:
            await self._client.unlock("Home Assistant")

        async def _on_mech_status(self, event: Event.MechStatusEvent, metadata) -> None:
            self._last_mechstatus = event.response
            self._attr_is_locked = self._last_mechstatus.lock_range
            self.async_write_ha_state()
            await self.set_changed_by()

        async def set_changed_by(self):
            history_type = EventData.HistoryData.HistoryType
            hist_entry = await self._client.get_history_tail()
            if hist_entry.response is not None:
                match hist_entry.response.type:
                    case history_type.AUTOLOCK:
                        self._attr_changed_by = "autolock"
                    case history_type.BLE_LOCK | history_type.BLE_UNLOCK:
                        self._attr_changed_by = "bluetooth"
                    case history_type.WEB_LOCK | history_type.WEB_UNLOCK:
                        self._attr_changed_by = "web"
                    case history_type.MANUAL_LOCKED | history_type.MANUAL_UNLOCKED | history_type.MANUAL_ELSE:
                        self._attr_changed_by = "manual"
                    case _:
                        self._attr_changed_by = None
            self.async_write_ha_state()
    class MechSettingsEntryEntity(NumberEntity):
        _attr_has_entity_name = True
        _attr_should_poll = False
        _attr_entity_category = EntityCategory.CONFIG
        _attr_native_max_value = 65535
        _attr_native_min_value = 0
        _attr_mode = NumberMode.BOX
        def __init__(self, device: "Sesame5", 
                     attr_name: str,
                     unit_of_measurement: str,
                     icon: str = "mdi:number",
                     device_class: Optional[NumberDeviceClass] = None) -> None:
            super().__init__()
            self._client = device.client
            self._client.add_listener(Event.MechSettingsEvent, self._on_mech_settings)
            self._value_name = attr_name
            if device.client.mech_settings is not None:
                self._attr_native_value = getattr(device.client.mech_settings, self._value_name)
            self._attr_unique_id = format_mac(device.entry.data[CONF_MAC]) + "_" + attr_name
            self._attr_translation_key = attr_name
            self._attr_icon = icon
            self._attr_native_unit_of_measurement = unit_of_measurement
            self._attr_device_class = device_class
            self._attr_device_info = device.device_info

        def _on_mech_settings(self, event: Event.MechSettingsEvent, metadata) -> None:
            self._attr_native_value = getattr(event.response, self._value_name)
            self.async_write_ha_state()

        async def async_set_native_value(self, value: float) -> None:
            if self._client.mech_settings is None:
                raise ValueError("Mech settings not available")
            new_settings = copy.copy(self._client.mech_settings)
            setattr(new_settings, self._value_name, int(value))
            await self._client.set_mech_settings(new_settings)

    offers = [Platform.LOCK, Platform.NUMBER, Platform.SENSOR, Platform.BINARY_SENSOR]

    def __init__(self, entry: SesameConfigEntry) -> None:
        super().__init__(entry)

    async def populate_device_info(self) -> None:
        await super().populate_device_info()
        assert self.device_info is not None
        self.device_info["model"] = "Sesame 5"
    
    def get_entities(self, entity_type: Platform):
        match entity_type:
            case Platform.LOCK:
                return [self.SesameLock(self)]
            case Platform.NUMBER:
                return [
                    self.MechSettingsEntryEntity(self, "auto_lock_seconds", "s", "mdi:timer-lock", NumberDeviceClass.DURATION),
                    self.MechSettingsEntryEntity(self, "lock", "°", "mdi:lock"),
                    self.MechSettingsEntryEntity(self, "unlock", "°", "mdi:lock-open-variant"),
                ]
            case Platform.SENSOR:
                return [
                    self.MechStatusSensor(self, "battery", "mdi:battery", "mV", SensorDeviceClass.VOLTAGE, default_disabled=True),
                    self.MechStatusSensor(self, "target", "mdi:target", default_disabled=True),
                    self.MechStatusSensor(self, "position", "mdi:angle-acute"),
                ]
            case Platform.BINARY_SENSOR:
                return [
                    self.MechStatusBinarySensor(self, "clutch_failed", "mdi:alert", BinarySensorDeviceClass.PROBLEM, default_disabled=True),
                    self.MechStatusBinarySensor(self, "lock_range", "mdi:lock", default_disabled=True),
                    self.MechStatusBinarySensor(self, "unlock_range", "mdi:lock-open-variant", default_disabled=True),
                    self.MechStatusBinarySensor(self, "critical", "mdi:alert-circle", BinarySensorDeviceClass.PROBLEM),
                    self.MechStatusBinarySensor(self, "stop", "mdi:stop-circle", default_disabled=True),
                    self.MechStatusBinarySensor(self, "low_battery", "mdi:battery-alert", BinarySensorDeviceClass.BATTERY),
                    self.MechStatusBinarySensor(self, "clockwise", "mdi:rotate-right", default_disabled=True),
                ]
            case _:
                return []
