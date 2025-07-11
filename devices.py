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

from .models import SesameDevice

class Sesame5(SesameDevice):
    class MechStatusSensor(SesameDevice.Entity, SensorEntity):
        _attr_has_entity_name = True
        _attr_should_poll = False
        _attr_entity_category = EntityCategory.DIAGNOSTIC
        
        def __init__(self, device: "Sesame5",
                     attr_name: str,
                     icon: str = "mdi:information",
                     unit: Optional[str] = None,
                     device_class: Optional[SensorDeviceClass] = None,
                     default_disabled: bool = False) -> None:
            super().__init__(device)
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

        async def async_added_to_hass(self) -> None:
            await super().async_added_to_hass()
            self._client.add_listener(Event.MechStatusEvent, self._on_mech_status)

        async def async_will_remove_from_hass(self) -> None:
            self._client.remove_listener(Event.MechStatusEvent, self._on_mech_status)
            await super().async_will_remove_from_hass()

        def _on_mech_status(self, event: Event.MechStatusEvent, metadata) -> None:
            self._attr_native_value = getattr(event.response, self._value_name)
            self.async_write_ha_state()

    class MechStatusBinarySensor(SesameDevice.Entity, BinarySensorEntity):
        _attr_has_entity_name = True
        _attr_should_poll = False
        _attr_entity_category = EntityCategory.DIAGNOSTIC
        
        def __init__(self, device: "Sesame5", 
                     attr_name: str,
                     icon: str = "mdi:information",
                     device_class: Optional[BinarySensorDeviceClass] = None,
                     default_disabled: bool = False) -> None:
            super().__init__(device)
            self._value_name = attr_name
            self._attr_translation_key = attr_name
            self._attr_icon = icon
            self._attr_device_class = device_class
            self._attr_unique_id = format_mac(device.entry.data[CONF_MAC]) + "_" + attr_name
            self._attr_device_info = device.device_info
            self._attr_entity_registry_enabled_default = not default_disabled
            if device.client.mech_status is not None:
                self._attr_is_on = getattr(device.client.mech_status, self._value_name)

        async def async_added_to_hass(self) -> None:
            await super().async_added_to_hass()
            self._client.add_listener(Event.MechStatusEvent, self._on_mech_status)

        async def async_will_remove_from_hass(self) -> None:
            self._client.remove_listener(Event.MechStatusEvent, self._on_mech_status)
            await super().async_will_remove_from_hass()

        def _on_mech_status(self, event: Event.MechStatusEvent, metadata) -> None:
            self._attr_is_on = getattr(event.response, self._value_name)
            self.async_write_ha_state()

    class SesameLock(SesameDevice.Entity, LockEntity):
        _attr_has_entity_name = True
        _last_mechstatus: Optional[EventData.MechStatus]
        _attr_should_poll = False
        _attr_translation_key = "sesame_lock"
        def __init__(self, device: "Sesame5") -> None:
            super().__init__(device)
            self._attr_unique_id = format_mac(device.entry.data[CONF_MAC])
            self._last_mechstatus = self._client.mech_status
            self._attr_name = None
            self._attr_device_info = device.device_info
            if self._last_mechstatus is not None:
                self._attr_is_locked = self._last_mechstatus.lock_range
            if self._client.is_connected:
                asyncio.create_task(self.set_changed_by())

        async def async_added_to_hass(self) -> None:
            await super().async_added_to_hass()
            self._client.add_listener(Event.MechStatusEvent, self._on_mech_status)

        async def async_will_remove_from_hass(self) -> None:
            self._client.remove_listener(Event.MechStatusEvent, self._on_mech_status)
            await super().async_will_remove_from_hass()

        async def async_lock(self, **kwargs) -> None:
            self._attr_assumed_state = True
            self._attr_is_locking = True
            self.async_write_ha_state()
            try:
                await asyncio.gather(
                    self._client.lock("Home Assistant"),
                    self._client.wait_for(Event.MechStatusEvent)
                )
            finally:
                if self._attr_assumed_state:
                    self._attr_is_locking = False
                    self.async_write_ha_state()

        async def async_unlock(self, **kwargs) -> None:
            self._attr_assumed_state = True
            self._attr_is_unlocking = True
            self.async_write_ha_state()
            try:
                await asyncio.gather(
                    self._client.unlock("Home Assistant"),
                    self._client.wait_for(Event.MechStatusEvent)
                )
            finally:
                if self._attr_assumed_state:
                    self._attr_is_unlocking = False
                    self.async_write_ha_state()

        async def _on_mech_status(self, event: Event.MechStatusEvent, metadata) -> None:
            self._attr_assumed_state = False
            self._last_mechstatus = event.response
            if not self._last_mechstatus.stop:
                if self._client.mech_settings is None: # Keep these state unknown when we can't determine them
                    self._attr_is_locking = None
                    self._attr_is_unlocking = None
                else:
                    if self._last_mechstatus.clockwise == self._client.mech_settings.lock < self._client.mech_settings.unlock:
                        self._attr_is_locking = True
                        self._attr_is_unlocking = False
                    else:
                        self._attr_is_locking = False
                        self._attr_is_unlocking = True
            else:
                self._attr_is_locking = False
                self._attr_is_unlocking = False
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

    class MechSettingsEntryEntity(SesameDevice.Entity, NumberEntity):
        _attr_has_entity_name = True
        _attr_should_poll = False
        _attr_entity_category = EntityCategory.CONFIG
        _attr_mode = NumberMode.BOX
        def __init__(self, device: "Sesame5", 
                     attr_name: str,
                     unit_of_measurement: str,
                     value_range: tuple[int, int],
                     icon: str = "mdi:number",
                     device_class: Optional[NumberDeviceClass] = None) -> None:
            super().__init__(device)
            self._value_name = attr_name
            if device.client.mech_settings is not None:
                self._attr_native_value = getattr(device.client.mech_settings, self._value_name)
            self._attr_unique_id = format_mac(device.entry.data[CONF_MAC]) + "_" + attr_name
            self._attr_translation_key = attr_name
            self._attr_icon = icon
            self._attr_native_unit_of_measurement = unit_of_measurement
            self._attr_native_max_value = value_range[1]
            self._attr_native_min_value = value_range[0]
            self._attr_device_class = device_class
            self._attr_device_info = device.device_info

        async def async_added_to_hass(self) -> None:
            await super().async_added_to_hass()
            self._client.add_listener(Event.MechSettingsEvent, self._on_mech_settings)

        async def async_will_remove_from_hass(self) -> None:
            self._client.remove_listener(Event.MechSettingsEvent, self._on_mech_settings)
            await super().async_will_remove_from_hass()

        def _on_mech_settings(self, event: Event.MechSettingsEvent, metadata) -> None:
            self._attr_native_value = getattr(event.response, self._value_name)
            self.async_write_ha_state()

        async def async_set_native_value(self, value: float) -> None:
            if self._client.mech_settings is None:
                raise ValueError("Mech settings not available")
            new_settings = copy.copy(self._client.mech_settings)
            setattr(new_settings, self._value_name, int(value))
            await self._client.set_mech_settings(new_settings.lock, new_settings.unlock)
    class AutoLockTimeEntity(MechSettingsEntryEntity):
        def __init__(self, device: "Sesame5") -> None:
            super().__init__(device, "auto_lock_seconds", "s", (0, 65535), "mdi:timer-lock", NumberDeviceClass.DURATION)

        async def async_set_native_value(self, value: float) -> None:
            await self._client.set_autolock_time(int(value))


    offers = [Platform.LOCK, Platform.NUMBER, Platform.SENSOR, Platform.BINARY_SENSOR]

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
                    self.AutoLockTimeEntity(self),
                    self.MechSettingsEntryEntity(self, "lock", "°", (-32768, 32767), "mdi:lock"),
                    self.MechSettingsEntryEntity(self, "unlock", "°", (-32768, 32767), "mdi:lock-open-variant"),
                ]
            case Platform.SENSOR:
                return [
                    self.MechStatusSensor(self, "battery", "mdi:battery", "mV", SensorDeviceClass.VOLTAGE, default_disabled=True),
                    self.MechStatusSensor(self, "target", "mdi:target", "°", default_disabled=True),
                    self.MechStatusSensor(self, "position", "mdi:angle-acute", "°", ),
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
