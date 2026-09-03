"""Platform to locally control Tuya-based cover devices."""

import asyncio
import logging
import time
from functools import partial

import voluptuous as vol
from homeassistant.components.cover import (
    ATTR_POSITION,
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

        features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
        )

        if self._positioning_mode != COVER_MODE_NONE:
            features |= CoverEntityFeature.SET_POSITION

        self._attr_supported_features = features

    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        return self._current_cover_position

    @property
    def is_opening(self) -> bool:
        """Return whether the cover is opening."""
        return self._state == self._open_cmd

    @property
    def is_closing(self) -> bool:
        """Return whether the cover is closing."""
        return self._state == self._close_cmd

    @property
    def is_closed(self) -> bool | None:
        """Return whether the cover is fully closed."""
        if self._positioning_mode == COVER_MODE_NONE:
            return None

        if self._current_cover_position is None:
            return None

        return self._current_cover_position <= 0

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

            converted = requested

            if self._position_inverted:
                converted = 100 - converted

            if not self.has_config(CONF_SET_POSITION_DP):
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
        await self._async_start_movement(self._open_cmd)

        if self._positioning_mode == COVER_MODE_TIMED:
            self._schedule_stop(
                self._span_time + COVER_TIMEOUT_TOLERANCE
            )

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._async_start_movement(self._close_cmd)

        if self._positioning_mode == COVER_MODE_TIMED:
            self._schedule_stop(
                self._span_time + COVER_TIMEOUT_TOLERANCE
            )

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
            raw_position = self.dps_conf(
                CONF_CURRENT_POSITION_DP
            )

            if (
                isinstance(raw_position, (int, float))
                and not isinstance(raw_position, bool)
            ):
                position = round(raw_position)

                if self._position_inverted:
                    position = 100 - position

                self._current_cover_position = min(
                    max(position, 0),
                    100,
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
