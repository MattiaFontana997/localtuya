"""Platform to locally control Tuya-based light devices."""

import logging
import textwrap
from dataclasses import dataclass
from functools import partial

import homeassistant.util.color as color_util
import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_BRIGHTNESS, CONF_COLOR_TEMP, CONF_SCENE

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_BRIGHTNESS_LOWER,
    CONF_BRIGHTNESS_UPPER,
    CONF_COLOR,
    CONF_COLOR_RGB_ENCODING,
    CONF_COLOR_BRIGHTNESS_LOWER,
    CONF_COLOR_BRIGHTNESS_UPPER,
    CONF_COLOR_MODE,
    CONF_COLOR_MODE_SET,
    CONF_COLOR_TEMP_MAX_KELVIN,
    CONF_COLOR_TEMP_MIN_KELVIN,
    CONF_COLOR_TEMP_REVERSE,
    CONF_EFFECT,
    CONF_EFFECT_VALUES,
    CONF_MUSIC_MODE,
    CONF_SCENE_VALUES,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_MIN_KELVIN = 2700
DEFAULT_MAX_KELVIN = 6500

DEFAULT_COLOR_TEMP_REVERSE = False

DEFAULT_LOWER_BRIGHTNESS = 29
DEFAULT_UPPER_BRIGHTNESS = 1000

MODE_MANUAL = "manual"
MODE_COLOR = "colour"
MODE_MUSIC = "music"
MODE_SCENE = "scene"
MODE_WHITE = "white"

SCENE_CUSTOM = "Custom"
SCENE_MUSIC = "Music"

MODES_SET = {
    "Colour, Music, Scene and White": 0,
    "Manual, Music, Scene and White": 1,
}

SCENE_LIST_RGBW_1000 = {
    "Night": "000e0d0000000000000000c80000",
    "Read": "010e0d0000000000000003e801f4",
    "Meeting": "020e0d0000000000000003e803e8",
    "Leasure": "030e0d0000000000000001f401f4",
    "Soft": "04464602007803e803e800000000464602007803e8000a00000000",
    "Rainbow": (
        "05464601000003e803e800000000464601007803e803e800000000"
        "46460100f003e803e800000000"
    ),
    "Shine": (
        "06464601000003e803e800000000464601007803e803e800000000"
        "46460100f003e803e800000000"
    ),
    "Beautiful": (
        "07464602000003e803e800000000464602007803e803e800000000"
        "46460200f003e803e800000000464602003d03e803e800000000"
        "46460200ae03e803e800000000464602011303e803e800000000"
    ),
}

SCENE_LIST_RGBW_255 = {
    "Night": "bd76000168ffff",
    "Read": "fffcf70168ffff",
    "Meeting": "cf38000168ffff",
    "Leasure": "3855b40168ffff",
    "Scenario 1": "scene_1",
    "Scenario 2": "scene_2",
    "Scenario 3": "scene_3",
    "Scenario 4": "scene_4",
}

SCENE_LIST_RGB_1000 = {
    "Night": "000e0d00002e03e802cc00000000",
    "Read": "010e0d000084000003e800000000",
    "Working": "020e0d00001403e803e800000000",
    "Leisure": "030e0d0000e80383031c00000000",
    "Soft": "04464602007803e803e800000000464602007803e8000a00000000",
    "Colorful": (
        "05464601000003e803e800000000464601007803e803e800000000"
        "46460100f003e803e800000000464601003d03e803e800000000"
        "46460100ae03e803e800000000464601011303e803e800000000"
    ),
    "Dazzling": (
        "06464601000003e803e800000000464601007803e803e800000000"
        "46460100f003e803e800000000"
    ),
    "Music": (
        "07464602000003e803e800000000464602007803e803e800000000"
        "46460200f003e803e800000000464602003d03e803e800000000"
        "46460200ae03e803e800000000464602011303e803e800000000"
    ),
}


