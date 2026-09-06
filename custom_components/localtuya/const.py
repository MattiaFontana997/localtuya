"""Constants for localtuya integration."""

DOMAIN = "localtuya"

DATA_DISCOVERY = "discovery"
DATA_CLOUD = "cloud_data"

# Platforms in this list must support config flows
PLATFORMS = [
    "alarm_control_panel",
    "binary_sensor",
    "button",
    "camera",
    "climate",
    "cover",
    "datetime",
    "event",
    "fan",
    "humidifier",
    "infrared",
    "lawn_mower",
    "light",
    "lock",
    "number",
    "remote",
    "select",
    "sensor",
    "siren",
    "switch",
    "text",
    "time",
    "vacuum",
    "valve",
    "water_heater",
]

TUYA_DEVICES = "tuya_devices"

ATTR_CURRENT = "current"
ATTR_CURRENT_CONSUMPTION = "current_consumption"
ATTR_VOLTAGE = "voltage"
ATTR_UPDATED_AT = "updated_at"

# config flow
CONF_LOCAL_KEY = "local_key"
CONF_ENABLE_DEBUG = "enable_debug"
CONF_PROTOCOL_VERSION = "protocol_version"
CONF_DPS_STRINGS = "dps_strings"
CONF_MODEL = "model"
CONF_PRODUCT_KEY = "product_key"
CONF_PRODUCT_NAME = "product_name"
CONF_USER_ID = "user_id"
CONF_ENABLE_ADD_ENTITIES = "add_entities"

CONF_ACTION = "action"
CONF_ADD_DEVICE = "add_device"
CONF_EDIT_DEVICE = "edit_device"
CONF_REVIEW_MAPPING = "review_mapping"
CONF_PREPARE_CONTRIBUTION = "prepare_contribution"
CONF_SETUP_CLOUD = "setup_cloud"
CONF_NO_CLOUD = "no_cloud"
CONF_MANUAL_DPS = "manual_dps_strings"
CONF_DEFAULT_VALUE = "dps_default_value"
CONF_RESET_DPIDS = "reset_dpids"
CONF_PASSIVE_ENTITY = "is_passive_entity"
CONF_EXTRA_STATE_ATTRIBUTES_DPS = "extra_state_attributes_dps"
CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS = "mapped_extra_state_attributes_dps"
CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS = "mapped_extra_state_attribute_mappings"

# light
CONF_BRIGHTNESS_LOWER = "brightness_lower"
CONF_BRIGHTNESS_UPPER = "brightness_upper"
CONF_BRIGHTNESS_STEP = "brightness_step"
CONF_BRIGHTNESS_NULL_VALUE = "brightness_null_value"
CONF_COLOR_BRIGHTNESS_LOWER = "color_brightness_lower"
CONF_COLOR_BRIGHTNESS_UPPER = "color_brightness_upper"
CONF_COLOR = "color"
CONF_COLOR_RGB_ENCODING = "color_rgb_encoding"
CONF_WHITE_MODE = "white_mode"
CONF_EFFECT = "effect"
CONF_EFFECT_VALUES = "effect_values"
CONF_COLOR_MODE = "color_mode"
CONF_COLOR_MODE_SET = "color_mode_set"
CONF_COLOR_TEMP_MIN_KELVIN = "color_temp_min_kelvin"
CONF_COLOR_TEMP_MAX_KELVIN = "color_temp_max_kelvin"
CONF_COLOR_TEMP_REVERSE = "color_temp_reverse"
CONF_MUSIC_MODE = "music_mode"
CONF_SCENE_VALUES = "scene_values"

# switch
CONF_CURRENT = "current"
CONF_CURRENT_CONSUMPTION = "current_consumption"
CONF_VOLTAGE = "voltage"

