# Justworx — Home Assistant integration

Control and monitor Justworx devices from Home Assistant. This is a **cloud-push** custom
integration (HACS) that talks to the Justworx **API** (`/api/v2`) — no direct broker or server
access. Real-time updates arrive over a WebSocket.

It implements the Justworx **capability taxonomy**: `/api/v2` returns a `capability` on any ID
that was authored as one on the product template — `{type, names, secure}` — and this integration
maps each capability `type` to the right Home Assistant entity. There is no separate
`capabilities[]` list any more; a capability is a sub-object of the ID it sits on, addressed by
that ID's `idNumber`.

## Capability → entity mapping

| Justworx capability | HA entity | device_class |
|---------------------|-----------|--------------|
| `Switch` | `switch` | — |
| `Light` | `light` (on/off) | — |
| `Lock` | `lock` | — |
| `GarageDoor` | `cover` | `garage` |
| `Cover` | `cover` | — |
| `ContactSensor` | `binary_sensor` | `door` |
| `MotionSensor` | `binary_sensor` | `motion` |
| `TemperatureSensor` | `sensor` | `temperature` |
| `AnalogGauge` | `sensor` | — |

`Thermostat` / `Dimmer` / `FanSpeed` are in the taxonomy but deferred (climate/fan platforms
are a later pass). The mapping table lives in
[`capability_map.py`](custom_components/justworx/capability_map.py) — the single, unit-tested
source of the HA column of the taxonomy.

**Known limitation: on/off polarity is a default, not a verified fact.** `/api/v2` has no
abstract command list any more (see below), so a Lock/GarageDoor/Switch entity's state and
actuation follow a fixed convention — raw `high` = the active state (on/open/unlocked), `low` =
the inactive one — unless the ID's own `stateKeywords` say otherwise for that specific piece of
hardware. This has not been verified against real Lock/GarageDoor wiring; see
`capability_map.py`'s module docstring before trusting a Lock entity's locked/unlocked state as
ground truth on a device that has not set `stateKeywords`.

## How it works
- **Auth:** **OAuth2 (account-linked)** — you just **log in to Justworx** in the browser; no API key.
  The integration bundles a **public PKCE client** (no secret shipped) and links via the Justworx
  authorization server (`oauth.justworx.com`); the access token is forwarded to the API and
  auto-refreshed. Matches the Alexa / Google / claude.ai experience.
- **State (`cloud_push`):** the integration holds a **WebSocket** connection to
  `wss://api.justworx.com/api/v2/stream` and updates entities the instant a device reports — no
  active polling. A `value_reported` event updates the mapped ID's value; `device_online`/
  `device_offline` drive availability; the socket reconnects with backoff on drop, resuming from
  its last cursor. A **slow fallback poll (5 min)** is the only remaining poll (a full re-fetch),
  as belt-and-braces. (This replaces the SSE stream at `GET /events/stream`, withdrawn 2026-08-30
  — it never delivered a byte through Cloudflare.)
- **Actuation:** entity services (turn on/off, open/close, lock/unlock) write the ID directly —
  `PUT /devices/{serial}/ids/{idNumber}/value` — using the high/low convention above. There is no
  abstract capability-command endpoint any more; `momentaryOutput`/`delayedOutput` IDs (a pulse
  relay, common for a garage door opener) ignore the value sent and fire their configured pulse
  regardless, so the same call correctly handles both a sustained relay and a momentary one.
  Secure capabilities (Lock/GarageDoor) actuate with `confirm` (waits for a confirmed device
  reply).

## Install (HACS)
1. HACS → Integrations → ⋮ → **Custom repositories** → add `wkyle101/jwx-homeassistant`,
   category **Integration**.
2. Install **Justworx**, restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → **Justworx** → you'll be redirected to
   **log in to Justworx** (OAuth) and approve access. No API key to paste.

## Development / test
The mapping and event-apply cores have **no Home Assistant imports**, so they're unit-tested with
plain Python:

```sh
python -m unittest discover -s tests          # mapping + event-apply unit tests
```

An optional end-to-end test runs the mapping against a real Justworx account when you point it at
one; it skips cleanly when `JWX_TEST_BASE` is unset:

```sh
JWX_TEST_BASE=https://api.justworx.com/api/v2 JWX_TEST_KEY=<jwx_live_... key> \
  python -m unittest discover -s tests
```

To verify in Home Assistant, load the custom integration in a test instance → devices appear with
the mapped entities → a service call actuates a device → state updates over the WebSocket almost
immediately, or on the next poll at worst.

## Layout
```
custom_components/justworx/
  capability_map.py   capability -> HA mapping + state/actuation convention (pure, unit-tested)
  events.py           pure event-apply core (cloud_push, unit-tested)
  stream.py           holds the WebSocket open, feeds events to the coordinator
  api.py              async Justworx API client (aiohttp)
  coordinator.py      DataUpdateCoordinator (slow fallback poll) + apply_stream_event
  entity.py           base capability entity, identified by (serial, idNumber)
  switch.py light.py lock.py cover.py binary_sensor.py sensor.py
  config_flow.py             OAuth2 (PKCE) config flow
  application_credentials.py  bundled public PKCE client + AuthorizationServer
  __init__.py const.py manifest.json translations/
tests/                mapping + event-apply unit tests, live-account integration test
hacs.json
```

## Status
Works against the Justworx API (`https://api.justworx.com/api/v2`). Uses `cloud_push` via the
real-time WebSocket and maps the published capability taxonomy to Home Assistant entities.
Authentication is OAuth2 with a public PKCE client. Roadmap: publish to HACS, verify the on/off
polarity convention against real Lock/GarageDoor hardware, a PIN model for secure capabilities,
and the Thermostat/Dimmer/Fan platforms.
