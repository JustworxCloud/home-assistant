"""Application Credentials for Justworx OAuth2, using a PUBLIC PKCE client.

The integration bundles a public `client_id` (registered in __init__.async_setup) and uses PKCE, so
no client secret is shipped — the correct model for a distributed (HACS) integration. `async_setup`
imports the credential automatically, so the user never has to register their own OAuth app.
"""

from __future__ import annotations

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    return AuthorizationServer(authorize_url=OAUTH2_AUTHORIZE, token_url=OAUTH2_TOKEN)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """PKCE public client — no secret; the token endpoint auth method is 'none'."""
    return config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce(
        hass,
        auth_domain,
        credential.client_id,
        OAUTH2_AUTHORIZE,
        OAUTH2_TOKEN,
        client_secret=credential.client_secret or "",
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    return {"oauth_url": OAUTH2_AUTHORIZE}
