"""Tests for Tuya UDP discovery packet decoding."""

import binascii
import json
import struct
import unittest
from unittest.mock import AsyncMock, patch

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    algorithms,
    modes,
)
from cryptography.hazmat.primitives.ciphers.aead import (
    AESGCM,
)

from custom_components.localtuya.discovery import (
    HEADER_55AA,
    HEADER_6699,
    PREFIX_55AA,
    SUFFIX_55AA,
    SUFFIX_6699,
    UDP_KEY,
    TuyaDiscovery,
    _build_6699_discovery_request,
    decrypt_udp,
)


PAYLOAD = {
    "gwId": "test-device",
    "ip": "192.168.1.50",
    "version": "3.4",
}


def _json_bytes():
    return json.dumps(
        PAYLOAD,
        separators=(",", ":"),
    ).encode()


def _encrypt_ecb(data):
    padder = padding.PKCS7(
        128
    ).padder()

    padded = (
        padder.update(data)
        + padder.finalize()
    )

    encryptor = Cipher(
        algorithms.AES(UDP_KEY),
        modes.ECB(),
    ).encryptor()

    return (
        encryptor.update(padded)
        + encryptor.finalize()
    )


def _build_55aa(payload):
    declared_length = (
        len(payload) + 8
    )

    header = struct.pack(
        HEADER_55AA,
        0x000055AA,
        1,
        0,
        declared_length,
    )

    before_crc = header + payload

    crc = (
        binascii.crc32(
            before_crc
        )
        & 0xFFFFFFFF
    )

    return (
        before_crc
        + struct.pack(">I", crc)
        + SUFFIX_55AA
    )


def _build_6699(payload):
    iv = bytes(range(12))

    # AES-GCM adds a 16-byte authentication tag.
    declared_length = (
        len(iv)
        + len(payload)
        + 16
    )

    header = struct.pack(
        HEADER_6699,
        0x00006699,
        0,
        1,
        0,
        declared_length,
    )

    associated_data = header[4:]

    ciphertext_and_tag = (
        AESGCM(UDP_KEY).encrypt(
            iv,
            payload,
            associated_data,
        )
    )

    return (
        header
        + iv
        + ciphertext_and_tag
        + SUFFIX_6699
    )


class DiscoveryPacketTests(unittest.TestCase):
    """Test every supported discovery packet format."""

    def test_plaintext_json(self):
        """Plain JSON broadcasts are accepted."""
        decoded = json.loads(
            decrypt_udp(
                _json_bytes()
            )
        )

        self.assertEqual(
            decoded,
            PAYLOAD,
        )

    def test_legacy_ecb_payload(self):
        """Legacy raw AES-ECB discovery packets are accepted."""
        encrypted = _encrypt_ecb(
            _json_bytes()
        )

        decoded = json.loads(
            decrypt_udp(encrypted)
        )

        self.assertEqual(
            decoded,
            PAYLOAD,
        )

    def test_55aa_frame(self):
        """Legacy framed 55AA packets are verified and decoded."""
        packet = _build_55aa(
            _json_bytes()
        )

        self.assertTrue(
            packet.startswith(
                PREFIX_55AA
            )
        )

        decoded = json.loads(
            decrypt_udp(packet)
        )

        self.assertEqual(
            decoded,
            PAYLOAD,
        )

    def test_6699_frame(self):
        """Authenticated AES-GCM 6699 packets are decoded."""
        packet = _build_6699(
            _json_bytes()
        )

        decoded = json.loads(
            decrypt_udp(packet)
        )

        self.assertEqual(
            decoded,
            PAYLOAD,
        )

    def test_active_discovery_request_is_valid_6699(self):
        """REQ_DEVINFO active discovery uses authenticated 6699 framing."""
        packet = (
            _build_6699_discovery_request(
                "10.0.21.135",
                iv=bytes(range(12)),
            )
        )

        (
            prefix,
            _unknown,
            _seqno,
            command,
            _length,
        ) = struct.unpack(
            HEADER_6699,
            packet[
                :struct.calcsize(
                    HEADER_6699
                )
            ],
        )

        self.assertEqual(
            prefix,
            0x00006699,
        )
        self.assertEqual(
            command,
            0x25,
        )

        decoded = json.loads(
            decrypt_udp(packet)
        )

        self.assertEqual(
            decoded,
            {
                "from": "app",
                "ip": "10.0.21.135",
            },
        )

    def test_55aa_bad_crc_rejected(self):
        """A corrupted 55AA packet must never be accepted."""
        packet = bytearray(
            _build_55aa(
                _json_bytes()
            )
        )

        packet[20] ^= 0x01

        with self.assertRaisesRegex(
            ValueError,
            "CRC",
        ):
            decrypt_udp(
                bytes(packet)
            )

    def test_device_registration_and_refresh(self):
        """Discovery merges repeated broadcasts by device ID."""
        received = []

        discovery = TuyaDiscovery(
            received.append
        )

        discovery.device_found(
            {
                "gwId": "abc123",
                "version": 3.3,
            },
            source_ip="192.168.1.20",
        )

        self.assertEqual(
            discovery.devices[
                "abc123"
            ]["ip"],
            "192.168.1.20",
        )
        self.assertEqual(
            discovery.devices[
                "abc123"
            ]["version"],
            "3.3",
        )

        discovery.device_found(
            {
                "gwId": "abc123",
                "ip": "192.168.1.21",
                "productKey": "test",
            }
        )

        self.assertEqual(
            discovery.devices[
                "abc123"
            ]["ip"],
            "192.168.1.21",
        )
        self.assertEqual(
            discovery.devices[
                "abc123"
            ]["productKey"],
            "test",
        )

        self.assertEqual(
            len(received),
            2,
        )


class ActiveDiscoveryTests(
    unittest.IsolatedAsyncioTestCase
):
    """Test active Tuya discovery network selection."""

    async def test_enabled_ipv4_adapter_is_probed(
        self,
    ):
        discovery = TuyaDiscovery(
            hass=object()
        )

        adapters = [
            {
                "enabled": True,
                "ipv4": [
                    {
                        "address":
                            "10.0.21.10",
                        "network_prefix":
                            24,
                    }
                ],
            }
        ]

        with (
            patch(
                "custom_components.localtuya.discovery."
                "async_get_adapters",
                new=AsyncMock(
                    return_value=adapters
                ),
            ),
            patch(
                "custom_components.localtuya.discovery."
                "_async_send_discovery_request",
                new=AsyncMock(),
            ) as sender,
        ):
            result = (
                await discovery
                .async_request_discovery()
            )

        self.assertTrue(result)

        sender.assert_awaited_once_with(
            "10.0.21.10",
            "10.0.21.255",
        )


if __name__ == "__main__":
    unittest.main()
