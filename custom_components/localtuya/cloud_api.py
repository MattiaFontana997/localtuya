"""Async client for Tuya Cloud APIs."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

from aiohttp import ClientError, ClientTimeout

from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=15)

SUCCESS = "ok"


def calc_sign(msg: str, key: str) -> str:
    """Calculate a Tuya HMAC-SHA256 signature."""
    return hmac.new(
        key.encode("latin-1"),
        msg.encode("latin-1"),
        hashlib.sha256,
    ).hexdigest().upper()


class TuyaCloudApi:
    """Client for the Tuya Cloud API."""

    def __init__(
        self,
        hass,
        region_code,
        client_id,
        secret,
        user_id,
    ) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._base_url = (
            f"https://openapi.tuya{region_code}.com"
        )

        self._client_id = client_id or ""
        self._secret = secret or ""
        self._user_id = user_id or ""

        self._access_token = ""

        self._session = async_get_clientsession(hass)

        self.device_list: dict[str, dict[str, Any]] = {}

        self.device_specifications: dict[
            str,
            dict[str, Any],
        ] = {}

    def generate_payload(
        self,
        method: str,
        timestamp: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str = "",
    ) -> str:
        """Generate the canonical Tuya signing payload."""
        headers = headers or {}

        payload = (
            self._client_id
            + self._access_token
            + timestamp
        )

        payload += method.upper() + "\n"

        payload += hashlib.sha256(
            body.encode("utf-8")
        ).hexdigest()

        signature_headers = headers.get(
            "Signature-Headers",
            "",
        )

        signed_headers = "".join(
            f"{key}:{headers[key]}\n"
            for key in signature_headers.split(":")
            if key and key in headers
        )

        payload += (
            "\n"
            + signed_headers
            + "\n"
            + url
        )

        return payload

    async def async_make_request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Perform one signed asynchronous request."""
        method = method.upper()

        request_headers = dict(headers or {})

        body_text = ""

        if body is not None:
            body_text = json.dumps(
                body,
                separators=(",", ":"),
                ensure_ascii=False,
            )

            request_headers.setdefault(
                "Content-Type",
                "application/json",
            )

        timestamp = str(int(time.time() * 1000))

        payload = self.generate_payload(
            method,
            timestamp,
            url,
            request_headers,
            body_text,
        )

        auth_headers = {
            "client_id": self._client_id,
            "access_token": self._access_token,
            "sign": calc_sign(
                payload,
                self._secret,
            ),
            "t": timestamp,
            "sign_method": "HMAC-SHA256",
        }

        final_headers = {
            **auth_headers,
            **request_headers,
        }

        full_url = self._base_url + url

        try:
            async with self._session.request(
                method,
                full_url,
                headers=final_headers,
                data=(
                    body_text
                    if body is not None
                    else None
                ),
                timeout=REQUEST_TIMEOUT,
            ) as response:
                status = response.status
                response_text = await response.text()

        except (ClientError, TimeoutError) as exc:
            raise ConnectionError(
                f"Tuya Cloud request failed: {exc}"
            ) from exc

        if not response_text:
            return status, {}

        try:
            response_data = json.loads(
                response_text
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Tuya Cloud returned invalid JSON"
            ) from exc

        if not isinstance(response_data, dict):
            raise ValueError(
                "Tuya Cloud returned an unexpected response"
            )

        return status, response_data

    @staticmethod
    def _api_error(
        status: int,
        data: dict[str, Any],
    ) -> str | None:
        """Return a human-readable API error."""
        if not 200 <= status < 300:
            return f"Request failed, status {status}"

        if not data.get("success", False):
            return (
                f"Error {data.get('code', 'unknown')}: "
                f"{data.get('msg', 'Unknown Tuya Cloud error')}"
            )

        return None

    async def async_get_access_token(self) -> str:
        """Obtain a valid access token."""
        try:
            status, data = await self.async_make_request(
                "GET",
                "/v1.0/token?grant_type=1",
            )
        except (ConnectionError, ValueError) as exc:
            return str(exc)

        if error := self._api_error(status, data):
            return error

        result = data.get("result")

        if (
            not isinstance(result, dict)
            or not isinstance(
                result.get("access_token"),
                str,
            )
        ):
            return (
                "Tuya Cloud token response did not "
                "contain an access token"
            )

        self._access_token = result["access_token"]

        return SUCCESS

    async def async_get_devices_list(self) -> str:
        """Obtain devices associated with the configured user."""
        try:
            status, data = await self.async_make_request(
                "GET",
                f"/v1.0/users/{self._user_id}/devices",
            )
        except (ConnectionError, ValueError) as exc:
            return str(exc)

        if error := self._api_error(status, data):
            return error

        result = data.get("result")

        if not isinstance(result, list):
            return (
                "Tuya Cloud device list response "
                "did not contain a device list"
            )

        self.device_list = {
            device["id"]: device
            for device in result
            if (
                isinstance(device, dict)
                and isinstance(
                    device.get("id"),
                    str,
                )
            )
        }

        return SUCCESS

    async def async_get_device_specification(
        self,
        device_id: str,
    ) -> tuple[str, dict[str, Any] | None]:
        """Get Tuya function/status specification for one device."""
        endpoints = (
            f"/v1.0/iot-03/devices/{device_id}/specification",
            f"/v1.1/devices/{device_id}/specifications",
        )

        last_error = (
            "Unable to retrieve device specification"
        )

        for url in endpoints:
            try:
                status, data = await self.async_make_request(
                    "GET",
                    url,
                )
            except (ConnectionError, ValueError) as exc:
                last_error = str(exc)
                continue

            if error := self._api_error(status, data):
                last_error = error
                continue

            result = data.get("result")

            if not isinstance(result, dict):
                last_error = (
                    "Tuya Cloud specification response "
                    "did not contain a specification"
                )
                continue

            self.device_specifications[device_id] = result

            return SUCCESS, result

        return last_error, None
