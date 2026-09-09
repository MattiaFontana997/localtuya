"""Shared physical LAN transport for Tuya gateway-backed child devices.

Tuya BLE/Zigbee gateways often accept only a small number of simultaneous TCP
sessions. LocalTuya therefore keeps one physical pytuya connection per gateway
transport tuple and exposes lightweight child interfaces that serialize their
CID-scoped requests over that connection.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from contextlib import asynccontextmanager, suppress
from typing import Any

from . import pytuya
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_DATA_GATEWAY_POOL = "gateway_transport_pool"


class _GatewayListener(pytuya.TuyaListener):
    """Bridge physical gateway disconnects to all logical child listeners."""

    def __init__(self) -> None:
        self.owner: SharedGatewayTransport | None = None

    def status_updated(self, status):
        del status

    def disconnected(self):
        if self.owner is not None:
            self.owner.parent_disconnected()


class GatewayChildInterface:
    """Logical Tuya interface for one child routed through a shared gateway."""

    def __init__(
        self,
        shared: "SharedGatewayTransport",
        device_id: str,
        cid: str,
        listener: pytuya.TuyaListener,
    ) -> None:
        self._shared = shared
        self.id = str(device_id)
        self.cid = str(cid)
        self.gateway_id = shared.gateway_id
        self.listener = listener
        self.dps_cache: dict[str, Any] = {}
        self.dps_to_request: dict[str, Any] = {}
        self.dispatcher = None
        self._closed = False

    @property
    def version(self):
        return self._shared.parent.version

    @property
    def dev_type(self):
        return self._shared.parent.dev_type

    def add_dps_to_request(self, dp_indicies):
        if isinstance(dp_indicies, int):
            self.dps_to_request[str(dp_indicies)] = None
        else:
            self.dps_to_request.update({str(index): None for index in dp_indicies})

    async def status(self):
        async with self._shared.child_context(self):
            status = await self._shared.parent.status()
            self.dps_cache = copy.deepcopy(self._shared.parent.dps_cache)
            return copy.deepcopy(status)

    async def heartbeat(self):
        return await self._shared.heartbeat_once()

    def start_heartbeat(self):
        self._shared.start_heartbeat()

    async def reset(self, dpIds=None):
        async with self._shared.child_context(self):
            result = await self._shared.parent.reset(dpIds)
            self.dps_cache = copy.deepcopy(self._shared.parent.dps_cache)
            return result

    async def update_dps(self, dps=None):
        async with self._shared.child_context(self):
            return await self._shared.parent.update_dps(dps)

    async def set_dp(self, value, dp_index):
        async with self._shared.child_context(self):
            result = await self._shared.parent.set_dp(value, dp_index)
            self.dps_cache = copy.deepcopy(self._shared.parent.dps_cache)
            return result

    async def set_dps(self, dps):
        async with self._shared.child_context(self):
            result = await self._shared.parent.set_dps(dps)
            self.dps_cache = copy.deepcopy(self._shared.parent.dps_cache)
            return result

    async def detect_available_dps(self):
        async with self._shared.child_context(self):
            result = await self._shared.parent.detect_available_dps()
            self.dps_cache = copy.deepcopy(self._shared.parent.dps_cache)
            return copy.deepcopy(result)

    async def close(self):
        if self._closed:
            return
        self._closed = True
        await self._shared.pool.release(self)

    def _status_from_gateway(self, dps: dict[str, Any]) -> None:
        if self._closed or not isinstance(dps, dict):
            return
        self.dps_cache.update({str(key): value for key, value in dps.items()})
        try:
            self.listener.status_updated(copy.deepcopy(self.dps_cache))
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to dispatch shared gateway child status")

    def _parent_disconnected(self) -> None:
        if self._closed:
            return
        try:
            self.listener.disconnected()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to dispatch shared gateway disconnect")


class SharedGatewayTransport:
    """One physical pytuya connection shared by gateway child interfaces."""

    def __init__(
        self,
        pool: "GatewayTransportPool",
        key: tuple[str, str, str, float, bool],
        parent,
        gateway_id: str,
        listener: _GatewayListener,
    ) -> None:
        self.pool = pool
        self.key = key
        self.parent = parent
        self.gateway_id = str(gateway_id)
        self.listener = listener
        self.listener.owner = self
        self.children: dict[str, GatewayChildInterface] = {}
        self.lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None
        self._closed = False
        self._disconnected = False
        self._gateway_cache: dict[str, Any] = {}
        if self.parent.dispatcher is not None:
            self.parent.dispatcher.listener = self._status_message

    @property
    def alive(self) -> bool:
        """Return whether the physical session is still reusable."""
        return (
            not self._closed
            and not self._disconnected
            and self.parent.transport is not None
        )

    def add_child(
        self,
        device_id: str,
        cid: str,
        listener: pytuya.TuyaListener,
    ) -> GatewayChildInterface:
        existing = self.children.get(str(cid))
        if existing is not None and not existing._closed:
            existing.listener = listener
            existing.id = str(device_id)
            return existing
        child = GatewayChildInterface(self, device_id, cid, listener)
        self.children[str(cid)] = child
        return child

    @asynccontextmanager
    async def child_context(self, child: GatewayChildInterface):
        """Serialize and temporarily scope parent protocol state to one CID."""
        async with self.lock:
            if not self.alive:
                raise ConnectionResetError("shared Tuya gateway connection is closed")
            parent = self.parent
            saved = (
                parent.id,
                parent.cid,
                parent.gateway_id,
                parent.dps_cache,
                parent.dps_to_request,
            )
            parent.id = child.id
            parent.cid = child.cid
            parent.gateway_id = self.gateway_id
            parent.dps_cache = copy.deepcopy(child.dps_cache)
            parent.dps_to_request = copy.deepcopy(child.dps_to_request)
            try:
                yield
            finally:
                child.dps_cache = copy.deepcopy(parent.dps_cache)
                child.dps_to_request = copy.deepcopy(parent.dps_to_request)
                (
                    parent.id,
                    parent.cid,
                    parent.gateway_id,
                    parent.dps_cache,
                    parent.dps_to_request,
                ) = saved

    @asynccontextmanager
    async def gateway_context(self):
        """Serialize a gateway-level command such as heartbeat."""
        async with self.lock:
            if not self.alive:
                raise ConnectionResetError("shared Tuya gateway connection is closed")
            parent = self.parent
            saved = (
                parent.id,
                parent.cid,
                parent.gateway_id,
                parent.dps_cache,
                parent.dps_to_request,
            )
            parent.id = self.gateway_id
            parent.cid = None
            parent.gateway_id = None
            parent.dps_cache = copy.deepcopy(self._gateway_cache)
            parent.dps_to_request = {}
            try:
                yield
            finally:
                self._gateway_cache = copy.deepcopy(parent.dps_cache)
                (
                    parent.id,
                    parent.cid,
                    parent.gateway_id,
                    parent.dps_cache,
                    parent.dps_to_request,
                ) = saved

    def _status_message(self, message) -> None:
        """Decode one unsolicited STATUS frame and route it by CID."""
        parent = self.parent
        saved_cid = parent.cid
        try:
            parent.cid = None
            if message.seqno > 0:
                parent.seqno = message.seqno + 1
            decoded = parent._decode_payload(message.payload)  # noqa: SLF001
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Unable to decode shared gateway status", exc_info=True)
            return
        finally:
            parent.cid = saved_cid

        if not isinstance(decoded, dict):
            return
        nested = decoded.get("data")
        cid = decoded.get("cid")
        if not cid and isinstance(nested, dict):
            cid = nested.get("cid")
        dps = decoded.get("dps")
        if not isinstance(dps, dict) and isinstance(nested, dict):
            dps = nested.get("dps")
        if not isinstance(dps, dict):
            return
        if cid and (child := self.children.get(str(cid))) is not None:
            child._status_from_gateway(dps)

    def start_heartbeat(self) -> None:
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def heartbeat_once(self):
        async with self.gateway_context():
            return await self.parent.heartbeat()

    async def _heartbeat_loop(self) -> None:
        try:
            while self.alive:
                try:
                    await self.heartbeat_once()
                except asyncio.TimeoutError:
                    break
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("Shared Tuya gateway heartbeat failed", exc_info=True)
                    break
                await asyncio.sleep(pytuya.HEARTBEAT_INTERVAL)
        finally:
            if self.alive:
                transport = self.parent.transport
                self.parent.transport = None
                if transport is not None:
                    transport.close()
            if not self._closed:
                # Heartbeat failure is a physical disconnect too. Notify every
                # logical child once and make the pooled session non-reusable.
                self.parent_disconnected()

    def parent_disconnected(self) -> None:
        """Invalidate the pooled physical session and notify every child."""
        if self._disconnected:
            return
        self._disconnected = True
        for child in tuple(self.children.values()):
            child._parent_disconnected()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None
        self.children.clear()
        await self.parent.close()


class GatewayTransportPool:
    """Create/refcount shared gateway transports for one Home Assistant instance."""

    def __init__(self) -> None:
        self._transports: dict[
            tuple[str, str, str, float, bool], SharedGatewayTransport
        ] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        *,
        host: str,
        gateway_id: str,
        local_key: str,
        protocol_version: float,
        enable_debug: bool,
        device_id: str,
        cid: str,
        listener: pytuya.TuyaListener,
    ) -> GatewayChildInterface:
        key = (
            str(host),
            str(gateway_id),
            str(local_key),
            float(protocol_version),
            bool(enable_debug),
        )
        async with self._lock:
            shared = self._transports.get(key)
            if shared is not None and not shared.alive:
                self._transports.pop(key, None)
                await shared.close()
                shared = None
            if shared is None:
                physical_listener = _GatewayListener()
                parent = await pytuya.connect(
                    host,
                    gateway_id,
                    local_key,
                    protocol_version,
                    enable_debug,
                    physical_listener,
                )
                shared = SharedGatewayTransport(
                    self,
                    key,
                    parent,
                    gateway_id,
                    physical_listener,
                )
                self._transports[key] = shared
            return shared.add_child(device_id, cid, listener)

    async def release(self, child: GatewayChildInterface) -> None:
        async with self._lock:
            shared = child._shared
            current = shared.children.get(child.cid)
            if current is child:
                shared.children.pop(child.cid, None)
            if shared.children:
                return
            if self._transports.get(shared.key) is shared:
                self._transports.pop(shared.key, None)
            await shared.close()

    async def close(self) -> None:
        async with self._lock:
            transports = list(self._transports.values())
            self._transports.clear()
        for shared in transports:
            await shared.close()


async def async_acquire_gateway_child(
    hass,
    *,
    host: str,
    gateway_id: str,
    local_key: str,
    protocol_version: float,
    enable_debug: bool,
    device_id: str,
    cid: str,
    listener: pytuya.TuyaListener,
) -> GatewayChildInterface:
    """Acquire one logical child interface from the HA-scoped gateway pool."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    pool = domain_data.get(_DATA_GATEWAY_POOL)
    if not isinstance(pool, GatewayTransportPool):
        pool = GatewayTransportPool()
        domain_data[_DATA_GATEWAY_POOL] = pool
    return await pool.acquire(
        host=host,
        gateway_id=gateway_id,
        local_key=local_key,
        protocol_version=protocol_version,
        enable_debug=enable_debug,
        device_id=device_id,
        cid=cid,
        listener=listener,
    )