@dataclass(frozen=True)
class Mode:
    """Tuya work-mode values."""

    color: str = MODE_COLOR
    music: str = MODE_MUSIC
    scene: str = MODE_SCENE
    white: str = MODE_WHITE

    def as_list(self) -> list[str]:
        """Return all known work modes."""
        return [self.color, self.music, self.scene, self.white]

    def as_dict(self) -> dict[str, str]:
        """Return work modes for configuration UI."""
        return {
            "Default": self.white,
            "Mode Color": self.color,
            "Mode Scene": self.scene,
        }


MAP_MODE_SET = {
    0: Mode(),
    1: Mode(color=MODE_MANUAL),
}


def map_range(value, from_lower, from_upper, to_lower, to_upper):
    """Map a value from one numeric range to another."""
    if from_upper == from_lower:
        return round(to_lower)

    mapped = (
        (value - from_lower)
        * (to_upper - to_lower)
        / (from_upper - from_lower)
        + to_lower
    )

    low = min(to_lower, to_upper)
    high = max(to_lower, to_upper)

    return round(min(max(mapped, low), high))


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_BRIGHTNESS): vol.In(dps),
        vol.Optional(CONF_COLOR_TEMP): vol.In(dps),
        vol.Optional(
            CONF_BRIGHTNESS_LOWER,
            default=DEFAULT_LOWER_BRIGHTNESS,
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=0, max=10000),
        ),
        vol.Optional(
            CONF_BRIGHTNESS_UPPER,
            default=DEFAULT_UPPER_BRIGHTNESS,
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=0, max=10000),
        ),
        vol.Optional(CONF_COLOR_MODE): vol.In(dps),
        vol.Optional(CONF_COLOR): vol.In(dps),
        vol.Optional(
            CONF_COLOR_TEMP_MIN_KELVIN,
            default=DEFAULT_MIN_KELVIN,
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=1500, max=8000),
        ),
        vol.Optional(
            CONF_COLOR_TEMP_MAX_KELVIN,
            default=DEFAULT_MAX_KELVIN,
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=1500, max=8000),
        ),
        vol.Optional(
            CONF_COLOR_TEMP_REVERSE,
            default=DEFAULT_COLOR_TEMP_REVERSE,
            description={"suggested_value": DEFAULT_COLOR_TEMP_REVERSE},
        ): bool,
        vol.Optional(CONF_SCENE): vol.In(dps),
        vol.Optional(
            CONF_MUSIC_MODE,
            default=False,
            description={"suggested_value": False},
        ): bool,
    }