# cover
CONF_COMMANDS_SET = "commands_set"
CONF_POSITIONING_MODE = "positioning_mode"
CONF_CURRENT_POSITION_DP = "current_position_dp"
CONF_SET_POSITION_DP = "set_position_dp"
CONF_POSITION_INVERTED = "position_inverted"
CONF_SPAN_TIME = "span_time"
CONF_COVER_COMMAND_VALUES = "cover_command_values"
CONF_COVER_ACTION_DP = "cover_action_dp"
CONF_COVER_ACTION_VALUES = "cover_action_values"
CONF_COVER_OPEN_DP = "cover_open_dp"
CONF_COVER_OPEN_VALUES = "cover_open_values"
CONF_SET_POSITION_MIN = "set_position_min"
CONF_SET_POSITION_MAX = "set_position_max"
CONF_SET_POSITION_STEP = "set_position_step"
CONF_SET_POSITION_INVERTED = "set_position_inverted"
CONF_CURRENT_POSITION_MIN = "current_position_min"
CONF_CURRENT_POSITION_MAX = "current_position_max"
CONF_CURRENT_POSITION_INVERTED = "current_position_inverted"
CONF_TILT_POSITION_DP = "tilt_position_dp"
CONF_TILT_POSITION_MIN = "tilt_position_min"
CONF_TILT_POSITION_MAX = "tilt_position_max"
CONF_TILT_POSITION_STEP = "tilt_position_step"
CONF_TILT_POSITION_INVERTED = "tilt_position_inverted"

# fan
CONF_FAN_SPEED_CONTROL = "fan_speed_control"
CONF_FAN_OSCILLATING_CONTROL = "fan_oscillating_control"
CONF_FAN_SPEED_MIN = "fan_speed_min"
CONF_FAN_SPEED_MAX = "fan_speed_max"
CONF_FAN_ORDERED_LIST = "fan_speed_ordered_list"
CONF_FAN_DIRECTION = "fan_direction"
CONF_FAN_DIRECTION_FWD = "fan_direction_forward"
CONF_FAN_DIRECTION_REV = "fan_direction_reverse"
CONF_FAN_DPS_TYPE = "fan_dps_type"
CONF_FAN_PRESET_DP = "fan_preset_dp"
CONF_FAN_PRESET_VALUES = "fan_preset_values"
CONF_FAN_OSCILLATING_ON = "fan_oscillating_on"
CONF_FAN_OSCILLATING_OFF = "fan_oscillating_off"

# sensor
CONF_SCALING = "scaling"

# binary sensor
CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"

# climate
CONF_TARGET_TEMPERATURE_DP = "target_temperature_dp"
CONF_AWAY_TEMPERATURE_DP = "away_temperature_dp"
CONF_CURRENT_TEMPERATURE_DP = "current_temperature_dp"
CONF_TEMPERATURE_STEP = "temperature_step"
CONF_MAX_TEMP_DP = "max_temperature_dp"
CONF_MIN_TEMP_DP = "min_temperature_dp"
CONF_MAX_TEMP_PRECISION = "max_temperature_precision"
CONF_MIN_TEMP_PRECISION = "min_temperature_precision"
CONF_TEMP_MAX = "max_temperature_const"
CONF_TEMP_MIN = "min_temperature_const"
CONF_PRECISION = "precision"
CONF_TARGET_PRECISION = "target_precision"
CONF_HVAC_MODE_DP = "hvac_mode_dp"
CONF_HVAC_MODE_SET = "hvac_mode_set"
CONF_HVAC_MODE_VALUES = "hvac_mode_values"
CONF_HVAC_FAN_MODE_DP = "hvac_fan_mode_dp"
CONF_HVAC_FAN_MODE_SET = "hvac_fan_mode_set"
CONF_HVAC_FAN_MODE_VALUES = "hvac_fan_mode_values"
CONF_HVAC_SWING_MODE_DP = "hvac_swing_mode_dp"
CONF_HVAC_SWING_MODE_SET = "hvac_swing_mode_set"
CONF_HVAC_SWING_MODE_VALUES = "hvac_swing_mode_values"
CONF_HVAC_SWING_HORIZONTAL_MODE_DP = "hvac_swing_horizontal_mode_dp"
CONF_HVAC_SWING_HORIZONTAL_MODE_VALUES = "hvac_swing_horizontal_mode_values"
CONF_PRESET_DP = "preset_dp"
CONF_PRESET_SET = "preset_set"
CONF_PRESET_VALUES = "preset_values"
CONF_HEURISTIC_ACTION = "heuristic_action"
CONF_HVAC_ACTION_DP = "hvac_action_dp"
CONF_HVAC_ACTION_SET = "hvac_action_set"
CONF_ECO_DP = "eco_dp"
CONF_ECO_VALUE = "eco_value"
CONF_HVAC_ACTION_VALUES = "hvac_action_values"
CONF_TARGET_TEMPERATURE_LOW_DP = "target_temperature_low_dp"
CONF_TARGET_TEMPERATURE_HIGH_DP = "target_temperature_high_dp"
CONF_TARGET_TEMPERATURE_LOW_PRECISION = "target_temperature_low_precision"
CONF_TARGET_TEMPERATURE_HIGH_PRECISION = "target_temperature_high_precision"
CONF_TARGET_HUMIDITY_DP = "target_humidity_dp"
CONF_CURRENT_HUMIDITY_DP = "current_humidity_dp"
CONF_TARGET_HUMIDITY_PRECISION = "target_humidity_precision"
CONF_CURRENT_HUMIDITY_PRECISION = "current_humidity_precision"
CONF_HUMIDITY_MIN = "min_humidity_const"
CONF_HUMIDITY_MAX = "max_humidity_const"
CONF_TEMPERATURE_UNIT_DP = "temperature_unit_dp"
CONF_TEMPERATURE_UNIT_VALUES = "temperature_unit_values"

