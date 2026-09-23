"""Minimal async client for the Justworx API (/api/v2).

Uses Home Assistant's shared aiohttp session. Auth is an OAuth2 access token, obtained fresh from a
`token_getter` before every request so it is always valid (HA's OAuth2Session refreshes as needed).
Only the endpoints the integration needs.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import aiohttp


class JustworxApiError(Exception):
    """A Justworx API error carrying the HTTP status + stable code."""

    def __init__(self, status: int, code: str, detail: str | None = None) -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.status = status
        self.code = code
        self.detail = detail


class JustworxAuthError(JustworxApiError):
    """401/403 — token rejected or under-scoped."""


class JustworxApi:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        token_getter: Callable[[], Awaitable[str]],
    ) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._token = token_getter  # async () -> a valid OAuth2 access token

    async def _request(self, method: str, path: str, json: dict | None = None, params: dict | None = None) -> dict:
        url = f"{self._base}{path}"
        token = await self._token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        try:
            async with asyncio.timeout(30):
                async with self._session.request(method, url, headers=headers, json=json, params=params) as resp:
                    body = await resp.json(content_type=None)
                    if resp.status in (401, 403):
                        raise JustworxAuthError(resp.status, (body or {}).get("error", "UNAUTHORIZED"), (body or {}).get("detail"))
                    if resp.status >= 400:
                        raise JustworxApiError(resp.status, (body or {}).get("error", f"HTTP_{resp.status}"), (body or {}).get("detail"))
                    return body or {}
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise JustworxApiError(0, "NETWORK_ERROR", str(err)) from err

    async def whoami(self) -> dict:
        return await self._request("GET", "/me")

    async def list_devices(self) -> dict:
        return await self._request("GET", "/devices")

    async def get_device(self, serial: str) -> dict:
        """The device's full twin -- name, online, network, location, `ids[]` (each carrying its
        own `capability`), `rules[]`. There is no separate capabilities[] list any more; a
        capability lives on the ID it was authored against."""
        return await self._request("GET", f"/devices/{serial}")

    # ---- ID actuation -------------------------------------------------------------------------
    # There is no abstract capability-command endpoint on /api/v2 -- POST /devices/{serial}/commands
    # is gone, and nothing replaced it. Every write is a direct write to the ID the capability sits
    # on. This is not a loss for actuation: `momentaryOutput`/`delayedOutput` ignore the value sent
    # and fire their configured behaviour regardless, so a single set_id_value call correctly
    # handles both a sustained relay (a real high/low write) and a momentary pulse relay (any write
    # triggers the same pulse) without the caller needing to know which.

    async def set_id_value(self, serial: str, id_number: int, value, *, confirm: bool = False) -> dict:
        body: dict = {"value": value}
        if confirm:
            body["timeoutMs"] = 8000
        return await self._request("PUT", f"/devices/{serial}/ids/{id_number}/value", json=body)

    # ---- events ---------------------------------------------------------------------------------
    # Long-poll is not only a fallback for the WebSocket: the socket requires a `since` cursor on
    # connect, and omitting it replays the account's entire history rather than starting from now.
    # A wait_ms=0 call here is used purely to obtain a fresh cursor before the socket connects.

    async def get_events(self, since: str | None = None, wait_ms: int = 0) -> dict:
        params: dict = {"waitMs": str(wait_ms)}
        if since:
            params["since"] = since
        return await self._request("GET", "/events", params=params)
