"""Config flow for the SesameOS 3 integration."""

from __future__ import annotations

import base64
import logging
from typing import Any
from urllib.parse import parse_qs, urlparse

import voluptuous as vol

from sesameos3client import SesameClient

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.components import bluetooth

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_MAC): str,
        vol.Required("device_secret"): str,
    }
)

STEP_QR_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("qr_code"): str,
    }
)

def parse_qr_code(qr_code: str) -> dict[str, Any]:
    """Parse Sesame QR code and extract device information."""
    if not qr_code.startswith("ssm://UI?"):
        raise ValueError("Invalid QR code format")
    
    parsed = urlparse(qr_code)
    params = parse_qs(parsed.query)
    
    if "sk" not in params:
        raise ValueError("Missing device secret in QR code")
    
    device_secret_b64 = params["sk"][0]
    # Add padding if needed for base64 decoding
    padding_needed = 4 - (len(device_secret_b64) % 4)
    if padding_needed != 4:
        device_secret_b64 += "=" * padding_needed
    device_sk = base64.b64decode(device_secret_b64)
    
    if len(device_sk) < 39:
        raise ValueError("Invalid device secret length")
    
    product_version = device_sk[0]
    if product_version != 0x5:
        raise ValueError(f"Unsupported product version: {product_version}")
    
    device_secret = device_sk[1:17]
    device_uuid = device_sk[23:39]
    
    device_name = "Sesame 5"
    if "n" in params:
        device_name = params["n"][0]
    
    result = {
        "device_secret": base64.b64encode(device_secret).decode(),
        "device_uuid": device_uuid.hex(),
        "device_name": device_name,
        "product_version": product_version,
    }
    
    return result


def _matches_target_uuid(service_info, target_uuid: str) -> bool:
    """Check if service info matches target UUID by extracting Sesame device information."""
    if not service_info.manufacturer_data:
        return False
        
    # Look for CANDY HOUSE manufacturer data (0x055A)
    candy_house_data = service_info.manufacturer_data.get(0x055A)
    if not candy_house_data or len(candy_house_data) < 19:
        return False
        
    # Extract UUID from manufacturer data (bytes 3-18, after product type + status)
    device_uuid = candy_house_data[3:19].hex()
    return device_uuid.lower() == target_uuid.lower()


async def find_device_by_uuid(hass: HomeAssistant, target_uuid: str) -> str | None:
    """Find MAC address of Sesame device by UUID from Bluetooth scan."""
    try:
        # Get all discovered service info with CANDY HOUSE manufacturer ID
        service_infos = bluetooth.async_discovered_service_info(hass, connectable=True)
        
        for service_info in service_infos:
            if _matches_target_uuid(service_info, target_uuid):
                return service_info.address
                
        # If not found in current discoveries, try to wait for new advertisements
        _LOGGER.debug("Device not found in current discoveries, waiting for advertisements...")
        
        # Wait for matching advertisement for up to 10 seconds
        service_info = await bluetooth.async_process_advertisements(
            hass,
            lambda si: _matches_target_uuid(si, target_uuid),
            {"connectable": True},
            bluetooth.BluetoothScanningMode.ACTIVE,
            10
        )
        
        if service_info:
            return service_info.address
                    
    except Exception as e:
        _LOGGER.error("Error scanning for Bluetooth devices: %s", e)
        
    return None

async def connection_trial(hass: HomeAssistant, data: dict[str, Any]) -> None:
    client = SesameClient(data[CONF_MAC], base64.b64decode(data["device_secret"]))
    await client.connect()
    await client.disconnect()


class SesameConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SesameOS 3."""

    VERSION = 1
    
    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._qr_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - choose setup method."""
        if user_input is not None:
            if user_input["setup_method"] == "qr_code":
                return await self.async_step_qr_code()
            else:
                return await self.async_step_device_info()

        setup_schema = vol.Schema({
            vol.Required("setup_method", default="qr_code"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["qr_code", "manual"],
                    translation_key="setup_method",
                )
            )
        })

        return self.async_show_form(
            step_id="user", data_schema=setup_schema
        )

    async def async_step_qr_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle QR code setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                qr_data = parse_qr_code(user_input["qr_code"])
                self._qr_data = qr_data
                
                # Try to find device by UUID if available
                if "device_uuid" in qr_data:
                    mac_address = await find_device_by_uuid(self.hass, qr_data["device_uuid"])
                    if mac_address:
                        # Auto-fill MAC address and go to device info
                        return await self.async_step_device_info({
                            "_qr_prefill": True,
                            CONF_NAME: qr_data["device_name"],
                            "device_secret": qr_data["device_secret"],
                            CONF_MAC: mac_address,
                        })
                    else:
                        # Show device discovery step
                        return await self.async_step_device_discovery()
                else:
                    # No UUID in QR code, go to manual device info entry
                    return await self.async_step_device_info({
                        "_qr_prefill": True,
                        CONF_NAME: qr_data["device_name"],
                        "device_secret": qr_data["device_secret"],
                    })
                    
            except ValueError as e:
                errors["base"] = "invalid_qr_code"
                _LOGGER.error("Invalid QR code: %s", e)
            except Exception:
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected error parsing QR code")

        return self.async_show_form(
            step_id="qr_code", data_schema=STEP_QR_DATA_SCHEMA, errors=errors
        )

    async def async_step_device_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device discovery step when auto-discovery failed."""
        errors: dict[str, str] = {}
        qr_data = self._qr_data
        
        if user_input is not None:
            if user_input.get("action") == "retry":
                # Retry scanning for device
                if "device_uuid" in qr_data:
                    mac_address = await find_device_by_uuid(self.hass, qr_data["device_uuid"])
                    if mac_address:
                        # Found device, go to device info with pre-filled data
                        return await self.async_step_device_info({
                            "_qr_prefill": True,
                            CONF_NAME: qr_data["device_name"],
                            "device_secret": qr_data["device_secret"],
                            CONF_MAC: mac_address,
                        })
                    else:
                        errors["base"] = "device_not_found"
                        
            else:
                # Manual entry selected, go to device info
                return await self.async_step_device_info({
                    "_qr_prefill": True,
                    CONF_NAME: qr_data["device_name"],
                    "device_secret": qr_data["device_secret"],
                })

        discovery_schema = vol.Schema({
            vol.Required("action", default="retry"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["retry", "manual"],
                    translation_key="action",
                )
            )
        })

        return self.async_show_form(
            step_id="device_discovery",
            data_schema=discovery_schema,
            errors=errors,
            description_placeholders={
                "device_name": qr_data.get("device_name", "Unknown"),
                "device_uuid": qr_data.get("device_uuid", "Unknown"),
            }
        )

    async def async_step_device_info(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device info setup step."""
        errors: dict[str, str] = {}
        
        # Check if this is a QR code prefill call
        qr_prefill = user_input and user_input.pop("_qr_prefill", False)
        
        if user_input is not None and not qr_prefill:
            try:
                await connection_trial(self.hass, user_input)
            except:
                errors["base"] = "cannot_connect"
                _LOGGER.exception("Error connecting to SesameOS 3")
            else:
                title = user_input[CONF_NAME]
                del user_input[CONF_NAME]
                return self.async_create_entry(title=title, data=user_input)

        # Set up default values (from QR code if prefilled, otherwise empty)
        defaults = {}
        if qr_prefill and user_input:
            defaults = {
                CONF_NAME: user_input.get(CONF_NAME, ""),
                CONF_MAC: user_input.get(CONF_MAC, ""),
                "device_secret": user_input.get("device_secret", ""),
            }

        # Create schema with defaults
        data_schema = vol.Schema({
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
            vol.Required(CONF_MAC, default=defaults.get(CONF_MAC, "")): str,
            vol.Required("device_secret", default=defaults.get("device_secret", "")): str,
        })

        return self.async_show_form(
            step_id="device_info", data_schema=data_schema, errors=errors
        )