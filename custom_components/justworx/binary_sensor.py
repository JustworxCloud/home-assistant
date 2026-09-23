"""Binary sensor platform — the `ContactSensor` and `MotionSensor` capabilities."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import capability_map as cm
from .const import DOMAIN
from .entity import JustworxCapabilityEntity

_DEVICE_CLASS = {
    "motion": BinarySensorDeviceClass.MOTION,
    "door": BinarySensorDeviceClass.DOOR,
    "window": BinarySensorDeviceClass.WINDOW,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        JustworxBinarySensor(coordinator, serial, id_entry["idNumber"])
        for serial, device in coordinator.data.items()
        for id_entry in device.get("ids", [])
        if cm.is_supported(id_entry) and cm.platform_for(id_entry["capability"]["type"]) == "binary_sensor"
    ]
    async_add_entities(entities)


class JustworxBinarySensor(JustworxCapabilityEntity, BinarySensorEntity):
    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        cap = self._capability or {}
        return _DEVICE_CLASS.get(cm.device_class_for(cap.get("type")))

    @property
    def is_on(self) -> bool | None:
        entry = self._id_entry
        return cm.binary_is_on(entry) if entry else None
