"""The Justworx integration — control Justworx devices via the Justworx API (cloud_push).

Auth is OAuth2 (account-linked). We bundle a public PKCE client so the user just logs in —
no API key, matching the Alexa/Google/claude.ai experience.
"""

from __future__ import annotations

import asyncio

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from . import capability_map as cm
from .api import JustworxApi
from .const import CLIENT_ID, DEFAULT_BASE_URL, DOMAIN, STREAM_FALLBACK_INTERVAL, STREAM_URL
from .coordinator import JustworxCoordinator
from .stream import run_event_stream

PLATFORMS = cm.PLATFORMS  # ["binary_sensor","cover","light","lock","sensor","switch"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Bundle the public PKCE client so users never register their own OAuth app."""
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, ""), "Justworx"
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(hass, entry)
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    async def token_getter() -> str:
        await oauth_session.async_ensure_token_valid()
        return oauth_session.token["access_token"]

    session = async_get_clientsession(hass)
    api = JustworxApi(session, DEFAULT_BASE_URL, token_getter)

    # Real-time comes from the WebSocket push; the coordinator poll is only a slow safety net.
    coordinator = JustworxCoordinator(hass, api, STREAM_FALLBACK_INTERVAL)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Hold the WebSocket stream open for the entry's lifetime (cloud_push). It pulls a fresh token
    # per (re)connect.
    stop = asyncio.Event()
    task = entry.async_create_background_task(
        hass,
        run_event_stream(coordinator, session, STREAM_URL, api, token_getter, stop),
        name="justworx-stream",
    )

    def _stop_stream() -> None:
        stop.set()
        task.cancel()

    entry.async_on_unload(_stop_stream)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
