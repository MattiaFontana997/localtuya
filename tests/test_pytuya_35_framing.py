import struct
import unittest

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from custom_components.localtuya import pytuya


class _Logger:
    def debug(self, *args, **kwargs):
        pass


class TestTuya35Framing(unittest.TestCase):
    KEY = b"0123456789abcdef"
    IV = b"abcdefghijkl"

    def test_6699_pack_and_unpack(self):
        self.assertTrue(hasattr(pytuya, "PREFIX_6699_VALUE"))
        self.assertTrue(hasattr(pytuya, "MESSAGE_HEADER_FMT_6699"))

        payload = b'{"protocol":4}'

        msg = pytuya.TuyaMessage(
            7,
            pytuya.DP_QUERY_NEW,
            None,
            payload,
            0,
            True,
            pytuya.PREFIX_6699_VALUE,
            self.IV,
        )

        frame = pytuya.pack_message(msg, hmac_key=self.KEY)

        header_len = struct.calcsize(pytuya.MESSAGE_HEADER_FMT_6699)

        prefix, unknown, seqno, cmd, length = struct.unpack(
            pytuya.MESSAGE_HEADER_FMT_6699,
            frame[:header_len],
        )

        self.assertEqual(prefix, pytuya.PREFIX_6699_VALUE)
        self.assertEqual(unknown, 0)
        self.assertEqual(seqno, 7)
        self.assertEqual(cmd, pytuya.DP_QUERY_NEW)

        # 12-byte IV + ciphertext + 16-byte GCM tag.
        self.assertEqual(length, len(payload) + 28)
        self.assertEqual(frame[-4:], pytuya.SUFFIX_6699_BIN)

        aad = frame[4:header_len]
        expected_ciphertext_and_tag = AESGCM(self.KEY).encrypt(
            self.IV,
            payload,
            aad,
        )

        self.assertEqual(
            frame[header_len:-4],
            self.IV + expected_ciphertext_and_tag,
        )

        parsed_header = pytuya.parse_header(frame)

        decoded = pytuya.unpack_message(
            frame,
            hmac_key=self.KEY,
            header=parsed_header,
            no_retcode=True,
            logger=_Logger(),
        )

        self.assertEqual(decoded.seqno, 7)
        self.assertEqual(decoded.cmd, pytuya.DP_QUERY_NEW)
        self.assertEqual(decoded.payload, payload)
        self.assertEqual(decoded.prefix, pytuya.PREFIX_6699_VALUE)
        self.assertEqual(decoded.iv, self.IV)
        self.assertTrue(decoded.crc_good)

    def test_6699_rejects_modified_authentication_tag(self):
        self.assertTrue(hasattr(pytuya, "PREFIX_6699_VALUE"))

        payload = b'{"protocol":4}'

        msg = pytuya.TuyaMessage(
            8,
            pytuya.DP_QUERY_NEW,
            None,
            payload,
            0,
            True,
            pytuya.PREFIX_6699_VALUE,
            self.IV,
        )

        frame = bytearray(
            pytuya.pack_message(msg, hmac_key=self.KEY)
        )

        # Last byte before the four-byte suffix is part of the GCM tag.
        frame[-5] ^= 0x01

        with self.assertRaises(pytuya.DecodeError):
            pytuya.unpack_message(
                bytes(frame),
                hmac_key=self.KEY,
                no_retcode=True,
                logger=_Logger(),
            )


if __name__ == "__main__":
    unittest.main()
