"""Sensor platform — the `TemperatureSensor` and `AnalogGauge` capabilities."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import capability_map as cm
from .const import DOMAIN
from .entity import JustworxCapabilityEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        JustworxSensor(coordinator, serial, id_entry["idNumber"])
        for serial, device in coordinator.data.items()
        for id_entry in device.get("ids", [])
        if cm.is_supported(id_entry) and cm.platform_for(id_entry["capability"]["type"]) == "sensor"
    ]
    async_add_entities(entities)


class JustworxSensor(JustworxCapabilityEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_class(self) -> SensorDeviceClass | None:
        cap = self._capability or {}
        return SensorDeviceClass.TEMPERATURE if cap.get("type") == "TemperatureSensor" else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        cap = self._capability or {}
        # AnalogGauge carries no server-side unit in v1 — surface unitless.
        return UnitOfTemperature.CELSIUS if cap.get("type") == "TemperatureSensor" else None

    @property
    def native_value(self):
        entry = self._id_entry
        return cm.sensor_value(entry) if entry else None
