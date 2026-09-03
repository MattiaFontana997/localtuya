"""Tests for the asynchronous Tuya Cloud API client."""

import hashlib
import hmac
import unittest
from unittest.mock import (
    AsyncMock,
    call,
    patch,
)

from custom_components.localtuya.cloud_api import (
    SUCCESS,
    TuyaCloudApi,
    calc_sign,
)


class CloudApiTests(
    unittest.IsolatedAsyncioTestCase
):
    """Test Cloud API behavior without network access."""

    @staticmethod
    def _api():
        with patch(
            "custom_components.localtuya.cloud_api."
            "async_get_clientsession",
            return_value=object(),
        ):
            api = TuyaCloudApi(
                object(),
                "eu",
                "client",
                "secret",
                "user",
            )

        return api

    def test_calc_sign(self):
        """Tuya signatures are uppercase HMAC-SHA256."""
        expected = hmac.new(
            b"secret",
            b"message",
            hashlib.sha256,
        ).hexdigest().upper()

        self.assertEqual(
            calc_sign(
                "message",
                "secret",
            ),
            expected,
        )

    def test_generate_payload(self):
        """Canonical request payload contains signed headers."""
        api = self._api()
        api._access_token = "token"

        body = '{"x":1}'

        generated = (
            api.generate_payload(
                "POST",
                "123",
                "/v1.0/test",
                {
                    "Signature-Headers":
                        "area",
                    "area": "eu",
                },
                body,
            )
        )

        body_hash = hashlib.sha256(
            body.encode()
        ).hexdigest()

        expected = (
            "client"
            "token"
            "123"
            "POST\n"
            f"{body_hash}"
            "\n"
            "area:eu\n"
            "\n"
            "/v1.0/test"
        )

        self.assertEqual(
            generated,
            expected,
        )

    def test_specification_dp_validation(self):
        """Only positive numeric DP identifiers are usable."""
        self.assertTrue(
            TuyaCloudApi
            ._specification_has_dp_ids(
                {
                    "functions": [
                        {
                            "dp_id": "20",
                            "code":
                                "switch_led",
                        }
                    ]
                }
            )
        )

        self.assertFalse(
            TuyaCloudApi
            ._specification_has_dp_ids(
                {
                    "functions": [
                        {
                            "dp_id": True,
                        },
                        {
                            "id": 0,
                        },
                        {
                            "code":
                                "switch",
                        },
                    ]
                }
            )
        )

    async def test_specification_fallback(self):
        """v1.0 fallback is used when v1.1 lacks numeric DP IDs."""
        api = self._api()

        api.async_make_request = (
            AsyncMock(
                side_effect=[
                    (
                        200,
                        {
                            "success": True,
                            "result": {
                                "functions": [
                                    {
                                        "code":
                                            "switch",
                                        "type":
                                            "Boolean",
                                    }
                                ]
                            },
                        },
                    ),
                    (
                        200,
                        {
                            "success": True,
                            "result": {
                                "functions": [
                                    {
                                        "dp_id":
                                            1,
                                        "code":
                                            "switch",
                                        "type":
                                            "Boolean",
                                    }
                                ]
                            },
                        },
                    ),
                ]
            )
        )

        result, specification = (
            await api
            .async_get_device_specification(
                "device-1"
            )
        )

        self.assertEqual(
            result,
            SUCCESS,
        )
        self.assertEqual(
            specification[
                "functions"
            ][0]["dp_id"],
            1,
        )

        self.assertEqual(
            api.async_make_request
            .call_args_list,
            [
                call(
                    "GET",
                    "/v1.1/devices/"
                    "device-1/"
                    "specifications",
                ),
                call(
                    "GET",
                    "/v1.0/iot-03/"
                    "devices/device-1/"
                    "specification",
                ),
            ],
        )

        self.assertEqual(
            api.device_specifications[
                "device-1"
            ],
            specification,
        )

    async def test_device_list_filters_invalid_entries(self):
        """Malformed Cloud device entries do not enter the cache."""
        api = self._api()

        api.async_make_request = (
            AsyncMock(
                return_value=(
                    200,
                    {
                        "success": True,
                        "result": [
                            {
                                "id":
                                    "good-device",
                                "name":
                                    "Good",
                            },
                            {
                                "id": 123,
                            },
                            {
                                "name":
                                    "Missing ID",
                            },
                            "invalid",
                        ],
                    },
                )
            )
        )

        result = (
            await api
            .async_get_devices_list()
        )

        self.assertEqual(
            result,
            SUCCESS,
        )
        self.assertEqual(
            list(
                api.device_list
            ),
            ["good-device"],
        )

    async def test_access_token_validation(self):
        """Token response must contain a string access token."""
        api = self._api()

        api.async_make_request = (
            AsyncMock(
                side_effect=[
                    (
                        200,
                        {
                            "success": True,
                            "result": {},
                        },
                    ),
                    (
                        200,
                        {
                            "success": True,
                            "result": {
                                "access_token":
                                    "token-123"
                            },
                        },
                    ),
                ]
            )
        )

        invalid = (
            await api
            .async_get_access_token()
        )

        self.assertIn(
            "did not contain",
            invalid,
        )

        valid = (
            await api
            .async_get_access_token()
        )

        self.assertEqual(
            valid,
            SUCCESS,
        )
        self.assertEqual(
            api._access_token,
            "token-123",
        )


if __name__ == "__main__":
    unittest.main()
