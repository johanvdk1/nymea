"""Test the nymea config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.nymea.config_flow import (
    CannotConnect,
    InvalidHost,
    NymeaConfigFlow,
)
from custom_components.nymea.const import (
    CONF_WEBSOCKET_PORT,
    DEFAULT_RPC_PORT,
    DEFAULT_WS_PORT,
    DOMAIN,
)

MOCK_HOST = "192.168.2.179"
MOCK_PORTS = (DEFAULT_RPC_PORT, DEFAULT_WS_PORT)


# ---------------------------------------------------------------------------
# Manual setup (user + ports + link)
# ---------------------------------------------------------------------------


async def test_form_user(hass: HomeAssistant, mock_maveo_box) -> None:
    """Test the user step shows only the host field."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_form_user_to_ports(hass: HomeAssistant, mock_maveo_box) -> None:
    """Test that submitting the host moves to the ports step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "ports"


async def test_form_user_invalid_host(hass: HomeAssistant) -> None:
    """Test we handle an invalid host at the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "-invalid-host-"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {CONF_HOST: "cannot_connect"}


async def test_form_ports_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect at the ports step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result2["step_id"] == "ports"

    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        with patch("custom_components.nymea.config_flow.MaveoBox") as mock_box:
            mock_box.return_value.test_connection = AsyncMock(return_value=False)

            result3 = await hass.config_entries.flow.async_configure(
                result2["flow_id"],
                {CONF_PORT: DEFAULT_RPC_PORT, CONF_WEBSOCKET_PORT: DEFAULT_WS_PORT},
            )

    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "ports"
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_form_full_manual_flow(hass: HomeAssistant, mock_maveo_box) -> None:
    """Test the full manual setup flow: user → ports → link → entry created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"

    # Step 1: submit host
    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
    assert result2["step_id"] == "ports"

    # Step 2: confirm ports
    with patch(
        "custom_components.nymea.config_flow.MaveoBox",
        return_value=mock_maveo_box,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_PORT: DEFAULT_RPC_PORT, CONF_WEBSOCKET_PORT: DEFAULT_WS_PORT},
        )
    assert result3["step_id"] == "link"

    # Step 3: press button (link)
    with patch(
        "custom_components.nymea.config_flow.MaveoBox",
        return_value=mock_maveo_box,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {},
        )
    await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == f"nymea({MOCK_HOST})"
    assert result4["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_RPC_PORT,
        CONF_WEBSOCKET_PORT: DEFAULT_WS_PORT,
        CONF_TOKEN: "test_token_12345",
    }


# ---------------------------------------------------------------------------
# Zeroconf discovery
# ---------------------------------------------------------------------------


def _make_discovery_info(ws=False):
    """Create a zeroconf discovery info object."""
    return zeroconf.ZeroconfServiceInfo(
        ip_address=MOCK_HOST,
        ip_addresses=[MOCK_HOST],
        hostname="nymea-device.local.",
        name=f"nymea._{'ws' if ws else 'jsonrpc'}._tcp.local.",
        port=4445 if ws else 2223,
        type=f"_{'ws' if ws else 'jsonrpc'}._tcp.local.",
        properties={},
    )


async def test_zeroconf_discovery(hass: HomeAssistant, mock_maveo_box) -> None:
    """Test zeroconf discovery shows the zeroconf_confirm form with ports."""
    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        with patch(
            "custom_components.nymea.config_flow.MaveoBox",
            return_value=mock_maveo_box,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_ZEROCONF},
                data=_make_discovery_info(),
            )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {"host": MOCK_HOST}


async def test_zeroconf_confirm_step(hass: HomeAssistant, mock_maveo_box) -> None:
    """Test confirming zeroconf discovery moves to the link step."""
    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        with patch(
            "custom_components.nymea.config_flow.MaveoBox",
            return_value=mock_maveo_box,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_ZEROCONF},
                data=_make_discovery_info(),
            )

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_PORT: DEFAULT_RPC_PORT, CONF_WEBSOCKET_PORT: DEFAULT_WS_PORT},
            )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "link"


async def test_zeroconf_full_flow(hass: HomeAssistant, mock_maveo_box) -> None:
    """Test full zeroconf flow: discovery → confirm → link → entry created."""
    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        with patch(
            "custom_components.nymea.config_flow.MaveoBox",
            return_value=mock_maveo_box,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_ZEROCONF},
                data=_make_discovery_info(),
            )
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_PORT: DEFAULT_RPC_PORT, CONF_WEBSOCKET_PORT: DEFAULT_WS_PORT},
            )
            assert result2["step_id"] == "link"

            result3 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], {}
            )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_HOST] == MOCK_HOST
    assert result3["data"][CONF_PORT] == DEFAULT_RPC_PORT
    assert result3["data"][CONF_WEBSOCKET_PORT] == DEFAULT_WS_PORT
    assert result3["data"][CONF_TOKEN] == "test_token_12345"


async def test_zeroconf_websocket_ignored(hass: HomeAssistant) -> None:
    """Test that WebSocket zeroconf discoveries are ignored."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_make_discovery_info(ws=True),
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_zeroconf_cannot_connect(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts on connection failure."""
    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        with patch("custom_components.nymea.config_flow.MaveoBox") as mock_box:
            mock_box.return_value.test_connection = AsyncMock(return_value=False)

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_ZEROCONF},
                data=_make_discovery_info(),
            )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


# ---------------------------------------------------------------------------
# Reconfigure
# ---------------------------------------------------------------------------


async def test_reconfigure_shows_form(hass: HomeAssistant, mock_maveo_box) -> None:
    """Test reconfigure shows a pre-populated form."""
    # First create an entry
    entry = hass.config_entries.async_add(
        config_entries.ConfigEntry(
            version=1,
            domain=DOMAIN,
            title=f"nymea({MOCK_HOST})",
            data={
                CONF_HOST: MOCK_HOST,
                CONF_PORT: DEFAULT_RPC_PORT,
                CONF_WEBSOCKET_PORT: DEFAULT_WS_PORT,
                CONF_TOKEN: "test_token_12345",
            },
            source=config_entries.SOURCE_USER,
        )
    )

    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"] == {"host": MOCK_HOST}


async def test_reconfigure_without_repair(hass: HomeAssistant, mock_maveo_box) -> None:
    """Test reconfigure without re-pairing just updates ports."""
    entry = hass.config_entries.async_add(
        config_entries.ConfigEntry(
            version=1,
            domain=DOMAIN,
            title=f"nymea({MOCK_HOST})",
            data={
                CONF_HOST: MOCK_HOST,
                CONF_PORT: DEFAULT_RPC_PORT,
                CONF_WEBSOCKET_PORT: DEFAULT_WS_PORT,
                CONF_TOKEN: "test_token_12345",
            },
            source=config_entries.SOURCE_USER,
        )
    )

    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PORT: 2224,
                CONF_WEBSOCKET_PORT: 4446,
                "repair": False,
            },
        )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PORT] == 2224
    assert entry.data[CONF_WEBSOCKET_PORT] == 4446
    assert entry.data[CONF_TOKEN] == "test_token_12345"  # token unchanged


async def test_reconfigure_with_repair(hass: HomeAssistant, mock_maveo_box) -> None:
    """Test reconfigure with re-pair goes through the link step."""
    entry = hass.config_entries.async_add(
        config_entries.ConfigEntry(
            version=1,
            domain=DOMAIN,
            title=f"nymea({MOCK_HOST})",
            data={
                CONF_HOST: MOCK_HOST,
                CONF_PORT: DEFAULT_RPC_PORT,
                CONF_WEBSOCKET_PORT: DEFAULT_WS_PORT,
                CONF_TOKEN: "old_token",
            },
            source=config_entries.SOURCE_USER,
        )
    )

    with patch(
        "custom_components.nymea.config_flow._get_ports_from_xml",
        return_value=MOCK_PORTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PORT: DEFAULT_RPC_PORT,
                CONF_WEBSOCKET_PORT: DEFAULT_WS_PORT,
                "repair": True,
            },
        )

    # Should go to link step for button press
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "link"

    # Complete the link step
    with patch(
        "custom_components.nymea.config_flow.MaveoBox",
        return_value=mock_maveo_box,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {}
        )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_TOKEN] == "test_token_12345"  # new token
