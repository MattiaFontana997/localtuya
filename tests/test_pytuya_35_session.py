import hmac
import unittest
from hashlib import sha256
from unittest.mock import AsyncMock, patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from custom_components.localtuya import pytuya


class TestTuya35Session(unittest.IsolatedAsyncioTestCase):
    KEY_TEXT = "0123456789abcdef"
    KEY = KEY_TEXT.encode("latin1")

    LOCAL_NONCE = b"0123456789abcdef"
    REMOTE_NONCE = b"fedcba9876543210"

    @staticmethod
    def _protocol():
        loop = __import__("asyncio").get_running_loop()
        listener = pytuya.EmptyListener()

        protocol = pytuya.TuyaProtocol(
            "test-device-123456",
            TestTuya35Session.KEY_TEXT,
            3.5,
            False,
            loop.create_future(),
            listener,
        )

        protocol._test_listener = listener
        return protocol

    async def test_35_handshake_message_uses_6699(self):
        protocol = self._protocol()

        frame = protocol._encode_message(
            pytuya.MessagePayload(
                pytuya.SESS_KEY_NEG_START,
                self.LOCAL_NONCE,
            )
        )

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
            pytuya.SESS_KEY_NEG_START,
        )
        self.assertEqual(
            decoded.payload,
            self.LOCAL_NONCE,
        )

        await protocol.close()

    async def test_exchange_negotiates_session_key_for_35(self):
        protocol = self._protocol()

        protocol._negotiate_session_key = AsyncMock(
            return_value=False
        )

        result = await protocol.exchange(
            pytuya.DP_QUERY
        )

        self.assertIsNone(result)

        protocol._negotiate_session_key.assert_awaited_once()

        await protocol.close()

    async def test_connection_loss_discards_35_session_key(self):
        protocol = self._protocol()

        session_key = b"fedcba9876543210"

        protocol.local_key = session_key
        protocol.dispatcher.local_key = session_key

        protocol.connection_lost(None)

        self.assertEqual(
            protocol.local_key,
            self.KEY,
        )
        self.assertEqual(
            protocol.dispatcher.local_key,
            self.KEY,
        )

        await protocol.close()

    async def test_bad_35_handshake_hmac_is_rejected(self):
        protocol = self._protocol()

        bad_payload = (
            self.REMOTE_NONCE
            + b"\x00" * 32
        )

        step2_message = pytuya.TuyaMessage(
            100,
            pytuya.SESS_KEY_NEG_RESP,
            0,
            bad_payload,
            0,
            True,
            pytuya.PREFIX_6699_VALUE,
            b"abcdefghijkl",
        )

        async def fake_exchange_quick(payload, recv_retries):
            if payload.cmd == pytuya.SESS_KEY_NEG_START:
                return step2_message

            raise AssertionError(
                "FINISH must not be sent after bad HMAC"
            )

        protocol.exchange_quick = fake_exchange_quick

        with patch(
            "custom_components.localtuya.pytuya.secrets.token_bytes",
            return_value=self.LOCAL_NONCE,
        ):
            result = await protocol._negotiate_session_key()

        self.assertFalse(result)

        self.assertEqual(
            protocol.local_key,
            self.KEY,
        )
        self.assertEqual(
            protocol.dispatcher.local_key,
            self.KEY,
        )

        await protocol.close()

    async def test_35_session_key_negotiation(self):
        protocol = self._protocol()

        step2_payload = (
            self.REMOTE_NONCE
            + hmac.new(
                self.KEY,
                self.LOCAL_NONCE,
                sha256,
            ).digest()
        )

        step2_message = pytuya.TuyaMessage(
            100,
            pytuya.SESS_KEY_NEG_RESP,
            0,
            step2_payload,
            0,
            True,
            pytuya.PREFIX_6699_VALUE,
            b"abcdefghijkl",
        )

        calls = []

        async def fake_exchange_quick(payload, recv_retries):
            calls.append(
                (payload, recv_retries)
            )

            if payload.cmd == pytuya.SESS_KEY_NEG_START:
                return step2_message

            if payload.cmd == pytuya.SESS_KEY_NEG_FINISH:
                # Step 3 must still be sent using the permanent
                # device key. The negotiated session key becomes
                # active only after FINISH has been transmitted.
                self.assertEqual(
                    protocol.local_key,
                    self.KEY,
                )
                self.assertEqual(
                    protocol.dispatcher.local_key,
                    self.KEY,
                )
                return None

            raise AssertionError(
                f"Unexpected command {payload.cmd}"
            )

        protocol.exchange_quick = fake_exchange_quick

        with patch(
            "custom_components.localtuya.pytuya.secrets.token_bytes",
            return_value=self.LOCAL_NONCE,
        ):
            result = await protocol._negotiate_session_key()

        self.assertTrue(result)

        self.assertEqual(len(calls), 2)

        step1, step1_retries = calls[0]
        self.assertEqual(
            step1.cmd,
            pytuya.SESS_KEY_NEG_START,
        )
        self.assertEqual(
            step1.payload,
            self.LOCAL_NONCE,
        )
        self.assertEqual(step1_retries, 2)

        step3, step3_retries = calls[1]
        self.assertEqual(
            step3.cmd,
            pytuya.SESS_KEY_NEG_FINISH,
        )
        self.assertIsNone(step3_retries)

        expected_step3_hmac = hmac.new(
            self.KEY,
            self.REMOTE_NONCE,
            sha256,
        ).digest()

        self.assertEqual(
            step3.payload,
            expected_step3_hmac,
        )

        session_seed = bytes(
            a ^ b
            for a, b
            in zip(
                self.LOCAL_NONCE,
                self.REMOTE_NONCE,
            )
        )

        expected_session_key = AESGCM(
            self.KEY
        ).encrypt(
            self.LOCAL_NONCE[:12],
            session_seed,
            None,
        )[:16]

        self.assertEqual(
            protocol.local_key,
            expected_session_key,
        )
        self.assertEqual(
            protocol.dispatcher.local_key,
            expected_session_key,
        )

        await protocol.close()


if __name__ == "__main__":
    unittest.main()
