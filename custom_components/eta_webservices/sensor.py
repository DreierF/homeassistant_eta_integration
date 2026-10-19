"""Sensor platform for the ETA sensor integration in Home Assistant.

Help Links:
 Entity Source: https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/entity.py
 SensorEntity derives from Entity https://github.com/home-assistant/core/blob/dev/homeassistant/components/sensor/__init__.py


author nigl, Tidone
"""

from __future__ import annotations

from datetime import time
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import async_get_current_platform
from homeassistant.helpers.typing import VolDictType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ETAEndpoint, ETAError, ETAValidWritableValues
from .const import (
    CHOSEN_FLOAT_SENSORS,
    CHOSEN_TEXT_SENSORS,
    CHOSEN_WRITABLE_SENSORS,
    CUSTOM_UNIT_TIMESLOT,
    CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE,
    DOMAIN,
    ERROR_UPDATE_COORDINATOR,
    FLOAT_DICT,
    SENSOR_UPDATE_COORDINATOR,
    TEXT_DICT,
    WRITABLE_DICT,
    WRITABLE_UPDATE_COORDINATOR,
)
from .coordinator import (
    EtaConfigEntry,
    ETAErrorUpdateCoordinator,
    ETASensorUpdateCoordinator,
)
from .entity import EtaCoordinatedSensorEntity, EtaErrorEntity
from .utils import get_native_unit

_LOGGER = logging.getLogger(__name__)

WRITE_TIMESLOT_SCHEMA: VolDictType = {
    vol.Required("begin"): cv.time,
    vol.Required("end"): cv.time,
    vol.Optional("temperature"): vol.Coerce(float),
}

# Plain time slots report a raw value of 0. The spec requires a value on every
# time slot write, so this is sent back unchanged.
PLAIN_TIMESLOT_RAW_VALUE = 0


def _deduplicate_entities_by_unique_id(
    entities: list[SensorEntity],
) -> list[SensorEntity]:
    """Drop duplicate entities with identical unique IDs.

    In rare edge cases a sensor can temporarily end up in multiple categories
    in config data. Guard against duplicate entity registration at runtime.
    """
    deduplicated_entities: list[SensorEntity] = []
    seen_unique_ids: set[str] = set()

    for entity in entities:
        unique_id = entity.unique_id
        if unique_id is None:
            deduplicated_entities.append(entity)
            continue

        if unique_id in seen_unique_ids:
            _LOGGER.warning(
                "Skipping duplicate sensor entity with unique_id '%s' (entity_id: %s)",
                unique_id,
                entity.entity_id,
            )
            continue

        seen_unique_ids.add(unique_id)
        deduplicated_entities.append(entity)

    return deduplicated_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EtaConfigEntry,
    async_add_entities,
):
    """Setup sensors from a config entry created in the integrations UI."""
    config = config_entry.runtime_data

    sensor_coordinator = config[SENSOR_UPDATE_COORDINATOR]
    writable_coordinator = config[WRITABLE_UPDATE_COORDINATOR]

    chosen_float_sensors = config[CHOSEN_FLOAT_SENSORS]
    chosen_writable_sensors = config[CHOSEN_WRITABLE_SENSORS]
    # first add all normal float sensors
    sensors = [
        EtaFloatSensor(
            config,
            hass,
            entity,
            config[FLOAT_DICT][entity],
            sensor_coordinator
            if entity + "_writable" not in chosen_writable_sensors
            else writable_coordinator,
        )
        for entity in chosen_float_sensors
    ]

    chosen_text_sensors = config[CHOSEN_TEXT_SENSORS]
    # then add the text sensors, except for the timeslot sensors which get added in a separate loop below
    sensors.extend(
        [
            EtaTextSensor(
                config,
                hass,
                entity,
                config[TEXT_DICT][entity],
                sensor_coordinator
                if entity + "_writable" not in chosen_writable_sensors
                else writable_coordinator,
            )
            for entity in chosen_text_sensors
            if config[TEXT_DICT][entity]["unit"]
            not in [CUSTOM_UNIT_TIMESLOT, CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE]
        ]  # pyright: ignore[reportArgumentType]
    )
    # add the non-writable timeslot sensors first
    # breaking change: all timeslot sensors which are also selected as writable sensors will now be ignored
    # this leads to these sensors never being added to HA even if the user selects the "add all entities" option in the config or options flows.
    # This was done because their value representation is the same as the writable timeslot sensors, leading to duplicate entities with the same value
    sensors.extend(
        [
            EtaTimeslotSensor(
                config,
                hass,
                entity,
                config[TEXT_DICT][entity],
                sensor_coordinator,
                writable=False,
                should_be_disabled=entity + "_writable" in chosen_writable_sensors,
            )
            for entity in chosen_text_sensors
            if config[TEXT_DICT][entity]["unit"]
            in [CUSTOM_UNIT_TIMESLOT, CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE]
        ]  # pyright: ignore[reportArgumentType]
    )
    # then add the writable timeslot sensors
    # These share the same implementation as the text timeslot sensors above,
    # but accept the write_timeslot service call
    sensors.extend(
        [
            EtaTimeslotSensor(
                config,
                hass,
                entity,
                config[WRITABLE_DICT][entity],
                sensor_coordinator,
                writable=True,
            )
            for entity in chosen_writable_sensors
            if config[WRITABLE_DICT][entity]["unit"]
            in [CUSTOM_UNIT_TIMESLOT, CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE]
        ]  # pyright: ignore[reportArgumentType]
    )
    error_coordinator = config[ERROR_UPDATE_COORDINATOR]
    sensors.extend(
        [
            EtaNbrErrorsSensor(config, hass, error_coordinator),
            EtaLatestErrorSensor(config, hass, error_coordinator),
        ]  # pyright: ignore[reportArgumentType]
    )
    # Final safety net: avoid HA startup failures if config data still contains
    # the same unique_id in multiple sensor categories.
    sensors = _deduplicate_entities_by_unique_id(sensors)  # pyright: ignore[reportArgumentType]
    async_add_entities(sensors, update_before_add=False)

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        "write_timeslot", WRITE_TIMESLOT_SCHEMA, "async_write_timeslot"
    )