# vacuum
CONF_POWERGO_DP = "powergo_dp"
CONF_IDLE_STATUS_VALUE = "idle_status_value"
CONF_RETURNING_STATUS_VALUE = "returning_status_value"
CONF_DOCKED_STATUS_VALUE = "docked_status_value"
CONF_BATTERY_DP = "battery_dp"
CONF_MODE_DP = "mode_dp"
CONF_MODES = "modes"
CONF_FAN_SPEED_DP = "fan_speed_dp"
CONF_FAN_SPEEDS = "fan_speeds"
CONF_CLEAN_TIME_DP = "clean_time_dp"
CONF_CLEAN_AREA_DP = "clean_area_dp"
CONF_CLEAN_RECORD_DP = "clean_record_dp"
CONF_LOCATE_DP = "locate_dp"
CONF_FAULT_DP = "fault_dp"
CONF_PAUSED_STATE = "paused_state"
CONF_RETURN_MODE = "return_mode"
CONF_STOP_STATUS = "stop_status"
CONF_VACUUM_STATUS_DP = "vacuum_status_dp"
CONF_VACUUM_STATUS_VALUES = "vacuum_status_values"
CONF_VACUUM_COMMAND_DP = "vacuum_command_dp"
CONF_VACUUM_COMMAND_VALUES = "vacuum_command_values"
CONF_VACUUM_ACTIVATE_DP = "vacuum_activate_dp"
CONF_VACUUM_ACTIVATE_ON = "vacuum_activate_on"
CONF_VACUUM_ACTIVATE_OFF = "vacuum_activate_off"
CONF_VACUUM_POWER_DP = "vacuum_power_dp"
CONF_VACUUM_POWER_ON = "vacuum_power_on"
CONF_VACUUM_POWER_OFF = "vacuum_power_off"
CONF_VACUUM_DIRECTION_DP = "vacuum_direction_dp"
CONF_VACUUM_DIRECTION_VALUES = "vacuum_direction_values"
CONF_VACUUM_FAN_SPEED_VALUES = "vacuum_fan_speed_values"
CONF_VACUUM_LOCATE_ON = "vacuum_locate_on"

# button
CONF_BUTTON_PRESS_VALUE = "button_press_value"

# text
CONF_TEXT_MIN = "text_min"
CONF_TEXT_MAX = "text_max"
CONF_TEXT_PATTERN = "text_pattern"
CONF_TEXT_MODE = "text_mode"

# valve
CONF_VALVE_SWITCH_DP = "valve_switch_dp"
CONF_VALVE_CURRENT_POSITION_DP = "valve_current_position_dp"
CONF_VALVE_POSITION_CONTROL = "valve_position_control"
CONF_VALVE_POSITION_MIN = "valve_position_min"
CONF_VALVE_POSITION_MAX = "valve_position_max"
CONF_VALVE_POSITION_INVERTED = "valve_position_inverted"
CONF_VALVE_OPEN_VALUE = "valve_open_value"
CONF_VALVE_CLOSED_VALUE = "valve_closed_value"
CONF_VALVE_SWITCH_ON = "valve_switch_on"
CONF_VALVE_SWITCH_OFF = "valve_switch_off"

# lock
CONF_LOCK_COMMAND_VALUES = "lock_command_values"
CONF_LOCK_STATE_DP = "lock_state_dp"
CONF_LOCK_STATE_VALUES = "lock_state_values"
CONF_LOCK_OPEN_DP = "lock_open_dp"
CONF_LOCK_OPEN_VALUES = "lock_open_values"
CONF_LOCK_OPEN_WRITABLE = "lock_open_writable"
CONF_LOCK_JAMMED_DP = "lock_jammed_dp"
CONF_LOCK_JAMMED_VALUES = "lock_jammed_values"

