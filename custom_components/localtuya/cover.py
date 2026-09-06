"""Platform to locally control Tuya-based cover devices."""

import asyncio
import logging
import time
from functools import partial

import voluptuous as vol
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    CoverEntity,
    CoverEntityFeature,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_COMMANDS_SET,
    CONF_CURRENT_POSITION_DP,
    CONF_POSITION_INVERTED,
    CONF_POSITIONING_MODE,
    CONF_SET_POSITION_DP,
    CONF_SPAN_TIME,
    CONF_COVER_COMMAND_VALUES,
    CONF_COVER_ACTION_DP,
    CONF_COVER_ACTION_VALUES,
    CONF_COVER_OPEN_DP,
    CONF_COVER_OPEN_VALUES,
    CONF_SET_POSITION_MIN,
    CONF_SET_POSITION_MAX,
    CONF_SET_POSITION_STEP,
    CONF_SET_POSITION_INVERTED,
    CONF_CURRENT_POSITION_MIN,
    CONF_CURRENT_POSITION_MAX,
    CONF_CURRENT_POSITION_INVERTED,
    CONF_TILT_POSITION_DP,
    CONF_TILT_POSITION_MIN,
    CONF_TILT_POSITION_MAX,
    CONF_TILT_POSITION_STEP,
    CONF_TILT_POSITION_INVERTED,
)

_LOGGER = logging.getLogger(__name__)

COVER_ONOFF_CMDS = "on_off_stop"
COVER_OPENCLOSE_CMDS = "open_close_stop"
COVER_FZZZ_CMDS = "fz_zz_stop"
COVER_12_CMDS = "1_2_3"

COVER_MODE_NONE = "none"
COVER_MODE_POSITION = "position"
COVER_MODE_TIMED = "timed"

COVER_TIMEOUT_TOLERANCE = 3.0

DEFAULT_COMMANDS_SET = COVER_ONOFF_CMDS
DEFAULT_POSITIONING_MODE = COVER_MODE_NONE
DEFAULT_SPAN_TIME = 25.0


def _valid_scalar_map(value, allowed_keys):
    """Validate a catalog-provided semantic -> raw scalar map."""
    if not isinstance(value, dict):
        return {}
    result = {}
    raw_values = []
    for key, raw in value.items():
        if key not in allowed_keys or not isinstance(raw, (str, int, float, bool)):
            return {}
        if key in result or any(raw == previous for previous in raw_values):
            return {}
        result[key] = raw
        raw_values.append(raw)
    return result


