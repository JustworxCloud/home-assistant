"""Polls the Justworx API and holds the latest device+ID snapshot."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import JustworxApi, JustworxApiError, JustworxAuthError
from .const import DOMAIN
from .events import apply_event

_LOGGER = logging.getLogger(__name__)


class JustworxCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Fetches every accessible device with its twin (ids[], each carrying its own capability),
    keyed by serial."""

    def __init__(self, hass: HomeAssistant, api: JustworxApi, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.cursor: str | None = None  # last events cursor seen, for the WebSocket to resume from

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            listing = await self.api.list_devices()
            devices: dict[str, dict] = {}
            for summary in listing.get("items", []):
                serial = summary["serial"]
                # get_device carries the live twin: ids[], each with its own `capability`.
                devices[serial] = await self.api.get_device(serial)
            return devices
        except JustworxAuthError as err:
            # Surfaces as a re-auth flow in HA.
            from homeassistant.exceptions import ConfigEntryAuthFailed

            raise ConfigEntryAuthFailed(str(err)) from err
        except JustworxApiError as err:
            raise UpdateFailed(f"Justworx API error: {err}") from err

    def apply_stream_event(self, item: dict) -> None:
        """Merge one real-time WebSocket/long-poll event item into the current data + notify
        entities (cloud_push). `item` is one EventItem: {cursor, ts, type, event, serial,
        message, actor, channel, data}."""
        cursor = item.get("cursor")
        if cursor:
            self.cursor = cursor
        devices = dict(self.data or {})
        apply_event(devices, item)
        self.async_set_updated_data(devices)
