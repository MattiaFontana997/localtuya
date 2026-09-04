import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from custom_components.localtuya import pytuya


class TestTuya35ErrorHandling(unittest.IsolatedAsyncioTestCase):
    KEY_TEXT = "0123456789abcdef"
    KEY = KEY_TEXT.encode("latin1")

    @staticmethod
    def _dispatcher():
        return pytuya.MessageDispatcher(
            "test-device-123456",
            lambda msg: None,
            3.5,
            TestTuya35ErrorHandling.KEY,
            False,
        )

    @staticmethod
    def _protocol():
        loop = asyncio.get_running_loop()
        listener = pytuya.EmptyListener()

        protocol = pytuya.TuyaProtocol(
            "test-device-123456",
            TestTuya35ErrorHandling.KEY_TEXT,
            3.5,
            False,
            loop.create_future(),
            listener,
        )

        protocol._test_listener = listener
        return protocol

    async def test_bad_6699_authentication_reaches_waiter(self):
        dispatcher = self._dispatcher()

        waiter = asyncio.create_task(
            dispatcher.wait_for(
                10,
                pytuya.DP_QUERY_NEW,
                timeout=0.1,
            )
        )

        await asyncio.sleep(0)

        message = pytuya.TuyaMessage(
            700,
            pytuya.DP_QUERY_NEW,
            0,
            b'{"dps":{"1":true}}',
            0,
            True,
            pytuya.PREFIX_6699_VALUE,
            b"abcdefghijkl",
        )

        frame = bytearray(
            pytuya.pack_message(
                message,
                hmac_key=self.KEY,
            )
        )

        # Corrupt the AES-GCM authentication tag.
        frame[-5] ^= 0x01

        try:
            # A bad probe/frame must not escape from
            # asyncio.Protocol.data_received().
            dispatcher.add_data(bytes(frame))

            with self.assertRaises(
                pytuya.DecodeError
            ):
                await waiter

            self.assertEqual(
                dispatcher.buffer,
                b"",
            )

        finally:
            if not waiter.done():
                waiter.cancel()

                try:
                    await waiter
                except asyncio.CancelledError:
                    pass

    async def test_expected_probe_failure_does_not_log_exception(self):
        protocol = self._protocol()

        probe_error = pytuya.DecodeError(
            "expected incompatible protocol probe"
        )

        protocol.status = AsyncMock(
            side_effect=probe_error
        )
        protocol.exception = MagicMock()
        protocol.debug = MagicMock()

        try:
            with self.assertRaises(
                pytuya.DecodeError
            ):
                await protocol.detect_available_dps()

            # Expected protocol mismatches must not emit
            # ERROR-level exception tracebacks.
            protocol.exception.assert_not_called()

            protocol.debug.assert_called()

        finally:
            await protocol.close()


if __name__ == "__main__":
    unittest.main()
