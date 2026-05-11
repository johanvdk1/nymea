"""Config flow for maveo integration."""

from __future__ import annotations

import logging
import re
from typing import Any
import xml.etree.ElementTree as ET

import aiohttp
from homeassistant import config_entries, exceptions
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
import voluptuous as vol

from .const import CONF_WEBSOCKET_PORT, DOMAIN  # pylint:disable=unused-import
from .maveo_box import MaveoBox

_LOGGER = logging.getLogger(__name__)

CONF_REPAIR = "repair"
DEFAULT_RPC_PORT = 2223
DEFAULT_WS_PORT = 4445


async def _get_ports_from_xml(host: str) -> tuple[int, int]:
    """Fetch JSON-RPC and WebSocket ports from server.xml on port 80."""
    rpc_port = DEFAULT_RPC_PORT
    ws_port = DEFAULT_WS_PORT

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://{host}/server.xml",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                content = await resp.text()

        root = ET.fromstring(content)
        ns = {"upnp": "urn:schemas-upnp-org:device-1-0"}

        for service in root.findall(".//upnp:service", ns):
            stype = service.find("upnp:serviceType", ns)
            scpd = service.find("upnp:SCPDURL", ns)
            if stype is None or scpd is None:
                continue
            port = int(scpd.text.split(":")[-1])
            if "service:ws:1" in stype.text:
                ws_port = port
            elif "service:nymeas:1" in stype.text:
                rpc_port = port

    except Exception as err:
        _LOGGER.warning("Could not fetch server.xml, using defaults: %s", err)

    _LOGGER.info("Ports from server.xml — RPC: %s, WS: %s", rpc_port, ws_port)
    return rpc_port, ws_port


def _ports_schema(rpc_port: int = DEFAULT_RPC_PORT, ws_port: int = DEFAULT_WS_PORT) -> vol.Schema:
    """Build a schema for the ports confirmation form."""
    return vol.Schema(
        {
            vol.Required(CONF_PORT, default=rpc_port): int,
            vol.Required(CONF_WEBSOCKET_PORT, default=ws_port): int,
        }
    )


