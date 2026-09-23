"""cloud_push -- hold the WebSocket event stream open and feed events to the coordinator.

Replaces the SSE stream at GET /events/stream, withdrawn 2026-08-30 (it never delivered a byte
through Cloudflare -- perfect at origin, zero bytes at the edge). The WebSocket at
wss://api.justworx.com/api/v2/stream is the replacement, preferred transport (~110ms push).

Runs as a background task for the integration's lifetime. The socket requires a `since` cursor in
its first frame -- omitting it replays the account's ENTIRE history rather than starting from now
-- so a long-poll round always runs first, purely to obtain one, before the socket ever connects.
Reconnects with backoff on drop, resuming from the last cursor seen; the coordinator's slow
fallback poll (a full re-fetch) covers any gap in the meantime.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import aiohttp

from .api import JustworxApi

_LOGGER = logging.getLogger(__name__)


async def run_event_stream(
    coordinator,
    session: aiohttp.ClientSession,
    stream_url: str,
    api: JustworxApi,
    token_getter: Callable[[], Awaitable[str]],
    stop: asyncio.Event,
) -> None:
    backoff = 1

    while not stop.is_set():
        try:
            since = coordinator.cursor
            if since is None:
                # First connect ever this run: bootstrap a cursor with a long-poll round rather
                # than connecting with no `since` at all.
                page = await api.get_events(wait_ms=0)
                since = page.get("cursor")
                coordinator.cursor = since

            token = await token_getter()
            async with session.ws_connect(stream_url, heartbeat=None) as ws:
                await ws.send_json({"type": "subscribe", "token": token, "since": since})
                backoff = 1
                _LOGGER.debug("Justworx WebSocket connected")

                async for msg in ws:
                    if stop.is_set():
                        break
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    frame = msg.json()
                    ftype = frame.get("type")

                    if ftype == "ping":
                        await ws.send_json({"type": "pong"})
                        continue
                    if frame.get("error"):
                        # UNAUTHORIZED (no/invalid token) or INVALID_FIELDS (bad first frame). The
                        # socket stays open -- send a correct frame and carry on -- but a token
                        # rejection here means it is time to fetch a fresh one and reconnect.
                        _LOGGER.debug("Justworx WebSocket error frame: %s", frame.get("detail"))
                        break

                    # An EventPage: {items, cursor, hasMore}, same shape GET /events returns.
                    for item in frame.get("items", []):
                        coordinator.apply_stream_event(item)
                    if frame.get("cursor"):
                        coordinator.cursor = frame["cursor"]
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 -- reconnect on any transport error
            if stop.is_set():
                break
            _LOGGER.debug("Justworx WebSocket dropped (%s); reconnecting in %ss", err, backoff)
            try:
                await asyncio.wait_for(stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 60)
