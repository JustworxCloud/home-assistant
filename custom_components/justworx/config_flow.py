"""Config flow — OAuth2 (account-linked). No API key: the user logs in to Justworx."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JustworxApi
from .const import DEFAULT_BASE_URL, DOMAIN, SCOPES


class JustworxOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle the Justworx OAuth2 authorization-code (PKCE) flow."""

    DOMAIN = DOMAIN
    VERSION = 2  # was 1 (API-key entries); OAuth entries store a token, not a key.

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Scopes requested at authorization."""
        return {"scope": " ".join(SCOPES)}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Called once we hold a token — resolve the account and create the entry."""
        token = data["token"]["access_token"]

        async def _token() -> str:
            return token

        api = JustworxApi(async_get_clientsession(self.hass), DEFAULT_BASE_URL, _token)
        me = await api.whoami()

        await self.async_set_unique_id(me.get("accountId"))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Justworx", data=data)
