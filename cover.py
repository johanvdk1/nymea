"""Support for nymea cover entities."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

if TYPE_CHECKING:
    from .maveo_stick import MaveoStick

from .maveo_stick import State

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add cover entities for passed config_entry in HA.

    Args:
        hass: Home Assistant instance.
        config_entry: Config entry for this integration.
        async_add_entities: Callback to add entities to HA.
    """
    maveoBox = config_entry.runtime_data
    async_add_entities(GarageDoor(stick) for stick in maveoBox.maveoSticks)


class GarageDoor(CoverEntity):
    """Representation of a GarageDoor."""

    device_class = CoverDeviceClass.GARAGE
    has_entity_name = True
    should_poll = False
    supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, maveoStick: MaveoStick) -> None:
        """Initialize the garage door."""
        self._maveoStick: MaveoStick = maveoStick
        self._attr_unique_id: str = f"{self._maveoStick.id}_cover"
        self._attr_name: str = self._maveoStick.name
        self._available: bool = True

        # Cache action type IDs and state type ID from already-known thing class data
        self.stateTypeIdState: str | None = None
        self._action_type_open: str | None = None
        self._action_type_close: str | None = None
        self._action_type_stop: str | None = None

        self._cache_type_ids()

    def _cache_type_ids(self) -> None:
        """Cache state and action type IDs from the thing class definition."""
        params: dict[str, Any] = {"thingClassIds": [self._maveoStick.thingclassid]}
        response = self._maveoStick.maveoBox.send_command(
            "Integrations.GetThingClasses", params
        )
        if not response:
            _LOGGER.error("Failed to get thing class for cover entity")
            return

        thing_classes = response.get("params", {}).get("thingClasses", [])
        if not thing_classes:
            _LOGGER.error("Thing class not found for cover entity")
            return

        thing_class = thing_classes[0]

        # Cache state type ID for "State"
        statetype_state = next(
            (st for st in thing_class.get("stateTypes", []) if st["displayName"] == "State"),
            None,
        )
        if statetype_state:
            self.stateTypeIdState = statetype_state["id"]

        # Cache action type IDs for Open, Close, Stop
        for action in thing_class.get("actionTypes", []):
            name = action.get("displayName", "")
            if name == "Open":
                self._action_type_open = action["id"]
            elif name == "Close":
                self._action_type_close = action["id"]
            elif name == "Stop":
                self._action_type_stop = action["id"]

        _LOGGER.debug(
            "Cached type IDs — state: %s, open: %s, close: %s, stop: %s",
            self.stateTypeIdState,
            self._action_type_open,
            self._action_type_close,
            self._action_type_stop,
        )

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await self.async_update()
        self._maveoStick.register_callback(self.async_write_ha_state)

    async def async_update(self) -> None:
        """Fetch initial state (called once before notification listener starts)."""
        if not self.stateTypeIdState:
            return
        params: dict[str, str] = {
            "thingId": self._maveoStick.id,
            "stateTypeId": self.stateTypeIdState,
        }
        try:
            value: str = self._maveoStick.maveoBox.send_command(
                "Integrations.GetStateValue", params
            )["params"]["value"]
            self._maveoStick.state = State[value]
            self._available = True
        except Exception as ex:
            self._available = False
            _LOGGER.error(
                "Error fetching initial state for %s: %s", self._maveoStick.id, ex
            )

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._maveoStick.remove_callback(self.async_write_ha_state)

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._maveoStick.id)},
            "name": "maveo Stick",
            "model": "maveo Stick",
            "sw_version": self._maveoStick.firmware_version,
            "manufacturer": "Marantec",
        }

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return (
            self._maveoStick.state == State.closed
        )

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._maveoStick.state == State.closing

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._maveoStick.state == State.opening

    @property
    def available(self) -> bool:
        """Return the availability of the cover."""
        return self._available

    def _execute_action(self, action_type_id: str | None) -> None:
        """Execute an action on the garage door."""
        if not action_type_id:
            _LOGGER.error("Action type ID not available")
            return
        params: dict[str, str] = {
            "actionTypeId": action_type_id,
            "thingId": self._maveoStick.id,
        }
        self._maveoStick.maveoBox.send_command("Integrations.ExecuteAction", params)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._execute_action(self._action_type_open)
        self._maveoStick.state = State.opening
        await self._maveoStick.publish_updates()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._execute_action(self._action_type_close)
        self._maveoStick.state = State.closing
        await self._maveoStick.publish_updates()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._execute_action(self._action_type_stop)
        self._maveoStick.state = State.unknown
        await self._maveoStick.publish_updates()
