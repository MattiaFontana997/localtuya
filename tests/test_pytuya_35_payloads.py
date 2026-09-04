import asyncio
import json
import unittest
from unittest.mock import patch

from custom_components.localtuya import pytuya


class CaptureTransport:
    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, data):
        self.writes.append(data)

    def close(self):
        self.closed = True


class TestTuya35Payloads(unittest.IsolatedAsyncioTestCase):
    KEY_TEXT = "0123456789abcdef"
    KEY = KEY_TEXT.encode("latin1")

    @staticmethod
    def _protocol():
        loop = asyncio.get_running_loop()
        listener = pytuya.EmptyListener()

        protocol = pytuya.TuyaProtocol(
            "test-device-123456",
            TestTuya35Payloads.KEY_TEXT,
            3.5,
            False,
            loop.create_future(),
            listener,
        )

        protocol._test_listener = listener
        return protocol

    async def test_35_protocol_metadata(self):
        protocol = self._protocol()

        try:
            self.assertEqual(
                protocol.version,
                3.5,
            )
            self.assertEqual(
                protocol.dev_type,
                "v3.5",
            )
            self.assertEqual(
                protocol.version_bytes,
                b"3.5",
            )
            self.assertEqual(
                protocol.version_header,
                b"3.5" + 12 * b"\x00",
            )
            self.assertEqual(
                pytuya.PROTOCOL_VERSION_BYTES_35,
                b"3.5",
            )
        finally:
            await protocol.close()

    async def test_35_query_uses_dp_query_new(self):
        protocol = self._protocol()

        try:
            payload = protocol._generate_payload(
                pytuya.DP_QUERY
            )

            self.assertEqual(
                payload.cmd,
                pytuya.DP_QUERY_NEW,
            )
            self.assertEqual(
                payload.payload,
                b"{}",
            )
        finally:
            await protocol.close()

    async def test_35_control_uses_new_command_and_data_envelope(self):
        protocol = self._protocol()

        try:
            with patch(
                "custom_components.localtuya.pytuya.time.time",
                return_value=1700000000,
            ):
                payload = protocol._generate_payload(
                    pytuya.CONTROL,
                    {"1": True},
                )

            self.assertEqual(
                payload.cmd,
                pytuya.CONTROL_NEW,
            )

            decoded = json.loads(
                payload.payload.decode()
            )

            self.assertEqual(
                decoded,
                {
                    "protocol": 5,
                    "t": 1700000000,
                    "data": {
                        "dps": {
                            "1": True,
                        }
                    },
                },
            )
        finally:
            await protocol.close()

    async def test_35_control_template_is_not_mutated_between_calls(self):
        protocol = self._protocol()

        try:
            with patch(
                "custom_components.localtuya.pytuya.time.time",
                return_value=1700000000,
            ):
                first = protocol._generate_payload(
                    pytuya.CONTROL,
                    {"1": True},
                )
                second = protocol._generate_payload(
                    pytuya.CONTROL,
                    {"1": False},
                )

            first_json = json.loads(
                first.payload.decode()
            )
            second_json = json.loads(
                second.payload.decode()
            )

            self.assertIsInstance(
                first_json["t"],
                int,
            )
            self.assertIsInstance(
                second_json["t"],
                int,
            )

            self.assertEqual(
                first_json["data"]["dps"],
                {"1": True},
            )
            self.assertEqual(
                second_json["data"]["dps"],
                {"1": False},
            )
        finally:
            await protocol.close()

    async def test_35_decode_payload_already_decrypted_by_gcm(self):
        protocol = self._protocol()

        try:
            raw = (
                protocol.version_header
                + b'{"data":{"dps":{"1":true,"2":22}}}'
            )

            decoded = protocol._decode_payload(raw)

            self.assertEqual(
                decoded["dps"],
                {
                    "1": True,
                    "2": 22,
                },
            )
        finally:
            await protocol.close()

    async def test_update_dps_supports_35(self):
        protocol = self._protocol()
        transport = CaptureTransport()
        protocol.transport = transport

        try:
            result = await protocol.update_dps(
                [18]
            )

            self.assertTrue(result)
            self.assertEqual(
                len(transport.writes),
                1,
            )

            frame = transport.writes[0]

            header = pytuya.parse_header(frame)

            self.assertEqual(
                header.prefix,
                pytuya.PREFIX_6699_VALUE,
            )

            decoded = pytuya.unpack_message(
                frame,
                hmac_key=self.KEY,
                no_retcode=True,
            )

            self.assertEqual(
                decoded.cmd,
                pytuya.UPDATEDPS,
            )
            self.assertEqual(
                decoded.payload,
                b'{"dpId":[18]}',
            )
        finally:
            await protocol.close()


if __name__ == "__main__":
    unittest.main()
