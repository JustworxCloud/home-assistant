"""Lock platform — the `Lock` capability (secure: unlock is confirmed)."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import capability_map as cm
from .const import DOMAIN
from .entity import JustworxCapabilityEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        JustworxLock(coordinator, serial, id_entry["idNumber"])
        for serial, device in coordinator.data.items()
        for id_entry in device.get("ids", [])
        if cm.is_supported(id_entry) and cm.platform_for(id_entry["capability"]["type"]) == "lock"
    ]
    async_add_entities(entities)


class JustworxLock(JustworxCapabilityEntity, LockEntity):
    @property
    def is_locked(self) -> bool | None:
        entry = self._id_entry
        return cm.lock_is_locked(entry) if entry else None

    async def async_lock(self, **kwargs) -> None:
        await self._send("lock")

    async def async_unlock(self, **kwargs) -> None:
        await self._send("unlock")
