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
    ATTR_WHITE,
    DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_BRIGHTNESS, CONF_COLOR_TEMP, CONF_SCENE

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_BRIGHTNESS_LOWER,
    CONF_BRIGHTNESS_NULL_VALUE,
    CONF_BRIGHTNESS_STEP,
    CONF_BRIGHTNESS_UPPER,
    CONF_BRIGHTNESS_VALUES,
    CONF_BRIGHTNESS_AS_POWER,
    CONF_COLOR,
    CONF_COLOR_RGB_ENCODING,
    CONF_COLOR_SATURATION_UPPER,
    CONF_COLOR_BRIGHTNESS_LOWER,
    CONF_COLOR_BRIGHTNESS_UPPER,
    CONF_COLOR_MODE,
    CONF_COLOR_MODE_SET,
    CONF_COLOR_TEMP_MAX_KELVIN,
    CONF_COLOR_TEMP_MIN_KELVIN,
    CONF_COLOR_TEMP_REVERSE,
    CONF_COLOR_TEMP_STEP,
    CONF_COLOR_TEMP_VALUES,
    CONF_EFFECT,
    CONF_EFFECT_VALUES,
    CONF_LIGHT_OFF_VALUE,
    CONF_LIGHT_ON_VALUE,
    CONF_LIGHT_NULL_VALUE,
    CONF_LIGHT_POWER_MASK,
    CONF_MUSIC_MODE,
    CONF_SCENE_VALUES,
    CONF_WHITE_MODE,
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


def _light_power_scalar(value):
    """Validate an exact scalar light power value without coercion."""
    if isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise vol.Invalid("light power value must be bool, int or str")