class LocaltuyaLight(LocalTuyaEntity, LightEntity):
    """Representation of a Tuya light."""

    def __init__(
        self,
        device,
        config_entry,
        lightid,
        **kwargs,
    ):
        """Initialize the Tuya light."""
        super().__init__(
            device,
            config_entry,
            lightid,
            _LOGGER,
            **kwargs,
        )

        self._state = None
        self._attr_is_on = None
        self._attr_brightness = None
        self._attr_hs_color = None
        self._attr_color_temp_kelvin = None
        self._attr_color_mode = None
        self._attr_effect = None

        self._lower_brightness = int(
            self._config.get(
                CONF_BRIGHTNESS_LOWER,
                DEFAULT_LOWER_BRIGHTNESS,
            )
        )
        self._upper_brightness = int(
            self._config.get(
                CONF_BRIGHTNESS_UPPER,
                DEFAULT_UPPER_BRIGHTNESS,
            )
        )

        if self._upper_brightness <= self._lower_brightness:
            self.warning(
                "Invalid brightness range %s..%s; using defaults",
                self._lower_brightness,
                self._upper_brightness,
            )
            self._lower_brightness = DEFAULT_LOWER_BRIGHTNESS
            self._upper_brightness = DEFAULT_UPPER_BRIGHTNESS

        self._lower_color_brightness = int(
            self._config.get(
                CONF_COLOR_BRIGHTNESS_LOWER,
                self._lower_brightness,
            )
        )
        self._upper_color_brightness = int(
            self._config.get(
                CONF_COLOR_BRIGHTNESS_UPPER,
                self._upper_brightness,
            )
        )

        if self._upper_color_brightness <= self._lower_color_brightness:
            self.warning(
                "Invalid color brightness range %s..%s; using white brightness range",
                self._lower_color_brightness,
                self._upper_color_brightness,
            )
            self._lower_color_brightness = self._lower_brightness
            self._upper_color_brightness = self._upper_brightness

        configured_min_kelvin = int(
            self._config.get(
                CONF_COLOR_TEMP_MIN_KELVIN,
                DEFAULT_MIN_KELVIN,
            )
        )
        configured_max_kelvin = int(
            self._config.get(
                CONF_COLOR_TEMP_MAX_KELVIN,
                DEFAULT_MAX_KELVIN,
            )
        )

        self._min_kelvin = min(
            configured_min_kelvin,
            configured_max_kelvin,
        )
        self._max_kelvin = max(
            configured_min_kelvin,
            configured_max_kelvin,
        )

        if self._min_kelvin == self._max_kelvin:
            self.warning(
                "Invalid color temperature range %s..%s K; using defaults",
                configured_min_kelvin,
                configured_max_kelvin,
            )
            self._min_kelvin = DEFAULT_MIN_KELVIN
            self._max_kelvin = DEFAULT_MAX_KELVIN

        self._max_mired = (
            color_util.color_temperature_kelvin_to_mired(
                self._min_kelvin
            )
        )
        self._min_mired = (
            color_util.color_temperature_kelvin_to_mired(
                self._max_kelvin
            )
        )

        self._raw_color_temp_max = self._upper_brightness

        self._color_temp_reverse = bool(
            self._config.get(
                CONF_COLOR_TEMP_REVERSE,
                DEFAULT_COLOR_TEMP_REVERSE,
            )
        )

        mode_set = self._config.get(CONF_COLOR_MODE_SET, 0)

        if isinstance(mode_set, str) and mode_set in MODES_SET:
            mode_set = MODES_SET[mode_set]

        try:
            mode_set = int(mode_set)
        except (TypeError, ValueError):
            mode_set = 0

        self._modes = MAP_MODE_SET.get(mode_set, Mode())

        # Catalog mappings can explicitly require Tuya's legacy 14-hex
        # RRGGBB+HHHH+SS+VV payload. Without this flag, keep the historical
        # auto-detection behaviour based on the first color payload received.
        self._color_rgb_encoding_forced = bool(
            self._config.get(CONF_COLOR_RGB_ENCODING, False)
        )
        self._color_uses_rgb_encoding = self._color_rgb_encoding_forced
        self._scenes = self._configured_scenes()

        if not self._scenes and self.has_config(CONF_SCENE):
            try:
                scene_dp = int(self._config[CONF_SCENE])
            except (TypeError, ValueError):
                scene_dp = 20

            if scene_dp < 20:
                self._scenes = SCENE_LIST_RGBW_255
            elif not self.has_config(CONF_BRIGHTNESS):
                self._scenes = SCENE_LIST_RGB_1000
            else:
                self._scenes = SCENE_LIST_RGBW_1000

        self._effects = self._configured_effects()

        self._music_mode_enabled = bool(
            self._config.get(CONF_MUSIC_MODE, False)
        )

        self._attr_supported_color_modes = (
            self._build_supported_color_modes()
        )

        features = LightEntityFeature(0)

        effects = self._build_effect_list()
        if effects:
            features |= LightEntityFeature.EFFECT

        self._attr_supported_features = features
        self._attr_effect_list = effects or None

        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_min_color_temp_kelvin = self._min_kelvin
            self._attr_max_color_temp_kelvin = self._max_kelvin

    def _configured_effects(self) -> dict[str, str]:
        """Return exact catalog-provided dedicated effect values."""
        configured = self._config.get(CONF_EFFECT_VALUES)

        if configured is None:
            return {}

        if not self.has_config(CONF_EFFECT):
            self.warning(
                "Ignoring effect_values because no effect DP is configured"
            )
            return {}

        if not isinstance(configured, dict):
            self.warning("Invalid effect_values config")
            return {}

        effects: dict[str, str] = {}
        raw_values: set[str] = set()

        for name, value in configured.items():
            if (
                not isinstance(name, str)
                or not name.strip()
                or not isinstance(value, str)
                or not value
                or value in raw_values
            ):
                self.warning(
                    "Ignoring invalid custom light effect entry %r: %r",
                    name,
                    value,
                )
                continue

            friendly = name.strip()
            if friendly in effects:
                continue

            effects[friendly] = value
            raw_values.add(value)

        return effects

    def _build_effect_list(self) -> list[str]:
        """Build HA effects using Tuya Local's dedicated-DP precedence."""
        if self._effects:
            return list(self._effects)

        effects = list(self._scenes)

        if (
            self._music_mode_enabled
            and SCENE_MUSIC not in effects
        ):
            effects.append(SCENE_MUSIC)

        return effects

    def _find_effect_by_raw(self, value) -> str | None:
        """Translate a raw dedicated effect value to its HA name."""
        for name, raw_value in self._effects.items():
            if raw_value == value:
                return name
        return None

    def _configured_scenes(self) -> dict[str, str]:
        """Return valid catalog-provided Tuya scene values."""
        configured = self._config.get(CONF_SCENE_VALUES)

        if configured is None:
            return {}

        if not isinstance(configured, dict):
            self.warning(
                "Invalid scene_values config; using legacy scene presets"
            )
            return {}

        scenes: dict[str, str] = {}

        for name, value in configured.items():
            if (
                not isinstance(name, str)
                or not name.strip()
                or not isinstance(value, str)
                or not value
            ):
                self.warning(
                    "Ignoring invalid custom light scene entry %r: %r",
                    name,
                    value,
                )
                continue

            if (
                not value.startswith(self._modes.scene)
                and not self.has_config(CONF_SCENE)
            ):
                self.warning(
                    "Ignoring payload scene %s because no scene DP is configured",
                    name,
                )
                continue

            scenes[name.strip()] = value

        return scenes

    def _build_supported_color_modes(self) -> set[ColorMode]:
        """Return supported Home Assistant color modes."""
        color_modes = set()

        if self.has_config(CONF_COLOR_TEMP):
            color_modes.add(ColorMode.COLOR_TEMP)

        if self.has_config(CONF_COLOR):
            color_modes.add(ColorMode.HS)

        if color_modes:
            return color_modes

        if self.has_config(CONF_BRIGHTNESS):
            return {ColorMode.BRIGHTNESS}

        return {ColorMode.ONOFF}

    def _raw_mode(self):
        """Return the current raw Tuya work mode."""
        if self.has_config(CONF_COLOR_MODE):
            return self.dps_conf(CONF_COLOR_MODE)

        # A color-only lamp with no work-mode DP is always in color mode.
        if (
            self.has_config(CONF_COLOR)
            and not self.has_config(CONF_COLOR_TEMP)
        ):
            return self._modes.color

        return self._modes.white

    def _is_white_mode(self, mode=None) -> bool:
        """Return whether current Tuya mode is white."""
        if mode is None:
            mode = self._raw_mode()

        return mode is None or mode == self._modes.white

    def _is_color_mode(self, mode=None) -> bool:
        """Return whether current Tuya mode is color."""
        if mode is None:
            mode = self._raw_mode()

        return mode == self._modes.color

    def _is_scene_mode(self, mode=None) -> bool:
        """Return whether current Tuya mode is a scene."""
        if mode is None:
            mode = self._raw_mode()

        return (
            isinstance(mode, str)
            and mode.startswith(self._modes.scene)
        )

    def _is_music_mode(self, mode=None) -> bool:
        """Return whether current Tuya mode is music."""
        if mode is None:
            mode = self._raw_mode()

        return mode == self._modes.music

    def _determine_color_mode(self, mode) -> ColorMode:
        """Translate Tuya work mode to a Home Assistant color mode."""
        supported = self._attr_supported_color_modes

        if len(supported) == 1:
            return next(iter(supported))

        if self._is_color_mode(mode) and ColorMode.HS in supported:
            return ColorMode.HS

        if (
            self._is_white_mode(mode)
            and ColorMode.COLOR_TEMP in supported
        ):
            return ColorMode.COLOR_TEMP

        if (
            self._attr_color_mode is not None
            and self._attr_color_mode in supported
        ):
            return self._attr_color_mode

        if ColorMode.COLOR_TEMP in supported:
            return ColorMode.COLOR_TEMP

        if ColorMode.HS in supported:
            return ColorMode.HS

        if ColorMode.BRIGHTNESS in supported:
            return ColorMode.BRIGHTNESS

        return ColorMode.ONOFF

    def _raw_brightness_to_ha(self, value) -> int | None:
        """Convert a Tuya brightness value to HA's 0..255 range."""
        if value is None or isinstance(value, bool):
            return None

        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        return map_range(
            value,
            self._lower_brightness,
            self._upper_brightness,
            0,
            255,
        )

    def _ha_brightness_to_raw(self, value) -> int:
        """Convert HA brightness to the Tuya brightness range."""
        return map_range(
            int(value),
            0,
            255,
            self._lower_brightness,
            self._upper_brightness,
        )

    def _raw_color_brightness_to_ha(self, value) -> int | None:
        """Convert a Tuya HSV value to HA's 0..255 brightness range."""
        if value is None or isinstance(value, bool):
            return None

        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        return map_range(
            value,
            self._lower_color_brightness,
            self._upper_color_brightness,
            0,
            255,
        )

    def _ha_brightness_to_raw_color(self, value) -> int:
        """Convert HA brightness to the Tuya HSV value range."""
        return map_range(
            int(value),
            0,
            255,
            self._lower_color_brightness,
            self._upper_color_brightness,
        )

    def _raw_color_temp_to_kelvin(self, value) -> int | None:
        """Convert a Tuya color-temperature DP to Kelvin."""
        if value is None or isinstance(value, bool):
            return None

        try:
            raw_value = float(value)
        except (TypeError, ValueError):
            return None

        raw_value = min(
            max(raw_value, 0),
            self._raw_color_temp_max,
        )

        if self._color_temp_reverse:
            raw_value = self._raw_color_temp_max - raw_value

        ratio = raw_value / self._raw_color_temp_max

        mired = (
            self._max_mired
            - ((self._max_mired - self._min_mired) * ratio)
        )

        kelvin = color_util.color_temperature_mired_to_kelvin(mired)

        return min(
            max(kelvin, self._min_kelvin),
            self._max_kelvin,
        )

    def _kelvin_to_raw_color_temp(self, kelvin) -> int:
        """Convert a Kelvin color temperature to Tuya DP format."""
        kelvin = min(
            max(int(kelvin), self._min_kelvin),
            self._max_kelvin,
        )

        mired = color_util.color_temperature_kelvin_to_mired(kelvin)

        ratio = (
            (self._max_mired - mired)
            / (self._max_mired - self._min_mired)
        )

        raw_value = round(
            ratio * self._raw_color_temp_max
        )

        raw_value = min(
            max(raw_value, 0),
            self._raw_color_temp_max,
        )

        if self._color_temp_reverse:
            raw_value = self._raw_color_temp_max - raw_value

        return raw_value

    def _decode_color(self, raw_color):
        """Decode a Tuya HSV/RGB+HSV color payload."""
        if not isinstance(raw_color, str):
            return None

        raw_color = raw_color.strip()

        try:
            if len(raw_color) > 12:
                if len(raw_color) < 14:
                    return None

                self._color_uses_rgb_encoding = True

                hue = int(raw_color[6:10], 16)
                saturation = int(raw_color[10:12], 16)
                value = int(raw_color[12:14], 16)

                hs = (
                    min(max(float(hue), 0.0), 360.0),
                    min(
                        max(saturation * 100.0 / 255.0, 0.0),
                        100.0,
                    ),
                )

                brightness = min(max(value, 0), 255)

                return hs, brightness

            if len(raw_color) < 12:
                return None

            # An explicitly configured RGB+HSV device must keep using the
            # extended layout for writes even if it reports a legacy HSV-only
            # payload once. Auto-detected devices retain the old behaviour.
            if not self._color_rgb_encoding_forced:
                self._color_uses_rgb_encoding = False

            hue, saturation, value = [
                int(chunk, 16)
                for chunk in textwrap.wrap(raw_color[:12], 4)
            ]

            hs = (
                min(max(float(hue), 0.0), 360.0),
                min(max(saturation / 10.0, 0.0), 100.0),
            )

            brightness = self._raw_color_brightness_to_ha(value)

            return hs, brightness

        except ValueError:
            return None

    def _encode_color(self, hs, brightness) -> str:
        """Encode HA HSV values into the Tuya color DP format."""
        hue = min(max(float(hs[0]), 0.0), 360.0)
        saturation = min(max(float(hs[1]), 0.0), 100.0)
        brightness = min(max(int(brightness), 0), 255)

        if self._color_uses_rgb_encoding:
            rgb = color_util.color_hsv_to_RGB(
                hue,
                saturation,
                brightness * 100.0 / 255.0,
            )

            return (
                f"{round(rgb[0]):02x}"
                f"{round(rgb[1]):02x}"
                f"{round(rgb[2]):02x}"
                f"{round(hue):04x}"
                f"{round(saturation * 255.0 / 100.0):02x}"
                f"{brightness:02x}"
            )

        raw_brightness = self._ha_brightness_to_raw_color(
            brightness
        )

        return (
            f"{round(hue):04x}"
            f"{round(saturation * 10.0):04x}"
            f"{raw_brightness:04x}"
        )

    def _find_scene_by_scene_data(self, data) -> str:
        """Find the friendly scene name for a Tuya scene payload."""
        for name, scene_data in self._scenes.items():
            if scene_data == data:
                return name

        return SCENE_CUSTOM

    def _set_configured_dp(self, states, config_key, value):
        """Add a DP write only when that DP is configured."""
        if self.has_config(config_key):
            states[self._config[config_key]] = value

    async def async_turn_on(self, **kwargs):
        """Turn on or control the light."""
        states = {}

        if self.is_on is not True:
            states[self._dp_id] = True

        requested_effect = kwargs.get(ATTR_EFFECT)

        if (
            requested_effect is not None
            and self._attr_supported_features
            & LightEntityFeature.EFFECT
        ):
            if self._effects:
                raw_effect = self._effects.get(requested_effect)
                if raw_effect is not None:
                    self._set_configured_dp(
                        states,
                        CONF_EFFECT,
                        raw_effect,
                    )
            else:
                scene = self._scenes.get(requested_effect)

                if scene is not None:
                    if (
                        isinstance(scene, str)
                        and scene.startswith(MODE_SCENE)
                    ):
                        self._set_configured_dp(
                            states,
                            CONF_COLOR_MODE,
                            scene,
                        )
                    else:
                        self._set_configured_dp(
                            states,
                            CONF_COLOR_MODE,
                            self._modes.scene,
                        )
                        self._set_configured_dp(
                            states,
                            CONF_SCENE,
                            scene,
                        )

                elif (
                    requested_effect == SCENE_MUSIC
                    and self._music_mode_enabled
                ):
                    self._set_configured_dp(
                        states,
                        CONF_COLOR_MODE,
                        self._modes.music,
                    )

        requested_brightness = kwargs.get(ATTR_BRIGHTNESS)
        requested_hs = kwargs.get(ATTR_HS_COLOR)
        requested_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)

        if (
            requested_hs is not None
            and ColorMode.HS in self._attr_supported_color_modes
        ):
            brightness = (
                int(requested_brightness)
                if requested_brightness is not None
                else self._attr_brightness
            )

            if brightness is None:
                brightness = 255

            hue, saturation = requested_hs

            # A zero-saturation request can use the dedicated white
            # brightness DP on RGBW devices.
            if (
                saturation == 0
                and self.has_config(CONF_BRIGHTNESS)
                and self.has_config(CONF_COLOR_TEMP)
            ):
                self._set_configured_dp(
                    states,
                    CONF_BRIGHTNESS,
                    self._ha_brightness_to_raw(brightness),
                )
                self._set_configured_dp(
                    states,
                    CONF_COLOR_MODE,
                    self._modes.white,
                )
            else:
                self._set_configured_dp(
                    states,
                    CONF_COLOR,
                    self._encode_color(
                        (hue, saturation),
                        brightness,
                    ),
                )
                self._set_configured_dp(
                    states,
                    CONF_COLOR_MODE,
                    self._modes.color,
                )

        elif (
            requested_kelvin is not None
            and ColorMode.COLOR_TEMP
            in self._attr_supported_color_modes
        ):
            self._set_configured_dp(
                states,
                CONF_COLOR_MODE,
                self._modes.white,
            )
            self._set_configured_dp(
                states,
                CONF_COLOR_TEMP,
                self._kelvin_to_raw_color_temp(
                    requested_kelvin
                ),
            )

            if (
                requested_brightness is not None
                and self.has_config(CONF_BRIGHTNESS)
            ):
                self._set_configured_dp(
                    states,
                    CONF_BRIGHTNESS,
                    self._ha_brightness_to_raw(
                        requested_brightness
                    ),
                )

        elif requested_brightness is not None:
            brightness = int(requested_brightness)
            mode = self._raw_mode()

            if (
                self._is_color_mode(mode)
                and self.has_config(CONF_COLOR)
                and self._attr_hs_color is not None
            ):
                self._set_configured_dp(
                    states,
                    CONF_COLOR,
                    self._encode_color(
                        self._attr_hs_color,
                        brightness,
                    ),
                )
                self._set_configured_dp(
                    states,
                    CONF_COLOR_MODE,
                    self._modes.color,
                )

            elif self.has_config(CONF_BRIGHTNESS):
                self._set_configured_dp(
                    states,
                    CONF_BRIGHTNESS,
                    self._ha_brightness_to_raw(brightness),
                )

        if states:
            await self._device.set_dps(states)

    async def async_turn_off(self, **kwargs):
        """Turn the Tuya light off."""
        await self._device.set_dp(False, self._dp_id)

    def status_updated(self):
        """Update the light from the latest Tuya status."""
        super().status_updated()

        raw_power = self._state

        if isinstance(raw_power, bool):
            self._attr_is_on = raw_power
        elif raw_power in (0, 1):
            self._attr_is_on = bool(raw_power)
        else:
            self._attr_is_on = None

        mode = self._raw_mode()
        self._attr_color_mode = self._determine_color_mode(mode)
        self._attr_effect = None

        if self.has_config(CONF_BRIGHTNESS):
            raw_brightness = self.dps_conf(CONF_BRIGHTNESS)
            brightness = self._raw_brightness_to_ha(
                raw_brightness
            )

            if brightness is not None:
                self._attr_brightness = brightness

        if (
            ColorMode.HS in self._attr_supported_color_modes
            and self.has_config(CONF_COLOR)
            and (
                self._is_color_mode(mode)
                or ColorMode.COLOR_TEMP
                not in self._attr_supported_color_modes
            )
        ):
            decoded = self._decode_color(
                self.dps_conf(CONF_COLOR)
            )

            if decoded is not None:
                hs, brightness = decoded
                self._attr_hs_color = hs

                if brightness is not None:
                    self._attr_brightness = brightness

        if (
            ColorMode.COLOR_TEMP
            in self._attr_supported_color_modes
            and self._is_white_mode(mode)
        ):
            kelvin = self._raw_color_temp_to_kelvin(
                self.dps_conf(CONF_COLOR_TEMP)
            )

            if kelvin is not None:
                self._attr_color_temp_kelvin = kelvin

        if self._effects:
            self._attr_effect = self._find_effect_by_raw(
                self.dps_conf(CONF_EFFECT)
            )

        elif (
            self._is_scene_mode(mode)
            and self._attr_supported_features
            & LightEntityFeature.EFFECT
        ):
            if mode != self._modes.scene:
                scene_data = mode
            else:
                scene_data = self.dps_conf(CONF_SCENE)

            self._attr_effect = (
                self._find_scene_by_scene_data(scene_data)
            )

        elif (
            self._is_music_mode(mode)
            and self._music_mode_enabled
        ):
            self._attr_effect = SCENE_MUSIC

    def entity_default_value(self):
        """Return the default light power value."""
        return False


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaLight,
    flow_schema,
)
