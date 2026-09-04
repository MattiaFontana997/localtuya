import unittest
from unittest.mock import AsyncMock, patch

from custom_components.localtuya import config_flow


class TestConfigFlowProtocol35(unittest.IsolatedAsyncioTestCase):

    def test_35_is_first_supported_protocol(self):
        self.assertEqual(
            config_flow.SUPPORTED_PROTOCOL_VERSIONS,
            (
                "3.5",
                "3.4",
                "3.3",
                "3.2",
                "3.1",
            ),
        )

        self.assertEqual(
            config_flow.PROTOCOL_OPTIONS[0],
            config_flow.PROTOCOL_AUTO,
        )

        self.assertIn(
            "3.5",
            config_flow.PROTOCOL_OPTIONS,
        )

    async def test_auto_detection_probes_35_first(self):
        data = {
            config_flow.CONF_HOST: "10.0.21.142",
            config_flow.CONF_DEVICE_ID: "test-device",
            config_flow.CONF_LOCAL_KEY: "0123456789abcdef",
            config_flow.CONF_PROTOCOL_VERSION:
                config_flow.PROTOCOL_AUTO,
            config_flow.CONF_ENABLE_DEBUG: False,
        }

        probe = AsyncMock(
            return_value={
                "1": True,
                "2": 22,
            }
        )

        with patch.object(
            config_flow,
            "_async_probe_protocol",
            probe,
        ):
            dps, protocol = await config_flow.validate_input(
                None,
                data,
            )

        self.assertEqual(
            protocol,
            "3.5",
        )

        self.assertTrue(dps)

        probe.assert_awaited_once_with(
            data,
            "3.5",
            [],
        )

    async def test_explicit_35_is_accepted(self):
        data = {
            config_flow.CONF_HOST: "10.0.21.142",
            config_flow.CONF_DEVICE_ID: "test-device",
            config_flow.CONF_LOCAL_KEY: "0123456789abcdef",
            config_flow.CONF_PROTOCOL_VERSION: "3.5",
            config_flow.CONF_ENABLE_DEBUG: False,
        }

        probe = AsyncMock(
            return_value={
                "1": True,
            }
        )

        with patch.object(
            config_flow,
            "_async_probe_protocol",
            probe,
        ):
            dps, protocol = await config_flow.validate_input(
                None,
                data,
            )

        self.assertEqual(
            protocol,
            "3.5",
        )

        self.assertTrue(dps)

        probe.assert_awaited_once_with(
            data,
            "3.5",
            [],
        )


if __name__ == "__main__":
    unittest.main()