# humidifier
CONF_HUMIDIFIER_SWITCH_DP = "humidifier_switch_dp"
CONF_HUMIDIFIER_SWITCH_ON = "humidifier_switch_on"
CONF_HUMIDIFIER_SWITCH_OFF = "humidifier_switch_off"
CONF_HUMIDIFIER_CURRENT_HUMIDITY_DP = "humidifier_current_humidity_dp"
CONF_HUMIDIFIER_TARGET_HUMIDITY_DP = "humidifier_target_humidity_dp"
CONF_HUMIDIFIER_HUMIDITY_MIN = "humidifier_humidity_min"
CONF_HUMIDIFIER_HUMIDITY_MAX = "humidifier_humidity_max"
CONF_HUMIDIFIER_HUMIDITY_STEP = "humidifier_humidity_step"
CONF_HUMIDIFIER_HUMIDITY_SCALING = "humidifier_humidity_scaling"
CONF_HUMIDIFIER_MODE_DP = "humidifier_mode_dp"
CONF_HUMIDIFIER_MODE_VALUES = "humidifier_mode_values"
CONF_HUMIDIFIER_ACTION_DP = "humidifier_action_dp"
CONF_HUMIDIFIER_ACTION_VALUES = "humidifier_action_values"

# time
CONF_TIME_HOUR_DP = "time_hour_dp"
CONF_TIME_MINUTE_DP = "time_minute_dp"
CONF_TIME_SECOND_DP = "time_second_dp"
CONF_TIME_HMS_DP = "time_hms_dp"
CONF_TIME_HMS_FORMAT = "time_hms_format"

# water heater
CONF_WATER_HEATER_POWER_DP = "water_heater_power_dp"
CONF_WATER_HEATER_POWER_ON = "water_heater_power_on"
CONF_WATER_HEATER_POWER_OFF = "water_heater_power_off"
CONF_WATER_HEATER_CURRENT_TEMPERATURE_DP = "water_heater_current_temperature_dp"
CONF_WATER_HEATER_TARGET_TEMPERATURE_DP = "water_heater_target_temperature_dp"
CONF_WATER_HEATER_MIN_TEMPERATURE_DP = "water_heater_min_temperature_dp"
CONF_WATER_HEATER_MAX_TEMPERATURE_DP = "water_heater_max_temperature_dp"
CONF_WATER_HEATER_TEMPERATURE_SCALING = "water_heater_temperature_scaling"
CONF_WATER_HEATER_TEMPERATURE_MIN = "water_heater_temperature_min"
CONF_WATER_HEATER_TEMPERATURE_MAX = "water_heater_temperature_max"
CONF_WATER_HEATER_TEMPERATURE_STEP = "water_heater_temperature_step"
CONF_WATER_HEATER_TEMPERATURE_UNIT = "water_heater_temperature_unit"
CONF_WATER_HEATER_TEMPERATURE_UNIT_DP = "water_heater_temperature_unit_dp"
CONF_WATER_HEATER_TEMPERATURE_UNIT_VALUES = "water_heater_temperature_unit_values"
CONF_WATER_HEATER_MODE_DP = "water_heater_mode_dp"
CONF_WATER_HEATER_MODE_VALUES = "water_heater_mode_values"
CONF_WATER_HEATER_AWAY_DP = "water_heater_away_dp"
CONF_WATER_HEATER_AWAY_ON = "water_heater_away_on"
CONF_WATER_HEATER_AWAY_OFF = "water_heater_away_off"
CONF_WATER_HEATER_AWAY_MODE = "water_heater_away_mode"
CONF_WATER_HEATER_DEFAULT_MODE = "water_heater_default_mode"

# siren
CONF_SIREN_SWITCH_DP = "siren_switch_dp"
CONF_SIREN_SWITCH_ON = "siren_switch_on"
CONF_SIREN_SWITCH_OFF = "siren_switch_off"
CONF_SIREN_TONE_DP = "siren_tone_dp"
CONF_SIREN_TONE_VALUES = "siren_tone_values"
CONF_SIREN_DEFAULT_TONE = "siren_default_tone"
CONF_SIREN_DURATION_DP = "siren_duration_dp"
CONF_SIREN_DURATION_SCALING = "siren_duration_scaling"
CONF_SIREN_VOLUME_DP = "siren_volume_dp"
CONF_SIREN_VOLUME_VALUES = "siren_volume_values"
CONF_SIREN_VOLUME_MIN = "siren_volume_min"
CONF_SIREN_VOLUME_MAX = "siren_volume_max"

