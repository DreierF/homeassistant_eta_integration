"""Constants for the ETA integration."""

NAME = "eta_webservices"
DOMAIN = "eta_webservices"
ISSUE_URL = "https://github.com/Tidone/homeassistant_eta_integration/issues"


FLOAT_DICT = "FLOAT_DICT"
SWITCHES_DICT = "SWITCHES_DICT"
TEXT_DICT = "TEXT_DICT"
WRITABLE_DICT = "WRITABLE_DICT"
PENDING_DICT = "PENDING_DICT"
CHOSEN_FLOAT_SENSORS = "chosen_float_sensors"
CHOSEN_SWITCHES = "chosen_switches"
CHOSEN_TEXT_SENSORS = "chosen_text_sensors"
CHOSEN_WRITABLE_SENSORS = "chosen_writable_sensors"
CHOSEN_PENDING_SENSORS = "chosen_pending_sensors"

FORCE_LEGACY_MODE = "force_legacy_mode"
ENABLE_DEBUG_LOGGING = "enable_debug_logging"
AUTO_SELECT_ALL_ENTITIES = "auto_select_all_entities"

OPTIONS_UPDATE_SENSOR_VALUES = "update_sensor_values"
OPTIONS_ENUMERATE_NEW_ENDPOINTS = "enumerate_new_endpoints"
OPTIONS_UPDATE_ACTION = "options_update_action"
OPTIONS_ACTION_PARALLEL_ONLY = "update_parallel_requests"
OPTIONS_ACTION_UPDATE_SELECTED = "update_selected_entities"
OPTIONS_ACTION_REDISCOVER_AND_UPDATE = "rediscover_and_update_entities"
ADVANCED_OPTIONS_IGNORE_DECIMAL_PLACES_RESTRICTION = (
    "ignore_decimal_places_restriction_for_writable_entities"
)

ERROR_UPDATE_COORDINATOR = "error_update_coordinator"
WRITABLE_UPDATE_COORDINATOR = "writable_update_coordinator"
SENSOR_UPDATE_COORDINATOR = "sensor_update_coordinator"
PENDING_UPDATE_COORDINATOR = "pending_update_coordinator"
LAST_COORDINATOR_WARNING_TIMESTAMP = "last_coordinator_warning_timestamp"

CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT = "minutes_since_midnight"
CUSTOM_UNIT_TIMESLOT = "timeslot"
CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE = "timeslot_plus_temperature"
CUSTOM_UNIT_UNITLESS = "unitless"
# Writable variables with named values, e.g. "Frei" and "Gesperrt"
CUSTOM_UNIT_SELECT = "select"
CUSTOM_UNITS = [
    CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT,
    CUSTOM_UNIT_TIMESLOT,
    CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE,
    CUSTOM_UNIT_UNITLESS,
    CUSTOM_UNIT_SELECT,
]

# Internal units which should not be shown to the user
INVISIBLE_UNITS = [
    CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT,
    CUSTOM_UNIT_TIMESLOT,
    CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE,
    CUSTOM_UNIT_UNITLESS,
    CUSTOM_UNIT_SELECT,
]

ENTRY_ID = "entry_id"
MAX_PARALLEL_REQUESTS = "max_parallel_requests"
REQUEST_SEMAPHORE = "request_semaphore"
UPDATE_INTERVAL = "update_interval"
PAUSE_COORDINATORS_START_TIMESTAMP = "pause_coordinators_start_timestamp"
PAUSE_COORDINATORS_MAX_DURATION = 10 * 60  # seconds

# Defaults
DEFAULT_NAME = DOMAIN
REQUEST_TIMEOUT = 60
DEFAULT_MAX_PARALLEL_REQUESTS = 5
DEFAULT_UPDATE_INTERVAL = 60  # seconds
COORDINATOR_WARNING_INTERVAL = (
    30 * 60
)  # seconds between coordinator performance warnings


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
