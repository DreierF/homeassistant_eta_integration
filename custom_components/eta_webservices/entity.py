"""Common entity definitions for the ETA sensor integration."""

from abc import abstractmethod
from typing import Any, Generic, TypeVar, cast

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .api import EtaAPI, ETAEndpoint
from .const import (
    DEFAULT_MAX_PARALLEL_REQUESTS,
    ENTRY_ID,
    MAX_PARALLEL_REQUESTS,
    REQUEST_SEMAPHORE,
)
from .coordinator import ETAErrorUpdateCoordinator
from .utils import create_device_info, entity_unique_id

_EntityT = TypeVar("_EntityT")


class EtaEntity(Entity):
    """Common entity definition for all ETA entities."""

    _attr_has_entity_name = True

    def __init__(  # noqa: D107
        self,
        config: dict,
        hass: HomeAssistant,
        key: str,
        endpoint_info: ETAEndpoint,
    ) -> None:
        self.session = async_get_clientsession(hass)
        self.host = config.get(CONF_HOST, "")
        self.port = config.get(CONF_PORT, "")
        self.uri = endpoint_info["url"]
        self.max_parallel_requests = int(
            config.get(MAX_PARALLEL_REQUESTS, DEFAULT_MAX_PARALLEL_REQUESTS)
        )
        self.request_semaphore = config.get(REQUEST_SEMAPHORE)

        # The functional block becomes the device, the rest of the menu path the
        # entity name, e.g. "Kessel > Zähler > Volllaststunden" is the entity
        # "Zähler > Volllaststunden" of the device "Kessel".
        device_name, separator, name = endpoint_info["friendly_name"].partition(" > ")
        if not separator:
            device_name, name = None, endpoint_info["friendly_name"]
        self._attr_name = name
        self._attr_device_info = create_device_info(config[ENTRY_ID], device_name)
        self._attr_unique_id = entity_unique_id(config[ENTRY_ID], key)

    def _create_eta_client(self) -> EtaAPI:
        # Reuse configured concurrency settings for all entity-level write operations.
        return EtaAPI(
            self.session,
            self.host,
            self.port,
            max_concurrent_requests=self.max_parallel_requests,
            request_semaphore=self.request_semaphore,
        )


class EtaCoordinatedSensorEntity(
    EtaEntity,
    CoordinatorEntity[DataUpdateCoordinator[dict[str, float | str | bool]]],
    Generic[_EntityT],
):
    """Common coordinated sensor entity definition for normal ETA sensors."""

    def __init__(  # noqa: D107
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        config: dict,
        hass: HomeAssistant,
        key: str,
        endpoint_info: ETAEndpoint,
    ) -> None:
        EtaEntity.__init__(self, config, hass, key, endpoint_info)
        CoordinatorEntity.__init__(self, coordinator)  # pyright: ignore[reportArgumentType]

        self._attr_should_poll = False
        data = self.coordinator.data.get(self.uri)
        self.handle_data_updates(cast(_EntityT, data) if data is not None else None)

    @abstractmethod
    def handle_data_updates(self, data: _EntityT | None) -> None:  # noqa: D102
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        data = self.coordinator.data.get(self.uri)
        self.handle_data_updates(cast(_EntityT, data) if data is not None else None)
        super()._handle_coordinator_update()


class EtaErrorEntity(CoordinatorEntity[ETAErrorUpdateCoordinator]):
    """Entity definition for all ETA error sensors."""

    _attr_has_entity_name = True

    def __init__(  # noqa: D107
        self,
        coordinator: ETAErrorUpdateCoordinator,
        config: dict,
        unique_id_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{config[ENTRY_ID]}_{unique_id_suffix}"
        self._attr_device_info = create_device_info(config[ENTRY_ID], None)

    @abstractmethod
    def handle_data_updates(self, data) -> None:  # noqa: D102
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self.handle_data_updates(self.coordinator.data)
        super()._handle_coordinator_update()