# alarm control panel
CONF_ALARM_STATE_DP = "alarm_state_dp"
CONF_ALARM_STATE_VALUES = "alarm_state_values"
CONF_ALARM_TRIGGER_DP = "alarm_trigger_dp"
CONF_ALARM_TRIGGER_ON = "alarm_trigger_on"
CONF_ALARM_TRIGGER_OFF = "alarm_trigger_off"

# event
CONF_EVENT_DP = "event_dp"
CONF_EVENT_TYPES = "event_types"
CONF_EVENT_DEVICE_CLASS = "event_device_class"

# camera
CONF_CAMERA_SWITCH_DP = "camera_switch_dp"
CONF_CAMERA_SWITCH_ON = "camera_switch_on"
CONF_CAMERA_SWITCH_OFF = "camera_switch_off"
CONF_CAMERA_SNAPSHOT_DP = "camera_snapshot_dp"
CONF_CAMERA_SNAPSHOT_ENCODING = "camera_snapshot_encoding"
CONF_CAMERA_RECORD_DP = "camera_record_dp"
CONF_CAMERA_RECORD_ON = "camera_record_on"
CONF_CAMERA_RECORD_OFF = "camera_record_off"
CONF_CAMERA_MOTION_DP = "camera_motion_dp"
CONF_CAMERA_MOTION_ON = "camera_motion_on"
CONF_CAMERA_MOTION_OFF = "camera_motion_off"

# datetime
CONF_DATETIME_TIMESTAMP_DP = "datetime_timestamp_dp"
CONF_DATETIME_TIMESTAMP_SCALING = "datetime_timestamp_scaling"
CONF_DATETIME_TIMEZONE = "datetime_timezone"
CONF_DATETIME_YEAR_DP = "datetime_year_dp"
CONF_DATETIME_MONTH_DP = "datetime_month_dp"
CONF_DATETIME_DAY_DP = "datetime_day_dp"
CONF_DATETIME_HOUR_DP = "datetime_hour_dp"
CONF_DATETIME_MINUTE_DP = "datetime_minute_dp"
CONF_DATETIME_SECOND_DP = "datetime_second_dp"

# lawn mower
CONF_LAWN_MOWER_ACTIVITY_DP = "lawn_mower_activity_dp"
CONF_LAWN_MOWER_ACTIVITY_VALUES = "lawn_mower_activity_values"
CONF_LAWN_MOWER_COMMAND_DP = "lawn_mower_command_dp"
CONF_LAWN_MOWER_COMMAND_VALUES = "lawn_mower_command_values"

# remote
CONF_REMOTE_SEND_DP = "remote_send_dp"
CONF_REMOTE_RECEIVE_DP = "remote_receive_dp"
CONF_REMOTE_CONTROL_DP = "remote_control_dp"
CONF_REMOTE_DELAY_DP = "remote_delay_dp"
CONF_REMOTE_CODE_TYPE_DP = "remote_code_type_dp"
CONF_REMOTE_CODE_TYPE_VALUE = "remote_code_type_value"
CONF_REMOTE_SEND_COMMAND = "remote_send_command"
CONF_REMOTE_RF_SEND_COMMAND = "remote_rf_send_command"
CONF_REMOTE_LEARN_COMMAND = "remote_learn_command"
CONF_REMOTE_LEARN_EXIT_COMMAND = "remote_learn_exit_command"
CONF_REMOTE_RF_LEARN_COMMAND = "remote_rf_learn_command"
CONF_REMOTE_RF_LEARN_EXIT_COMMAND = "remote_rf_learn_exit_command"

# infrared
CONF_INFRARED_SEND_DP = "infrared_send_dp"
CONF_INFRARED_CONTROL_DP = "infrared_control_dp"
CONF_INFRARED_CODE_TYPE_DP = "infrared_code_type_dp"
CONF_INFRARED_CODE_TYPE_VALUE = "infrared_code_type_value"
CONF_INFRARED_SEND_COMMAND = "infrared_send_command"

# number
CONF_MIN_VALUE = "min_value"
CONF_MAX_VALUE = "max_value"
CONF_STEPSIZE_VALUE = "step_size"

# select
CONF_OPTIONS = "select_options"
CONF_OPTIONS_FRIENDLY = "select_options_friendly"

# States
ATTR_STATE = "raw_state"
CONF_RESTORE_ON_RECONNECT = "restore_on_reconnect"

# Remote device catalog
DATA_DEVICE_CATALOG = "device_catalog"