# Counters as (Fub-ID, Var-ID) of their CAN address. These IDs identify the
# variable type independently of the node number and the terminal language,
# e.g. 10021/12153 is "Volllaststunden" or "Full load hours" on every boiler.
COUNTER_VARIABLES = frozenset(
    {
        # Boiler: pellet consumption, operating times and event counters
        ("10021", "12012"),
        ("10021", "12013"),
        ("10021", "12014"),
        ("10021", "12016"),
        ("10021", "12017"),
        ("10021", "12018"),
        ("10021", "12081"),
        ("10021", "12082"),
        ("10021", "12153"),
        ("10021", "12154"),
        ("10021", "12155"),
        ("10021", "12156"),
        ("10021", "12157"),
        ("10021", "12299"),
        ("10021", "12323"),
        ("10021", "13642"),
        ("10021", "13643"),
        # Pellet store vacuum system
        ("10211", "13792"),
        ("10211", "13793"),
        ("10211", "13794"),
        ("10211", "13795"),
        # Water meter
        ("10531", "2274"),
    }
)


def _is_counter(uri: str) -> bool:
    """Return True if the variable at the CAN address is a known counter."""
    parts = uri.strip("/").split("/")
    return len(parts) == 5 and (parts[1], parts[4]) in COUNTER_VARIABLES


def _determine_state_class(
    uri: str, device_class: SensorDeviceClass | None
) -> SensorStateClass:
    # Energy and volume sensors can only be totals in HA
    if _is_counter(uri) or device_class in (
        SensorDeviceClass.ENERGY,
        SensorDeviceClass.VOLUME,
    ):
        return SensorStateClass.TOTAL_INCREASING
    return SensorStateClass.MEASUREMENT