def _same_raw_value(value, expected) -> bool:
    """Compare Tuya raw values without Python bool/int equality leakage."""
    return type(value) is type(expected) and value == expected


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_BRIGHTNESS): vol.In(dps),
        vol.Optional(CONF_COLOR_TEMP): vol.In(dps),
        vol.Optional(CONF_LIGHT_ON_VALUE): _light_power_scalar,
        vol.Optional(CONF_LIGHT_OFF_VALUE): _light_power_scalar,
        vol.Optional(CONF_LIGHT_NULL_VALUE): bool,
        vol.Optional(CONF_LIGHT_POWER_MASK): str,
        vol.Optional(CONF_BRIGHTNESS_VALUES): dict,
        vol.Optional(CONF_BRIGHTNESS_AS_POWER, default=False): bool,
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
        vol.Optional(
            CONF_BRIGHTNESS_STEP,
            default=1,
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=10000),
        ),
        vol.Optional(CONF_BRIGHTNESS_NULL_VALUE): vol.All(
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
        vol.Optional(CONF_COLOR_TEMP_STEP, default=1): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=10000),
        ),
        vol.Optional(CONF_COLOR_TEMP_VALUES): dict,
        vol.Optional(CONF_COLOR_SATURATION_UPPER): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=65535),
        ),
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

        self._power_on_value = self._config.get(CONF_LIGHT_ON_VALUE, True)
        self._power_off_value = self._config.get(CONF_LIGHT_OFF_VALUE, False)
        self._brightness_as_power = bool(
            self._config.get(CONF_BRIGHTNESS_AS_POWER, False)
        )
        self._brightness_values = self._configured_brightness_values()
        self._light_power_mask = self._configured_light_power_mask()

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

        try:
            self._brightness_step = int(
                self._config.get(CONF_BRIGHTNESS_STEP, 1)
            )
        except (TypeError, ValueError):
            self._brightness_step = 1
        if self._brightness_step <= 0:
            self.warning(
                "Invalid brightness step %s; using 1",
                self._brightness_step,
            )
            self._brightness_step = 1

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
        try:
            self._color_temp_step = int(
                self._config.get(CONF_COLOR_TEMP_STEP, 1)
            )
        except (TypeError, ValueError):
            self._color_temp_step = 1
        if self._color_temp_step <= 0:
            self._color_temp_step = 1
        self._color_temp_values = self._configured_color_temp_values()

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

        # Catalog mappings can mark RGBW lights whose dedicated white mode
        # uses the normal brightness DP but has no color-temperature DP.
        self._white_mode_enabled = bool(
            self._config.get(CONF_WHITE_MODE, False)
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

        if (
            self._white_mode_enabled
            and self.has_config(CONF_BRIGHTNESS)
        ):
            color_modes.add(ColorMode.WHITE)

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
            self._is_white_mode(mode)
            and ColorMode.WHITE in supported
        ):
            return ColorMode.WHITE

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

    def _configured_brightness_values(self) -> list[tuple[int, object]]:
        """Return ordered HA-brightness -> exact raw value mappings."""
        configured = self._config.get(CONF_BRIGHTNESS_VALUES)
        if not isinstance(configured, dict):
            return []

        result: list[tuple[int, object]] = []
        raw_values: list[object] = []
        for raw_brightness, raw_value in configured.items():
            if isinstance(raw_brightness, bool):
                continue
            try:
                brightness = int(raw_brightness)
            except (TypeError, ValueError):
                continue
            if brightness < 0 or brightness > 255:
                continue
            if not isinstance(raw_value, (bool, int, str)):
                continue
            if any(_same_raw_value(raw_value, seen) for seen in raw_values):
                continue
            result.append((brightness, raw_value))
            raw_values.append(raw_value)
        return result

    def _configured_color_temp_values(self) -> list[tuple[int, int]]:
        """Return ordered Kelvin -> raw discrete color-temperature mappings."""
        configured = self._config.get(CONF_COLOR_TEMP_VALUES)
        if not isinstance(configured, dict):
            return []

        result: list[tuple[int, int]] = []
        raw_values: set[int] = set()
        for raw_kelvin, raw_value in configured.items():
            if isinstance(raw_kelvin, bool) or isinstance(raw_value, bool):
                continue
            try:
                kelvin = int(raw_kelvin)
                value = int(raw_value)
            except (TypeError, ValueError):
                continue
            if not 1500 <= kelvin <= 8000 or value in raw_values:
                continue
            result.append((kelvin, value))
            raw_values.add(value)
        return result

    def _configured_light_power_mask(self) -> tuple[int, int] | None:
        """Validate an exact big-endian hex bit mask for a packed light switch."""
        raw_mask = self._config.get(CONF_LIGHT_POWER_MASK)
        if not isinstance(raw_mask, str):
            return None
        mask = raw_mask.strip()
        if not mask or len(mask) % 2 or any(ch not in "0123456789abcdefABCDEF" for ch in mask):
            return None
        value = int(mask, 16)
        if value <= 0:
            return None
        return value, len(mask)

    def _masked_power_state(self, raw_power) -> bool | None:
        """Read one boolean bit from a packed big-endian hex DP."""
        configured = getattr(self, "_light_power_mask", None)
        if configured is None or not isinstance(raw_power, str):
            return None
        value = raw_power.strip()
        if not value or len(value) % 2 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
            return None
        mask, _ = configured
        return bool(int(value, 16) & mask)

    def _masked_power_write_value(self, turn_on: bool) -> str | None:
        """Return a read-modify-write packed hex value, or None if current is unknown."""
        configured = getattr(self, "_light_power_mask", None)
        current = getattr(self, "_state", None)
        if configured is None or not isinstance(current, str):
            return None
        current = current.strip()
        if not current or len(current) % 2 or any(ch not in "0123456789abcdefABCDEF" for ch in current):
            return None
        mask, mask_width = configured
        value = int(current, 16)
        value = value | mask if turn_on else value & ~mask
        width = max(mask_width, len(current))
        return f"{value:0{width}x}"

    def _color_saturation_upper(self, *, extended: bool) -> int:
        """Return the raw saturation maximum for the active color payload."""
        configured = self._config.get(CONF_COLOR_SATURATION_UPPER)
        if isinstance(configured, bool):
            configured = None
        if configured is not None:
            try:
                value = int(configured)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
        return 255 if extended else 1000

    def _raw_brightness_to_ha(self, value) -> int | None:
        """Convert a Tuya brightness value to HA's 0..255 range."""
        if value is None:
            config = getattr(self, "_config", {})
            if isinstance(config, dict):
                value = config.get(CONF_BRIGHTNESS_NULL_VALUE)
            if value is None:
                return None

        mapped = getattr(self, "_brightness_values", [])
        if mapped:
            for brightness, raw_value in mapped:
                if _same_raw_value(value, raw_value):
                    return brightness
            return None

        if isinstance(value, bool):
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

    def _ha_brightness_to_raw(self, value):
        """Convert HA brightness to the exact Tuya brightness representation."""
        mapped = getattr(self, "_brightness_values", [])
        if mapped:
            target = min(max(int(value), 0), 255)
            best_raw = mapped[0][1]
            best_distance = abs(mapped[0][0] - target)
            for brightness, raw_value in mapped[1:]:
                distance = abs(brightness - target)
                if distance < best_distance:
                    best_raw = raw_value
                    best_distance = distance
            return best_raw

        raw_value = map_range(
            int(value),
            0,
            255,
            self._lower_brightness,
            self._upper_brightness,
        )
        brightness_step = getattr(self, "_brightness_step", 1)
        if brightness_step != 1:
            raw_value = brightness_step * round(
                float(raw_value) / brightness_step
            )
        return raw_value

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

        discrete = getattr(self, "_color_temp_values", [])
        if discrete:
            try:
                raw_value = int(value)
            except (TypeError, ValueError):
                return None
            for kelvin, configured_raw in discrete:
                if raw_value == configured_raw:
                    return kelvin
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

        discrete = getattr(self, "_color_temp_values", [])
        if discrete:
            best_raw = discrete[0][1]
            best_distance = abs(discrete[0][0] - kelvin)
            for configured_kelvin, raw_value in discrete[1:]:
                distance = abs(configured_kelvin - kelvin)
                if distance < best_distance:
                    best_raw = raw_value
                    best_distance = distance
            return best_raw

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

        step = getattr(self, "_color_temp_step", 1)
        if step != 1:
            raw_value = step * round(float(raw_value) / step)
            raw_value = min(max(raw_value, 0), self._raw_color_temp_max)

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

                saturation_upper = self._color_saturation_upper(extended=True)
                hs = (
                    min(max(float(hue), 0.0), 360.0),
                    min(
                        max(saturation * 100.0 / saturation_upper, 0.0),
                        100.0,
                    ),
                )

                if (
                    CONF_COLOR_BRIGHTNESS_LOWER in self._config
                    or CONF_COLOR_BRIGHTNESS_UPPER in self._config
                ):
                    brightness = self._raw_color_brightness_to_ha(value)
                else:
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

            saturation_upper = self._color_saturation_upper(extended=False)
            hs = (
                min(max(float(hue), 0.0), 360.0),
                min(max(saturation * 100.0 / saturation_upper, 0.0), 100.0),
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

            saturation_upper = self._color_saturation_upper(extended=True)
            raw_saturation = round(saturation * saturation_upper / 100.0)
            if (
                CONF_COLOR_BRIGHTNESS_LOWER in self._config
                or CONF_COLOR_BRIGHTNESS_UPPER in self._config
            ):
                raw_brightness = self._ha_brightness_to_raw_color(brightness)
            else:
                raw_brightness = brightness

            return (
                f"{round(rgb[0]):02x}"
                f"{round(rgb[1]):02x}"
                f"{round(rgb[2]):02x}"
                f"{round(hue):04x}"
                f"{raw_saturation:02x}"
                f"{raw_brightness:02x}"
            )

        raw_brightness = self._ha_brightness_to_raw_color(
            brightness
        )
        saturation_upper = self._color_saturation_upper(extended=False)
        raw_saturation = round(saturation * saturation_upper / 100.0)

        return (
            f"{round(hue):04x}"
            f"{raw_saturation:04x}"
            f"{raw_brightness:04x}"
        )

    def _find_scene_by_scene_data(self, data) -> str:
        """Find the friendly scene name for a Tuya scene payload."""
        # Tuya Local also models a bare ``scene`` work-mode value as an
        # effect carried entirely by the color-mode DP.  When no dedicated
        # scene-data DP exists, use that exact work-mode value for lookup
        # instead of treating the effect as an unknown/custom payload.
        if data is None and not self.has_config(CONF_SCENE):
            data = self._modes.scene

        for name, scene_data in self._scenes.items():
            if scene_data == data:
                return name

        return SCENE_CUSTOM

    def _set_configured_dp(self, states, config_key, value):
        """Add a DP write only when that DP is configured."""
        if self.has_config(config_key):
            states[self._config[config_key]] = value

    def _power_state_from_raw(self, raw_power):
        """Translate an exact raw Tuya power value to HA state."""
        config = getattr(self, "_config", {})
        if getattr(self, "_light_power_mask", None) is not None:
            return self._masked_power_state(raw_power)
        if raw_power is None and isinstance(config, dict) and CONF_LIGHT_NULL_VALUE in config:
            return bool(config[CONF_LIGHT_NULL_VALUE])

        custom_values = (
            isinstance(config, dict)
            and (CONF_LIGHT_ON_VALUE in config or CONF_LIGHT_OFF_VALUE in config)
        )
        on_value = getattr(self, "_power_on_value", True)
        off_value = getattr(self, "_power_off_value", False)

        if _same_raw_value(raw_power, on_value):
            return True
        if _same_raw_value(raw_power, off_value):
            return False

        # Preserve historical LocalTuya bool/0/1 reads when no exact mapping
        # was configured. Custom raw values stay strictly type-aware.
        if not custom_values:
            if isinstance(raw_power, bool):
                return raw_power
            if isinstance(raw_power, int) and not isinstance(raw_power, bool) and raw_power in (0, 1):
                return bool(raw_power)

        return None

    async def async_turn_on(self, **kwargs):
        """Turn on or control the light."""
        states = {}

        if self.is_on is not True:
            if getattr(self, "_brightness_as_power", False):
                if ATTR_BRIGHTNESS not in kwargs:
                    states[self._dp_id] = self._ha_brightness_to_raw(255)
            elif getattr(self, "_light_power_mask", None) is not None:
                masked = self._masked_power_write_value(True)
                if masked is not None:
                    states[self._dp_id] = masked
            else:
                states[self._dp_id] = getattr(self, "_power_on_value", True)

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
        requested_white = kwargs.get(ATTR_WHITE)

        if (
            requested_white is not None
            and ColorMode.WHITE in self._attr_supported_color_modes
        ):
            self._set_configured_dp(
                states,
                CONF_COLOR_MODE,
                self._modes.white,
            )
            self._set_configured_dp(
                states,
                CONF_BRIGHTNESS,
                self._ha_brightness_to_raw(int(requested_white)),
            )

        elif (
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
        if getattr(self, "_brightness_as_power", False):
            await self._device.set_dp(self._ha_brightness_to_raw(0), self._dp_id)
            return
        if getattr(self, "_light_power_mask", None) is not None:
            masked = self._masked_power_write_value(False)
            if masked is not None:
                await self._device.set_dp(masked, self._dp_id)
            return
        await self._device.set_dp(getattr(self, "_power_off_value", False), self._dp_id)

    def status_updated(self):
        """Update the light from the latest Tuya status."""
        super().status_updated()

        raw_power = self._state
        if getattr(self, "_brightness_as_power", False):
            power_brightness = self._raw_brightness_to_ha(raw_power)
            self._attr_is_on = (
                power_brightness is not None and power_brightness > 0
            )
        else:
            self._attr_is_on = self._power_state_from_raw(raw_power)

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
                or (
                    ColorMode.COLOR_TEMP
                    not in self._attr_supported_color_modes
                    and ColorMode.WHITE
                    not in self._attr_supported_color_modes
                )
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