def _reconfigure_schema(rpc_port: int, ws_port: int) -> vol.Schema:
    """Build a schema for the reconfigure form including re-pair checkbox."""
    return vol.Schema(
        {
            vol.Required(CONF_PORT, default=rpc_port): int,
            vol.Required(CONF_WEBSOCKET_PORT, default=ws_port): int,
            vol.Required(CONF_REPAIR, default=False): bool,
        }
    )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Args:
        hass: Home Assistant instance.
        data: User input data with host and port.

    Raises:
        InvalidHost: If the hostname format is invalid.
        CannotConnect: If connection to the device fails.
    """
    pattern: str = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$"
    if not re.match(pattern, data[CONF_HOST]):
        raise InvalidHost

    hub: MaveoBox = MaveoBox(hass, data[CONF_HOST], data[CONF_PORT])
    success: bool = await hub.test_connection()
    if not success:
        raise CannotConnect


class NymeaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a nymea config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the nymea config flow."""
        self.data: dict[str, Any] = {}
        self.discovery_info: zeroconf.ZeroconfServiceInfo | None = None

    # ------------------------------------------------------------------
    # Auto-discovery path (mDNS/zeroconf)
    # ------------------------------------------------------------------

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovery: %s", discovery_info)

        # We only want to handle JSON-RPC TCP discoveries, not WebSocket.
        if "_ws._tcp" in discovery_info.type:
            _LOGGER.debug("Ignoring WebSocket discovery, we need JSON-RPC TCP")
            return self.async_abort(reason="not_supported")

        host = discovery_info.host

        # Check if already configured.
        await self.async_set_unique_id(discovery_info.hostname.replace(".local.", ""))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.discovery_info = discovery_info

        # Fetch ports from server.xml.
        port, websocket_port = await _get_ports_from_xml(host)

        # Validate connection.
        try:
            await validate_input(self.hass, {CONF_HOST: host, CONF_PORT: port})
        except (CannotConnect, InvalidHost):
            return self.async_abort(reason="cannot_connect")

        self.data = {CONF_HOST: host, CONF_PORT: port, CONF_WEBSOCKET_PORT: websocket_port}
        _LOGGER.info("Discovered nymea device at %s:%s", host, port)

        self.context["title_placeholders"] = {"name": f"nymea ({host})"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show pre-populated editable form for the user to confirm discovered ports."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                data_schema=_ports_schema(
                    rpc_port=self.data.get(CONF_PORT, DEFAULT_RPC_PORT),
                    ws_port=self.data.get(CONF_WEBSOCKET_PORT, DEFAULT_WS_PORT),
                ),
                description_placeholders={"host": self.data.get(CONF_HOST, "unknown")},
            )

        # User confirmed (possibly with edits) — update stored data.
        self.data.update(user_input)
        return await self.async_step_link()

    # ------------------------------------------------------------------
    # Manual setup path
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1 of manual setup: enter the host address."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            pattern: str = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$"
            if not re.match(pattern, host):
                errors[CONF_HOST] = "cannot_connect"
            else:
                self.data[CONF_HOST] = host
                return await self.async_step_ports()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_ports(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2 of manual setup: confirm ports pre-populated from server.xml."""
        host = self.data[CONF_HOST]
        errors = {}

        if user_input is None:
            rpc_port, ws_port = await _get_ports_from_xml(host)
            return self.async_show_form(
                step_id="ports",
                data_schema=_ports_schema(rpc_port=rpc_port, ws_port=ws_port),
                description_placeholders={"host": host},
            )

        # Validate connection with the confirmed ports.
        try:
            await validate_input(self.hass, {CONF_HOST: host, **user_input})
        except CannotConnect:
            errors["base"] = "cannot_connect"
            rpc_port, ws_port = await _get_ports_from_xml(host)
            return self.async_show_form(
                step_id="ports",
                data_schema=_ports_schema(rpc_port=rpc_port, ws_port=ws_port),
                errors=errors,
                description_placeholders={"host": host},
            )

        self.data.update(user_input)
        return await self.async_step_link()

    # ------------------------------------------------------------------
    # Shared link (button press) step
    # ------------------------------------------------------------------

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to press the button on the maveo box to pair."""
        if user_input is None:
            _LOGGER.debug("Showing link form")
            return self.async_show_form(step_id="link")

        _LOGGER.info(
            "Starting pairing process for %s:%s",
            self.data.get(CONF_HOST),
            self.data.get(CONF_PORT),
        )

        if not self.data or CONF_HOST not in self.data:
            _LOGGER.error("Configuration data missing in link step: %s", self.data)
            return self.async_abort(reason="unknown")

        box: MaveoBox = MaveoBox(
            self.hass,
            self.data[CONF_HOST],
            self.data[CONF_PORT],
            websocket_port=self.data.get(CONF_WEBSOCKET_PORT, DEFAULT_WS_PORT),
        )
        token: str | None = await box.init_connection()
        self.data[CONF_TOKEN] = token

        return self.async_create_entry(
            title=f"nymea({self.data[CONF_HOST]})", data=self.data
        )

    # ------------------------------------------------------------------
    # Reconfigure path
    # ------------------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to reconfigure ports and optionally re-pair."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        current_host = entry.data.get(CONF_HOST, "")

        if user_input is None:
            # Pre-populate from server.xml.
            rpc_port, ws_port = await _get_ports_from_xml(current_host)
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=_reconfigure_schema(rpc_port=rpc_port, ws_port=ws_port),
                description_placeholders={"host": current_host},
            )

        repair = user_input.pop(CONF_REPAIR, False)

        # Keep existing host and token, update ports.
        self.data = {**entry.data, **user_input}

        if repair:
            # Go through button press flow to get a new token.
            return await self.async_step_link()

        # Just update the config entry and reload.
        return self.async_update_reload_and_abort(
            entry,
            data=self.data,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
