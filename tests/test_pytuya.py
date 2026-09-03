"""Regression tests for the LocalTuya PyTuya transport layer."""

import asyncio
import logging
import struct
import unittest

from custom_components.localtuya.pytuya import (
    AESCipher,
    CONTROL,
    DP_QUERY,
    DecodeError,
    EmptyListener,
    MESSAGE_HEADER_FMT,
    PREFIX_VALUE,
    PROTOCOL_VERSION_BYTES_31,
    SUFFIX_VALUE,
    TuyaMessage,
    TuyaProtocol,
    pack_message,
    parse_header,
    unpack_message,
)


LOGGER = logging.getLogger(__name__)
LOCAL_KEY_TEXT = "0123456789abcdef"
LOCAL_KEY = LOCAL_KEY_TEXT.encode("latin1")


class PyTuyaMessageTests(unittest.TestCase):
    """Test Tuya framing and validation."""

    def test_pack_unpack_crc(self):
        """Normal 55AA messages survive a CRC round trip."""
        message = TuyaMessage(
            7,
            DP_QUERY,
            0,
            b'{"dps":{"1":true}}',
            0,
            True,
        )

        packed = pack_message(message)

        unpacked = unpack_message(
            packed,
            no_retcode=True,
            logger=LOGGER,
        )

        self.assertEqual(unpacked.seqno, 7)
        self.assertEqual(unpacked.cmd, DP_QUERY)
        self.assertEqual(
            unpacked.payload,
            b'{"dps":{"1":true}}',
        )
        self.assertTrue(unpacked.crc_good)

    def test_pack_unpack_hmac(self):
        """Protocol 3.4 framing survives an HMAC round trip."""
        message = TuyaMessage(
            11,
            CONTROL,
            0,
            b"encrypted-payload",
            0,
            True,
        )

        packed = pack_message(
            message,
            hmac_key=LOCAL_KEY,
        )

        unpacked = unpack_message(
            packed,
            hmac_key=LOCAL_KEY,
            no_retcode=True,
            logger=LOGGER,
        )

        self.assertEqual(unpacked.seqno, 11)
        self.assertEqual(unpacked.cmd, CONTROL)
        self.assertEqual(
            unpacked.payload,
            b"encrypted-payload",
        )

    def test_tampered_message_rejected(self):
        """Payload corruption must fail CRC verification."""
        message = TuyaMessage(
            1,
            DP_QUERY,
            0,
            b"abcdef",
            0,
            True,
        )

        packed = bytearray(
            pack_message(message)
        )

        packed[16] ^= 0x01

        with self.assertRaisesRegex(
            DecodeError,
            "CRC",
        ):
            unpack_message(
                bytes(packed),
                no_retcode=True,
                logger=LOGGER,
            )

    def test_invalid_suffix_rejected(self):
        """A damaged Tuya frame suffix must be rejected."""
        message = TuyaMessage(
            1,
            DP_QUERY,
            0,
            b"abcdef",
            0,
            True,
        )

        packed = bytearray(
            pack_message(message)
        )

        packed[-1] ^= 0x01

        with self.assertRaisesRegex(
            DecodeError,
            "suffix",
        ):
            unpack_message(
                bytes(packed),
                no_retcode=True,
                logger=LOGGER,
            )

    def test_oversized_header_rejected(self):
        """Clearly corrupt payload lengths must be rejected."""
        header = struct.pack(
            MESSAGE_HEADER_FMT,
            PREFIX_VALUE,
            1,
            DP_QUERY,
            1001,
        )

        with self.assertRaisesRegex(
            DecodeError,
            "over 1000",
        ):
            parse_header(header)


class PyTuyaProtocolTests(
    unittest.IsolatedAsyncioTestCase
):
    """Test protocol-specific payload handling."""

    @staticmethod
    def _protocol(version):
        loop = asyncio.get_running_loop()
        listener = EmptyListener()

        protocol = TuyaProtocol(
            "test-device-123456",
            LOCAL_KEY_TEXT,
            version,
            False,
            loop.create_future(),
            listener,
        )

        # Keep a strong reference because TuyaProtocol stores
        # the actual listener as a weakref.
        protocol._test_listener = listener

        return protocol

    async def test_decode_payload_protocols_31_to_34(self):
        """Known payload format is decoded on every supported protocol."""
        raw = b'{"dps":{"1":true,"2":22}}'

        for version in (
            3.1,
            3.2,
            3.3,
            3.4,
        ):
            with self.subTest(version=version):
                protocol = self._protocol(
                    version
                )

                cipher = AESCipher(
                    protocol.local_key
                )

                if version == 3.1:
                    encrypted = cipher.encrypt(
                        raw
                    )

                    payload = (
                        PROTOCOL_VERSION_BYTES_31
                        + b"0" * 16
                        + encrypted
                    )

                elif version == 3.4:
                    payload = cipher.encrypt(
                        protocol.version_header
                        + raw,
                        use_base64=False,
                    )

                else:
                    payload = cipher.encrypt(
                        raw,
                        use_base64=False,
                    )

                decoded = (
                    protocol._decode_payload(
                        payload
                    )
                )

                self.assertEqual(
                    decoded["dps"],
                    {
                        "1": True,
                        "2": 22,
                    },
                )

                await protocol.close()

    async def test_connection_loss_discards_34_session_key(self):
        """A temporary 3.4 session key must never survive reconnect."""
        protocol = self._protocol(3.4)

        session_key = (
            b"fedcba9876543210"
        )

        protocol.local_key = session_key
        protocol.dispatcher.local_key = (
            session_key
        )

        protocol.connection_lost(None)

        self.assertEqual(
            protocol.local_key,
            LOCAL_KEY,
        )
        self.assertEqual(
            protocol.dispatcher.local_key,
            LOCAL_KEY,
        )

        await protocol.close()


if __name__ == "__main__":
    unittest.main()
