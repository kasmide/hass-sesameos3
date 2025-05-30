"""Config flow for the SesameOS 3 integration."""

from __future__ import annotations

import base64
import logging
from typing import Any

import voluptuous as vol

from sesameos3client import SesameClient, Event

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_MAC): str,
        vol.Required("private_key"): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def connection_trial(hass: HomeAssistant, data: dict[str, Any]) -> None:
    client = SesameClient(data[CONF_MAC], base64.b64decode(data["private_key"]))
    await client.connect()


class SesameConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SesameOS 3."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await connection_trial(self.hass, user_input)
            except:
                errors["base"] = "cannot_connect"
                _LOGGER.exception("Error connecting to SesameOS 3")
            else:
                title = user_input[CONF_NAME]
                del user_input[CONF_NAME]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )