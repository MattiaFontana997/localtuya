"""Local network discovery for Tuya devices."""

from __future__ import annotations

import asyncio
import binascii
import json
import logging
import struct
from collections.abc import Callable
from hashlib import md5
from typing import Any

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    algorithms,
    modes,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_LOGGER = logging.getLogger(__name__)

UDP_KEY = md5(b"yGAdlopoPVldABfn").digest()

UDP_PORTS = (6666, 6667, 7000)
DEFAULT_TIMEOUT = 6.0

PREFIX_55AA = b"\x00\x00\x55\xaa"
SUFFIX_55AA = b"\x00\x00\xaa\x55"

PREFIX_6699 = b"\x00\x00\x66\x99"
SUFFIX_6699 = b"\x00\x00\x99\x66"

HEADER_55AA = ">4I"
HEADER_6699 = ">IHIII"

HEADER_55AA_SIZE = struct.calcsize(HEADER_55AA)
HEADER_6699_SIZE = struct.calcsize(HEADER_6699)

MAX_UDP_PACKET_SIZE = 64 * 1024


def _decrypt_ecb(data: bytes) -> bytes:
    """Decrypt a legacy Tuya UDP AES-ECB payload."""
    if not data or len(data) % 16:
        raise ValueError(
            "Encrypted Tuya UDP payload is not AES block aligned"
        )

    decryptor = Cipher(
        algorithms.AES(UDP_KEY),
        modes.ECB(),
    ).decryptor()

    padded = decryptor.update(data) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()

    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as exc:
        raise ValueError(
            "Invalid padding in encrypted Tuya UDP payload"
        ) from exc


def _decode_json_bytes(data: bytes) -> str | None:
    """Return JSON-looking bytes as UTF-8 text."""
    data = data.strip().rstrip(b"\x00")

    if not (
        data.startswith(b"{")
        and data.endswith(b"}")
    ):
        return None

    return data.decode("utf-8")


def _decode_55aa(packet: bytes) -> str:
    """Decode a legacy 0x55AA Tuya UDP frame."""
    if len(packet) < HEADER_55AA_SIZE + 8:
        raise ValueError("Tuya 55AA UDP frame is too short")

    prefix, _seqno, _cmd, declared_length = struct.unpack(
        HEADER_55AA,
        packet[:HEADER_55AA_SIZE],
    )

    if prefix != 0x000055AA:
        raise ValueError("Invalid Tuya 55AA prefix")

    total_length = HEADER_55AA_SIZE + declared_length

    if (
        total_length > len(packet)
        or total_length < HEADER_55AA_SIZE + 8
    ):
        raise ValueError("Invalid Tuya 55AA UDP frame length")

    frame = packet[:total_length]

    if frame[-4:] != SUFFIX_55AA:
        raise ValueError("Invalid Tuya 55AA suffix")

    expected_crc = struct.unpack(
        ">I",
        frame[-8:-4],
    )[0]

    actual_crc = (
        binascii.crc32(frame[:-8]) & 0xFFFFFFFF
    )

    if expected_crc != actual_crc:
        raise ValueError("Invalid Tuya 55AA UDP CRC")

    payload = frame[HEADER_55AA_SIZE:-8]

    candidates = []

    # Some received packets prepend the 4-byte return code.
    if len(payload) >= 4:
        candidates.append(payload[4:])

    candidates.append(payload)

    for candidate in candidates:
        plaintext = _decode_json_bytes(candidate)

        if plaintext is not None:
            return plaintext

        try:
            decrypted = _decrypt_ecb(candidate)
        except ValueError:
            continue

        plaintext = _decode_json_bytes(decrypted)

        if plaintext is not None:
            return plaintext

    raise ValueError(
        "Unable to decode Tuya 55AA UDP payload"
    )


def _decode_6699(packet: bytes) -> str:
    """Decode a Tuya 0x6699 AES-GCM UDP frame."""
    if len(packet) < HEADER_6699_SIZE + 32:
        raise ValueError("Tuya 6699 UDP frame is too short")

    (
        prefix,
        _unknown,
        _seqno,
        _cmd,
        declared_length,
    ) = struct.unpack(
        HEADER_6699,
        packet[:HEADER_6699_SIZE],
    )

    if prefix != 0x00006699:
        raise ValueError("Invalid Tuya 6699 prefix")

    total_length = (
        HEADER_6699_SIZE
        + declared_length
        + len(SUFFIX_6699)
    )

    if (
        total_length > len(packet)
        or total_length < HEADER_6699_SIZE + 32
    ):
        raise ValueError("Invalid Tuya 6699 UDP frame length")

    frame = packet[:total_length]

    if frame[-4:] != SUFFIX_6699:
        raise ValueError("Invalid Tuya 6699 suffix")

    encrypted = frame[
        HEADER_6699_SIZE:-len(SUFFIX_6699)
    ]

    if len(encrypted) < 12 + 16:
        raise ValueError(
            "Tuya 6699 encrypted payload is too short"
        )

    iv = encrypted[:12]
    ciphertext_and_tag = encrypted[12:]

    associated_data = frame[4:HEADER_6699_SIZE]

    try:
        plaintext = AESGCM(UDP_KEY).decrypt(
            iv,
            ciphertext_and_tag,
            associated_data,
        )
    except Exception as exc:
        raise ValueError(
            "Unable to authenticate/decrypt Tuya 6699 UDP frame"
        ) from exc

    plaintext = plaintext.rstrip(b"\x00")

    if (
        not plaintext.startswith(b"{")
        and len(plaintext) >= 5
        and plaintext[4:5] == b"{"
    ):
        plaintext = plaintext[4:]

    decoded = _decode_json_bytes(plaintext)

    if decoded is None:
        raise ValueError(
            "Tuya 6699 UDP payload does not contain JSON"
        )

    return decoded


def decrypt_udp(message: bytes) -> str:
    """Decrypt/decode a Tuya UDP discovery packet."""
    if not message:
        raise ValueError("Empty Tuya UDP packet")

    if len(message) > MAX_UDP_PACKET_SIZE:
        raise ValueError("Tuya UDP packet is too large")

    if message.startswith(PREFIX_55AA):
        return _decode_55aa(message)

    if message.startswith(PREFIX_6699):
        return _decode_6699(message)

    plaintext = _decode_json_bytes(message)

    if plaintext is not None:
        return plaintext

    decrypted = _decrypt_ecb(message)
    plaintext = _decode_json_bytes(decrypted)

    if plaintext is None:
        raise ValueError(
            "Tuya UDP payload does not contain JSON"
        )

    return plaintext


class TuyaDiscovery(asyncio.DatagramProtocol):
    """Listen for Tuya LAN discovery broadcasts."""

    def __init__(
        self,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize discovery."""
        self.devices: dict[str, dict[str, Any]] = {}
        self._listeners: list[
            tuple[
                asyncio.DatagramTransport,
                asyncio.DatagramProtocol,
            ]
        ] = []
        self._callback = callback

    async def start(self) -> None:
        """Start discovery listeners."""
        if self._listeners:
            return

        loop = asyncio.get_running_loop()
        errors = []

        for port in UDP_PORTS:
            try:
                transport, protocol = (
                    await loop.create_datagram_endpoint(
                        lambda: self,
                        local_addr=("0.0.0.0", port),
                        reuse_port=True,
                    )
                )
            except OSError as exc:
                errors.append((port, exc))

                _LOGGER.warning(
                    "Unable to listen for Tuya discovery "
                    "on UDP %s: %s",
                    port,
                    exc,
                )
                continue

            self._listeners.append(
                (transport, protocol)
            )

        if not self._listeners:
            if errors:
                raise errors[0][1]

            raise OSError(
                "No Tuya discovery listener could be created"
            )

        ports = ", ".join(
            str(
                transport.get_extra_info("sockname")[1]
            )
            for transport, _ in self._listeners
            if transport.get_extra_info("sockname")
        )

        _LOGGER.debug(
            "Listening for Tuya broadcasts on UDP ports %s",
            ports,
        )

    def close(self) -> None:
        """Stop discovery."""
        self._callback = None

        for transport, _ in self._listeners:
            transport.close()

        self._listeners.clear()

    def datagram_received(
        self,
        data: bytes,
        addr,
    ) -> None:
        """Process one UDP datagram."""
        try:
            decoded = json.loads(
                decrypt_udp(data)
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            _LOGGER.debug(
                "Ignoring invalid Tuya UDP packet from %s: %s",
                addr,
                exc,
            )
            return
        except Exception:
            _LOGGER.exception(
                "Unexpected error decoding "
                "Tuya UDP packet from %s",
                addr,
            )
            return

        if not isinstance(decoded, dict):
            _LOGGER.debug(
                "Ignoring non-object Tuya discovery payload "
                "from %s",
                addr,
            )
            return

        self.device_found(
            decoded,
            source_ip=addr[0] if addr else None,
        )

    def error_received(self, exc: Exception) -> None:
        """Handle UDP transport errors."""
        _LOGGER.debug(
            "Tuya discovery UDP transport error: %s",
            exc,
        )

    def device_found(
        self,
        device: dict[str, Any],
        source_ip: str | None = None,
    ) -> None:
        """Register or refresh a discovered Tuya device."""
        gw_id = device.get("gwId") or device.get("id")

        if not gw_id:
            _LOGGER.debug(
                "Ignoring Tuya discovery packet "
                "without device ID"
            )
            return

        ip = device.get("ip") or source_ip

        if not ip:
            _LOGGER.debug(
                "Ignoring Tuya discovery packet "
                "for %s without IP",
                gw_id,
            )
            return

        normalized = dict(
            self.devices.get(str(gw_id), {})
        )
        normalized.update(device)

        normalized["gwId"] = str(gw_id)
        normalized["ip"] = str(ip)

        if normalized.get("version") is not None:
            normalized["version"] = str(
                normalized["version"]
            )

        previous = self.devices.get(str(gw_id))
        self.devices[str(gw_id)] = normalized

        if previous is None:
            _LOGGER.debug(
                "Discovered Tuya device %s at %s "
                "using protocol %s",
                gw_id,
                ip,
                normalized.get("version", "unknown"),
            )
        elif previous != normalized:
            _LOGGER.debug(
                "Updated Tuya discovery data "
                "for device %s at %s",
                gw_id,
                ip,
            )

        if self._callback is not None:
            self._callback(normalized)


async def discover(
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, dict[str, Any]]:
    """Discover Tuya devices on the local network."""
    discovery = TuyaDiscovery()

    try:
        await discovery.start()
        await asyncio.sleep(timeout)
        return dict(discovery.devices)
    finally:
        discovery.close()
