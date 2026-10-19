"""Variable sets to read many ETA variables with a single request."""

import asyncio
from collections.abc import Iterable
import logging
import re
from xml.parsers.expat import ExpatError

from aiohttp import ClientError, ClientResponseError
import xmltodict

from .api_client import APIClient, endpoint_key, resource_path

_LOGGER = logging.getLogger(__name__)

# Errors that mean the set is unusable, e.g. because the terminal rebooted and
# lost it, or the terminal answered with something other than a variable set.
VARIABLE_SET_ERRORS = (ClientError, TimeoutError, ExpatError, KeyError, TypeError)


class VariableSetUnsupportedError(Exception):
    """The terminal refused to create the variable set."""


class VariableSet:
    """A named set of variables on the terminal (spec section 5, /user/vars).

    Reading the set returns all of its variables at once instead of one request
    per variable. The terminal does not persist sets, so the set is created on
    first use and recreated when reading it fails, e.g. after a reboot.
    """

    def __init__(self, name: str, uris: Iterable[str]) -> None:
        """Initialize the set; name must match [a-zA-Z0-9]+."""
        if not re.fullmatch(r"[a-zA-Z0-9]+", name):
            raise ValueError(f"Invalid variable set name {name!r}")
        self.name = name
        self.uris = list(dict.fromkeys(uris))
        self.supported = True
        self._created = False

    @property
    def _path(self) -> str:
        return f"/user/vars/{self.name}"

    async def _create(self, http: APIClient) -> None:
        # A set left over from before a restart may hold other variables.
        await self.delete(http)
        try:
            await http.put_request(self._path)
        except ClientResponseError as err:
            self.supported = False
            raise VariableSetUnsupportedError(
                f"The terminal refused to create variable set {self.name}: {err}"
            ) from err

        results = await asyncio.gather(
            *(http.put_request(resource_path(self._path, uri)) for uri in self.uris),
            return_exceptions=True,
        )
        for uri, result in zip(self.uris, results, strict=True):
            # Such variables are missing from reads and count as failed.
            if isinstance(result, BaseException):
                _LOGGER.debug(
                    "Could not add %s to variable set %s: %r", uri, self.name, result
                )
        self._created = True

    async def _read(self, http: APIClient) -> dict[str, dict]:
        response = await http.get_request(self._path)
        variable_set = xmltodict.parse(await response.text())["eta"]["vars"]
        variables = (variable_set or {}).get("variable", [])
        if isinstance(variables, dict):
            variables = [variables]
        by_key = {endpoint_key(variable["@uri"]): variable for variable in variables}
        return {
            uri: by_key[endpoint_key(uri)]
            for uri in self.uris
            if endpoint_key(uri) in by_key
        }

    async def read(self, http: APIClient) -> dict[str, dict]:
        """Return the raw <variable> elements keyed by the URIs of the set."""
        if not self._created:
            await self._create(http)
            return await self._read(http)
        try:
            return await self._read(http)
        except VARIABLE_SET_ERRORS as err:
            _LOGGER.debug("Recreating variable set %s after %r", self.name, err)
            self._created = False
            await self._create(http)
            return await self._read(http)

    async def delete(self, http: APIClient) -> None:
        """Delete the set on the terminal, as the spec asks clients to do."""
        self._created = False
        try:
            await http.delete_request(self._path)
        except (ClientError, TimeoutError) as err:
            # Usually because the set does not exist
            _LOGGER.debug("Could not delete variable set %s: %r", self.name, err)
