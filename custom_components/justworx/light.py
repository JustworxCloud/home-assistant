"""Light platform — the `Light` capability (on/off in the MVP; brightness is a later pass)."""

from __future__ import annotations

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import capability_map as cm
from .const import DOMAIN
from .entity import JustworxCapabilityEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        JustworxLight(coordinator, serial, id_entry["idNumber"])
        for serial, device in coordinator.data.items()
        for id_entry in device.get("ids", [])
        if cm.is_supported(id_entry) and cm.platform_for(id_entry["capability"]["type"]) == "light"
    ]
    async_add_entities(entities)


class JustworxLight(JustworxCapabilityEntity, LightEntity):
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool | None:
        entry = self._id_entry
        return cm.switch_is_on(entry) if entry else None

    async def async_turn_on(self, **kwargs) -> None:
        await self._send("on")

    async def async_turn_off(self, **kwargs) -> None:
        await self._send("off")