def _number(value, default):
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _range_to_percent(value, minimum, maximum, inverted=False):
    """Convert one native cover position to an HA percentage."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    minimum = _number(minimum, 0.0)
    maximum = _number(maximum, 100.0)
    if maximum <= minimum:
        return None
    percentage = (float(value) - minimum) * 100.0 / (maximum - minimum)
    percentage = min(max(percentage, 0.0), 100.0)
    if inverted:
        percentage = 100.0 - percentage
    return round(percentage)


def _percent_to_range(percentage, minimum, maximum, step=1.0, inverted=False):
    """Convert an HA percentage to an exact native cover range value."""
    minimum = _number(minimum, 0.0)
    maximum = _number(maximum, 100.0)
    step = _number(step, 1.0)
    if maximum <= minimum or step <= 0:
        return None
    percentage = min(max(float(percentage), 0.0), 100.0)
    if inverted:
        percentage = 100.0 - percentage
    raw = minimum + (maximum - minimum) * percentage / 100.0
    raw = minimum + round((raw - minimum) / step) * step
    raw = min(max(raw, minimum), maximum)
    return int(raw) if float(raw).is_integer() else raw


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_COMMANDS_SET): vol.In(
            [
                COVER_ONOFF_CMDS,
                COVER_OPENCLOSE_CMDS,
                COVER_FZZZ_CMDS,
                COVER_12_CMDS,
            ]
        ),
        vol.Optional(
            CONF_POSITIONING_MODE,
            default=DEFAULT_POSITIONING_MODE,
        ): vol.In(
            [
                COVER_MODE_NONE,
                COVER_MODE_POSITION,
                COVER_MODE_TIMED,
            ]
        ),
        vol.Optional(CONF_CURRENT_POSITION_DP): vol.In(dps),
        vol.Optional(CONF_SET_POSITION_DP): vol.In(dps),
        vol.Optional(CONF_POSITION_INVERTED, default=False): bool,
        vol.Optional(
            CONF_SPAN_TIME,
            default=DEFAULT_SPAN_TIME,
        ): vol.All(
            vol.Coerce(float),
            vol.Range(min=1.0, max=300.0),
        ),
    }


class LocaltuyaCover(LocalTuyaEntity, CoverEntity):
    """Representation of a Tuya cover."""

    def __init__(
        self,
        device,
        config_entry,
        switchid,
        **kwargs,
    ):
        """Initialize the Tuya cover."""
        super().__init__(
            device,
            config_entry,
            switchid,
            _LOGGER,
            **kwargs,
        )

        commands_set = self._config.get(
            CONF_COMMANDS_SET,
            DEFAULT_COMMANDS_SET,
        )

        commands = commands_set.split("_")

        if len(commands) != 3:
            raise ValueError(
                f"Invalid cover commands set: {commands_set}"
            )

        self._open_cmd, self._close_cmd, self._stop_cmd = commands
        catalog_commands_configured = CONF_COVER_COMMAND_VALUES in self._config
        catalog_commands = _valid_scalar_map(
            self._config.get(CONF_COVER_COMMAND_VALUES),
            {"open", "close", "stop"},
        )
        if catalog_commands_configured:
            # An explicitly empty catalog map means this cover has no command
            # DP and must use its set-position DP for open/close instead of
            # falling back to the legacy on/off/stop command set.
            self._command_values = catalog_commands
            self._open_cmd = catalog_commands.get("open")
            self._close_cmd = catalog_commands.get("close")
            self._stop_cmd = catalog_commands.get("stop")
        else:
            self._command_values = {
                "open": self._open_cmd,
                "close": self._close_cmd,
                "stop": self._stop_cmd,
            }

        self._action_values = _valid_scalar_map(
            self._config.get(CONF_COVER_ACTION_VALUES),
            {"opening", "closing", "opened", "closed"},
        )
        self._open_values = _valid_scalar_map(
            self._config.get(CONF_COVER_OPEN_VALUES),
            {"open", "closed"},
        )
        self._semantic_state = None
        self._attr_current_cover_tilt_position = None

        self._positioning_mode = self._config.get(
            CONF_POSITIONING_MODE,
            DEFAULT_POSITIONING_MODE,
        )

        self._span_time = float(
            self._config.get(
                CONF_SPAN_TIME,
                DEFAULT_SPAN_TIME,
            )
        )

        self._position_inverted = bool(
            self._config.get(CONF_POSITION_INVERTED, False)
        )

        self._timer_start = time.monotonic()

        self._state = self._stop_cmd
        self._previous_state = self._state

        self._current_cover_position = (
            None
            if self._positioning_mode == COVER_MODE_NONE
            else 0
        )

        self._stop_task: asyncio.Task | None = None

        features = CoverEntityFeature(0)
        if self._command_values.get("open") is not None or self.has_config(CONF_SET_POSITION_DP):
            features |= CoverEntityFeature.OPEN
        if self._command_values.get("close") is not None or self.has_config(CONF_SET_POSITION_DP):
            features |= CoverEntityFeature.CLOSE
        if self._command_values.get("stop") is not None:
            features |= CoverEntityFeature.STOP
        if self._positioning_mode != COVER_MODE_NONE and self.has_config(CONF_SET_POSITION_DP):
            features |= CoverEntityFeature.SET_POSITION
        if self.has_config(CONF_TILT_POSITION_DP):
            features |= CoverEntityFeature.SET_TILT_POSITION

        self._attr_supported_features = features

    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        return self._current_cover_position

    @property
    def current_cover_tilt_position(self) -> int | None:
        return self._attr_current_cover_tilt_position

    @property
    def is_opening(self) -> bool | None:
        """Return whether the cover is opening."""
        if self._semantic_state is not None:
            return self._semantic_state == "opening"
        return self._state == self._open_cmd if self._open_cmd is not None else None

    @property
    def is_closing(self) -> bool | None:
        """Return whether the cover is closing."""
        if self._semantic_state is not None:
            return self._semantic_state == "closing"
        return self._state == self._close_cmd if self._close_cmd is not None else None

    @property
    def is_closed(self) -> bool | None:
        """Return whether the cover is fully closed."""
        if self._semantic_state == "closed":
            return True
        if self._semantic_state in {"opened", "opening", "closing"}:
            return False
        if self._current_cover_position is not None:
            return self._current_cover_position <= 0
        return None

    def _cancel_stop_task(self) -> None:
        """Cancel any previously scheduled automatic stop."""
        task = self._stop_task

        if task is not None and not task.done():
            task.cancel()

        self._stop_task = None

    def _stop_task_done(self, task) -> None:
        """Clear the stop task once it has completed."""
        if self._stop_task is task:
            self._stop_task = None

    def _schedule_stop(self, delay: float) -> None:
        """Schedule one automatic stop, replacing any old timer."""
        self._cancel_stop_task()

        task = self.hass.async_create_task(
            self._async_stop_after_timeout(delay),
            name=f"LocalTuya cover stop {self.entity_id}",
        )

        self._stop_task = task
        task.add_done_callback(self._stop_task_done)

    async def _async_stop_after_timeout(self, delay: float) -> None:
        """Stop the cover after the requested movement interval."""
        await asyncio.sleep(max(delay, 0.0))
        await self._async_send_stop()

    async def _async_send_stop(self) -> None:
        """Send the physical stop command without touching timer state."""
        self.debug(
            "Launching command %s to cover",
            self._stop_cmd,
        )

        if self._stop_cmd is None:
            return
        await self._device.set_dp(
            self._stop_cmd,
            self._dp_id,
        )

    async def _async_start_movement(self, command) -> None:
        """Start a new movement and invalidate any old stop timer."""
        self._cancel_stop_task()

        self.debug(
            "Launching command %s to cover",
            command,
        )

        if command is None:
            return
        await self._device.set_dp(
            command,
            self._dp_id,
        )

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        requested = int(kwargs[ATTR_POSITION])
        requested = min(max(requested, 0), 100)

        self.debug("Setting cover position: %s", requested)

        if self._positioning_mode == COVER_MODE_TIMED:
            current = self.current_cover_position

            if current is None:
                self.warning(
                    "Cannot use timed positioning without a known position"
                )
                return

            if requested == current:
                return

            delay = (
                abs(requested - current)
                / 100.0
                * self._span_time
            )

            command = (
                self._open_cmd
                if requested > current
                else self._close_cmd
            )

            await self._async_start_movement(command)
            self._schedule_stop(delay)
            return

        if self._positioning_mode == COVER_MODE_POSITION:
            self._cancel_stop_task()

            converted = _percent_to_range(
                requested,
                self._config.get(CONF_SET_POSITION_MIN, 0),
                self._config.get(CONF_SET_POSITION_MAX, 100),
                self._config.get(CONF_SET_POSITION_STEP, 1),
                bool(self._config.get(
                    CONF_SET_POSITION_INVERTED, self._position_inverted
                )),
            )

            if not self.has_config(CONF_SET_POSITION_DP) or converted is None:
                self.warning(
                    "Positioning mode selected without a set-position DP"
                )
                return

            await self._device.set_dp(
                converted,
                self._config[CONF_SET_POSITION_DP],
            )

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        if self._open_cmd is not None:
            await self._async_start_movement(self._open_cmd)
        elif self.has_config(CONF_SET_POSITION_DP):
            await self.async_set_cover_position(**{ATTR_POSITION: 100})
        else:
            return

        if self._positioning_mode == COVER_MODE_TIMED:
            self._schedule_stop(
                self._span_time + COVER_TIMEOUT_TOLERANCE
            )

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        if self._close_cmd is not None:
            await self._async_start_movement(self._close_cmd)
        elif self.has_config(CONF_SET_POSITION_DP):
            await self.async_set_cover_position(**{ATTR_POSITION: 0})
        else:
            return

        if self._positioning_mode == COVER_MODE_TIMED:
            self._schedule_stop(
                self._span_time + COVER_TIMEOUT_TOLERANCE
            )

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific percentage."""
        dp = self._config.get(CONF_TILT_POSITION_DP)
        if dp is None or ATTR_TILT_POSITION not in kwargs:
            return
        raw = _percent_to_range(
            kwargs[ATTR_TILT_POSITION],
            self._config.get(CONF_TILT_POSITION_MIN, 0),
            self._config.get(CONF_TILT_POSITION_MAX, 100),
            self._config.get(CONF_TILT_POSITION_STEP, 1),
            bool(self._config.get(CONF_TILT_POSITION_INVERTED, False)),
        )
        if raw is not None:
            await self._device.set_dp(raw, dp)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._cancel_stop_task()
        await self._async_send_stop()

    async def async_will_remove_from_hass(self):
        """Clean up delayed movement tasks when the entity unloads."""
        self._cancel_stop_task()
        await super().async_will_remove_from_hass()

    def status_restored(self, stored_state):
        """Restore the last stored cover status."""
        super().status_restored(stored_state)

        if self._positioning_mode != COVER_MODE_TIMED:
            return

        stored_pos = stored_state.attributes.get(
            "current_position"
        )

        if stored_pos is None:
            return

        try:
            stored_pos = int(stored_pos)
        except (TypeError, ValueError):
            return

        self._current_cover_position = min(
            max(stored_pos, 0),
            100,
        )

        self.debug(
            "Restored cover position %s",
            self._current_cover_position,
        )

    def status_updated(self):
        """Update the cover from the latest Tuya status."""
        self._previous_state = self._state
        raw_state = self.dps(self._dp_id)

        if raw_state is not None:
            self._state = raw_state

        if isinstance(self._state, str) and self._state.isupper():
            self._open_cmd = self._open_cmd.upper()
            self._close_cmd = self._close_cmd.upper()
            self._stop_cmd = self._stop_cmd.upper()

        if self.has_config(CONF_CURRENT_POSITION_DP):
            raw_position = self.dps_conf(CONF_CURRENT_POSITION_DP)
            position = _range_to_percent(
                raw_position,
                self._config.get(CONF_CURRENT_POSITION_MIN, 0),
                self._config.get(CONF_CURRENT_POSITION_MAX, 100),
                bool(self._config.get(
                    CONF_CURRENT_POSITION_INVERTED, self._position_inverted
                )),
            )
            if position is not None:
                self._current_cover_position = position
        elif self.has_config(CONF_SET_POSITION_DP):
            raw_position = self.dps_conf(CONF_SET_POSITION_DP)
            position = _range_to_percent(
                raw_position,
                self._config.get(CONF_SET_POSITION_MIN, 0),
                self._config.get(CONF_SET_POSITION_MAX, 100),
                bool(self._config.get(
                    CONF_SET_POSITION_INVERTED, self._position_inverted
                )),
            )
            if position is not None:
                self._current_cover_position = position

        self._semantic_state = None
        action_dp = self._config.get(CONF_COVER_ACTION_DP)
        if action_dp is not None and self._action_values:
            raw_action = self.dps(action_dp)
            self._semantic_state = next(
                (name for name, raw in self._action_values.items() if raw_action == raw),
                None,
            )
        open_dp = self._config.get(CONF_COVER_OPEN_DP)
        if self._semantic_state is None and open_dp is not None and self._open_values:
            raw_open = self.dps(open_dp)
            semantic = next(
                (name for name, raw in self._open_values.items() if raw_open == raw),
                None,
            )
            if semantic == "open":
                self._semantic_state = "opened"
                self._current_cover_position = 100
            elif semantic == "closed":
                self._semantic_state = "closed"
                self._current_cover_position = 0

        tilt_dp = self._config.get(CONF_TILT_POSITION_DP)
        if tilt_dp is not None:
            self._attr_current_cover_tilt_position = _range_to_percent(
                self.dps(tilt_dp),
                self._config.get(CONF_TILT_POSITION_MIN, 0),
                self._config.get(CONF_TILT_POSITION_MAX, 100),
                bool(self._config.get(CONF_TILT_POSITION_INVERTED, False)),
            )

        if (
            self._positioning_mode == COVER_MODE_TIMED
            and self._state != self._previous_state
        ):
            if (
                self._previous_state != self._stop_cmd
                and self._current_cover_position is not None
            ):
                elapsed = (
                    time.monotonic() - self._timer_start
                )

                position_delta = round(
                    elapsed / self._span_time * 100.0
                )

                if self._previous_state == self._close_cmd:
                    position_delta = -position_delta

                self._current_cover_position = min(
                    100,
                    max(
                        0,
                        self._current_cover_position
                        + position_delta,
                    ),
                )

                change = (
                    "stopped"
                    if self._state == self._stop_cmd
                    else "inverted"
                )

                self.debug(
                    "Movement %s after %.2f sec., "
                    "position difference %s",
                    change,
                    elapsed,
                    position_delta,
                )

            self._timer_start = time.monotonic()

        if (
            self._state is not None
            and not self._device.is_connecting
        ):
            self._last_state = self._state


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaCover,
    flow_schema,
)