def _determine_device_class(unit):
    unit_dict_eta = {
        "°C": SensorDeviceClass.TEMPERATURE,
        "W": SensorDeviceClass.POWER,
        "A": SensorDeviceClass.CURRENT,
        "Hz": SensorDeviceClass.FREQUENCY,
        "Pa": SensorDeviceClass.PRESSURE,
        "V": SensorDeviceClass.VOLTAGE,
        "W/m²": SensorDeviceClass.IRRADIANCE,
        "bar": SensorDeviceClass.PRESSURE,
        "kW": SensorDeviceClass.POWER,
        "kWh": SensorDeviceClass.ENERGY,
        "kg": SensorDeviceClass.WEIGHT,
        "mV": SensorDeviceClass.VOLTAGE,
        "s": SensorDeviceClass.DURATION,
        "%rH": SensorDeviceClass.HUMIDITY,
        "m³": SensorDeviceClass.VOLUME,
        "m³/h": SensorDeviceClass.VOLUME_FLOW_RATE,
    }

    if unit in unit_dict_eta:
        return unit_dict_eta[unit]

    return None


def _coerce_numeric_value(value: float | str | None) -> float | None:
    """Convert ETA values for numeric sensors, or return None if not numeric.

    ETA may temporarily return text placeholders (e.g. "---", "Aus") for
    sensors that are normally numeric. In that case we keep the entity type
    stable and publish an unavailable state for that update cycle.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)

    normalized_value = str(value).strip().replace(",", ".")
    if normalized_value == "":
        return None

    try:
        return float(normalized_value)
    except ValueError:
        return None


class EtaFloatSensor(SensorEntity, EtaCoordinatedSensorEntity[float]):
    """Representation of a Float Sensor."""

    def __init__(  # noqa: D107
        self,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
    ) -> None:
        _LOGGER.debug("ETA Integration - init float sensor")

        super().__init__(coordinator, config, hass, unique_id, endpoint_info)

        self._attr_device_class = _determine_device_class(endpoint_info["unit"])

        self._attr_native_unit_of_measurement = get_native_unit(endpoint_info["unit"])

        self._attr_state_class = _determine_state_class(
            endpoint_info["url"], self._attr_device_class
        )

    def handle_data_updates(self, data: float | str | None) -> None:  # noqa: D102
        numeric_value = _coerce_numeric_value(data)
        if numeric_value is None:
            _LOGGER.info(
                "Sensor %s received non-numeric value '%s'; setting state to unavailable",
                self.entity_id,
                data,
            )
            self._attr_native_value = None
            return
        self._attr_native_value = numeric_value


class EtaTextSensor(SensorEntity, EtaCoordinatedSensorEntity[str]):
    """Representation of a Text Sensor."""

    def __init__(  # noqa: D107
        self,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
    ) -> None:
        _LOGGER.debug("ETA Integration - init text sensor")

        super().__init__(coordinator, config, hass, unique_id, endpoint_info)

    def handle_data_updates(self, data: str | None) -> None:  # noqa: D102
        if data is None:
            _LOGGER.info(
                "Sensor %s received None value; setting state to unavailable",
                self.entity_id,
            )
        self._attr_native_value = data


class EtaTimeslotSensor(SensorEntity, EtaCoordinatedSensorEntity[str]):
    """Representation of a Text Sensor representing timeslots."""

    def __init__(  # noqa: D107
        self,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
        coordinator: ETASensorUpdateCoordinator,
        writable: bool,
        should_be_disabled: bool = False,
    ) -> None:
        _LOGGER.debug("ETA Integration - init timeslot sensor")

        self.temperature_unit = "°C"
        super().__init__(coordinator, config, hass, unique_id, endpoint_info)
        self.valid_values: ETAValidWritableValues = endpoint_info["valid_values"]  # pyright: ignore[reportAttributeAccessIssue]
        self.writable = writable
        self.has_temperature = (
            endpoint_info["unit"] == CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE
        )

        if should_be_disabled:
            entity_registry = er.async_get(hass)
            # Remove the entity from the list of deleted entities to allow re-adding it as disabled
            entity_registry.deleted_entities.pop(
                (SENSOR_DOMAIN, DOMAIN, self._attr_unique_id), None
            )
            self._attr_entity_registry_enabled_default = False

    async def async_write_timeslot(
        self, begin: time, end: time, temperature: float | None = None
    ) -> None:
        """Handle the write_timeslot service call.

        Times are rounded to the nearest quarter hour, so 23:59 ends the slot at
        midnight.
        """
        if not self.writable:
            raise ServiceValidationError(
                f"{self.entity_id} is not selected as a writable time slot"
            )
        if self.has_temperature and temperature is None:
            raise ServiceValidationError(
                f"{self.entity_id} needs a temperature for the time slot"
            )
        if not self.has_temperature and temperature is not None:
            raise ServiceValidationError(
                f"{self.entity_id} has no temperature for the time slot"
            )

        raw_value = PLAIN_TIMESLOT_RAW_VALUE
        # 0 °C is a valid temperature, so test against None
        if temperature is not None:
            if (
                temperature < self.valid_values["scaled_min_value"]
                or temperature > self.valid_values["scaled_max_value"]
            ):
                raise ServiceValidationError(
                    f"Temperature value out of bounds for entity {self.entity_id}"
                )
            raw_value = round(
                round(temperature, self.valid_values["dec_places"])
                * self.valid_values["scale_factor"]
            )

        raw_begin = round((begin.hour * 60 + begin.minute) / 15)
        raw_end = round((end.hour * 60 + end.minute) / 15)
        if raw_begin > raw_end:
            raise ServiceValidationError(
                f"Invalid timeslot for entity {self.entity_id}: begin is after end"
            )

        eta_client = self._create_eta_client()
        success = await eta_client.write_endpoint(
            self.uri, raw_value, raw_begin, raw_end
        )
        if not success:
            raise HomeAssistantError(
                f"Could not write value for entity {self.entity_id}, see log for details"
            )
        await self.coordinator.async_refresh()

    def _parse_timeslot_value(self, value: str) -> tuple[str, str, str | None]:
        """Parse a timeslot value string.

        Args:
            value: String in format "HH:MM - HH:MM" or "HH:MM - HH:MM <number>"

        Returns:
            Tuple of (start_time, end_time, optional_value)
            where optional_value is None if not present
        """
        # Split by " - " to separate start time from the rest
        parts = value.split("-")
        if len(parts) != 2:
            return "", "", None  # Invalid format

        start_time = parts[0].strip()

        # Split the second part by space to get end time and optional value
        end_parts = parts[1].strip().split()
        end_time = end_parts[0]

        # Check if there's a third value
        optional_value = end_parts[1] if len(end_parts) > 1 else None

        return start_time, end_time, optional_value

    def handle_data_updates(self, data: str | None) -> None:  # noqa: D102
        if data is None:
            _LOGGER.info(
                "Sensor %s received None value; setting state to unavailable",
                self.entity_id,
            )
            self._attr_native_value = None
            return

        start_time, end_time, temperature = self._parse_timeslot_value(str(data))

        if start_time == "" or end_time == "":
            self._attr_native_value = str(data)
            return

        if temperature:
            self._attr_native_value = (
                f"{start_time} - {end_time}: {temperature} {self.temperature_unit}"
            )
        else:
            self._attr_native_value = f"{start_time} - {end_time}"


class EtaNbrErrorsSensor(SensorEntity, EtaErrorEntity):
    """Representation of a sensor showing the number of active errors."""

    def __init__(  # noqa: D107
        self, config: dict, hass: HomeAssistant, coordinator: ETAErrorUpdateCoordinator
    ) -> None:
        super().__init__(coordinator, config, "nbr_active_errors")

        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_native_value = 0
        self._attr_native_unit_of_measurement = None

        self._attr_translation_key = "nbr_active_errors_sensor"

        self.handle_data_updates(self.coordinator.data)

    def handle_data_updates(self, data: list):  # noqa: D102
        self._attr_native_value = len(data)


class EtaLatestErrorSensor(SensorEntity, EtaErrorEntity):
    """Representation of a sensor showing the latest active error."""

    def __init__(  # noqa: D107
        self, config: dict, hass: HomeAssistant, coordinator: ETAErrorUpdateCoordinator
    ) -> None:
        super().__init__(coordinator, config, "latest_error")

        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self._attr_native_value = ""
        self._attr_native_unit_of_measurement = None

        self._attr_translation_key = "latest_error_sensor"

        self.handle_data_updates(self.coordinator.data)

    def handle_data_updates(self, data: list[ETAError]):  # noqa: D102
        if len(data) == 0:
            self._attr_native_value = "-"
            return

        sorted_errors = sorted(data, key=lambda d: d["time"])
        self._attr_native_value = sorted_errors[-1]["msg"]
