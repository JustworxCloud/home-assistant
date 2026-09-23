"""Constants for the Justworx integration."""

DOMAIN = "justworx"

# The Justworx API. Fixed (prod) — no longer a user-entered field; auth is OAuth2 now.
DEFAULT_BASE_URL = "https://api.justworx.com/api/v2"

# The real-time WebSocket at wss://.../api/v2/stream. Same host as DEFAULT_BASE_URL; spelled out
# separately because it is a ws:// URL, not an HTTP path under DEFAULT_BASE_URL.
STREAM_URL = "wss://api.justworx.com/api/v2/stream"

# Real-time state comes from the WebSocket push (cloud_push) -- preferred transport, ~110ms.
# The coordinator keeps only a SLOW fallback poll (a full re-fetch, no device round-trip) as
# belt-and-braces if the socket drops. This used to be the SSE stream at GET /events/stream,
# withdrawn 2026-08-30 (it never delivered a byte through Cloudflare); the WebSocket/long-poll
# pair replaced it.
STREAM_FALLBACK_INTERVAL = 300  # seconds

MANUFACTURER = "Justworx"

# --- OAuth2 — account-linked, no user API key ---
# Public PKCE client: the integration ships the (non-secret) client_id; the user just logs in.
# A confidential client's secret is deliberately NOT bundled (it can't be, in a public integration).
OAUTH2_AUTHORIZE = "https://oauth.justworx.com/oauth2/auth"
OAUTH2_TOKEN = "https://oauth.justworx.com/oauth2/token"
CLIENT_ID = "9e5cb593-0c99-4ed8-a6eb-7c8ff8942825"
SCOPES = ["openid", "offline_access", "devices:read", "devices:command", "events:read"]
