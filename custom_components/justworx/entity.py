"""Base entity: one Home Assistant entity per Justworx ID that carries a supported capability."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import capability_map as cm
from .const import DOMAIN, MANUFACTURER
from .coordinator import JustworxCoordinator


class JustworxCapabilityEntity(CoordinatorEntity[JustworxCoordinator]):
    """Ties one ID's capability (serial + idNumber) to the coordinator's snapshot.

    Identified by idNumber, not by a separate controlId -- /api/v2 has no controlId concept;
    the ID itself, addressed by idNumber, is the stable identifier. `capability` is a sub-object
    on that same ID, not a parallel list.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: JustworxCoordinator, serial: str, id_number: int) -> None:
        super().__init__(coordinator)
        self._serial = serial
        self._id_number = id_number
        self._attr_unique_id = f"{serial}:{id_number}"
        entry = self._id_entry or {}
        self._attr_name = cm.display_name(entry) if entry else str(id_number)

    @property
    def _device(self) -> dict:
        return self.coordinator.data.get(self._serial) or {}

    @property
    def _id_entry(self) -> dict | None:
        for entry in self._device.get("ids", []):
            if entry.get("idNumber") == self._id_number:
                return entry
        return None

    @property
    def _capability(self) -> dict | None:
        entry = self._id_entry
        return entry.get("capability") if entry else None

    @property
    def device_info(self) -> DeviceInfo:
        dev = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            name=dev.get("name") or dev.get("serial") or self._serial,
            manufacturer=MANUFACTURER,
            serial_number=dev.get("serial"),
        )

    @property
    def available(self) -> bool:
        return super().available and self._device.get("online", False) and self._id_entry is not None

    async def _send(self, intent: str) -> None:
        """Resolve an HA action intent to a raw write on this ID and send it."""
        entry = self._id_entry
        if entry is None:
            return
        value = cm.resolve_write_value(entry, intent)
        if value is None:
            return
        # Secure capabilities (lock/garage) confirm actuation; HA has no platform PIN requirement.
        cap = entry.get("capability") or {}
        confirm = bool(cap.get("secure"))
        await self.coordinator.api.set_id_value(self._serial, self._id_number, value, confirm=confirm)
        await self.coordinator.async_request_refresh()
