"""Cover platform — the `GarageDoor` and `Cover` capabilities."""

from __future__ import annotations

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import capability_map as cm
from .const import DOMAIN
from .entity import JustworxCapabilityEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        JustworxCover(coordinator, serial, id_entry["idNumber"])
        for serial, device in coordinator.data.items()
        for id_entry in device.get("ids", [])
        if cm.is_supported(id_entry) and cm.platform_for(id_entry["capability"]["type"]) == "cover"
    ]
    async_add_entities(entities)


class JustworxCover(JustworxCapabilityEntity, CoverEntity):
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    @property
    def device_class(self) -> CoverDeviceClass | None:
        cap = self._capability or {}
        return CoverDeviceClass.GARAGE if cm.device_class_for(cap.get("type")) == "garage" else None

    @property
    def is_closed(self) -> bool | None:
        entry = self._id_entry
        return cm.cover_is_closed(entry) if entry else None

    async def async_open_cover(self, **kwargs) -> None:
        await self._send("open")

    async def async_close_cover(self, **kwargs) -> None:
        await self._send("close")
