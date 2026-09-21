"""Async WebSocket client for Pixelblaze v3 controllers.

Standalone module: depends only on aiohttp/asyncio so it can be tested
outside Home Assistant. Speaks the native Pixelblaze protocol on port 81:

- JSON text frames for commands and state
  {"getConfig": true}            -> config frames (name, pixelCount, brightness...)
                                    and {"activeProgram": {...}, "runSequencer": ...}
  {"getVars": true}              -> {"vars": {...}} exported vars of active pattern
  {"setVars": {...}}             -> set exported vars
  {"brightness": 0..1, "save": false}
  {"activeProgramId": "<id>"}    -> switch pattern
  {"sequencerMode": 0|1|2, "runSequencer": bool}
  {"listPrograms": true}         -> binary frames (type 0x07)
- Binary frames: first byte = type, second = flags (bit0 start, bit2 end).
  Type 0x07 payload is "id\tname\n" lines. Other types (previews) are ignored.

The device accepts multiple concurrent WebSocket clients, so this client
coexists with the Pixelblaze web UI and other controllers.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

FRAME_PROGRAM_LIST = 0x07
FLAG_START = 0x01
FLAG_END = 0x04

RECONNECT_MIN = 1.0
RECONNECT_MAX = 30.0
REQUEST_TIMEOUT = 5.0


class PixelblazeError(Exception):
    """Raised when the Pixelblaze cannot be reached or a request times out."""


class PixelblazeClient:
    """Maintains one WebSocket connection to a Pixelblaze and mirrors its state."""

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession,
        on_update: Callable[[], None] | None = None,
        port: int = 81,
    ) -> None:
        self._host = host
        self._port = port
        self._session = session
        self._on_update = on_update

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task | None = None
        self._stopped = False
        self._connected_evt = asyncio.Event()

        # Mirrored device state
        self.config: dict[str, Any] = {}
        self.vars: dict[str, Any] = {}
        self.active_id: str | None = None
        self.active_name: str | None = None
        self.sequencer_on: bool = False
        self.sequencer_mode: int = 0
        self.fps: float | None = None
        self.patterns: dict[str, str] = {}  # id -> name

        # Response events for polling
        self._got_config = asyncio.Event()
        self._got_vars = asyncio.Event()
        self._got_patterns = asyncio.Event()
        self._list_buffer = bytearray()

        # Last non-zero brightness, for light turn_on after off
        self.last_brightness: float = 1.0

    # ---------------------------------------------------------------- lifecycle

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    async def start(self) -> None:
        """Start the connection loop."""
        if self._task is None:
            self._stopped = False
            self._task = asyncio.get_running_loop().create_task(self._run())

    async def stop(self) -> None:
        """Stop the connection loop and close the socket."""
        self._stopped = True
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def wait_connected(self, timeout: float = 10.0) -> None:
        try:
            await asyncio.wait_for(self._connected_evt.wait(), timeout)
        except TimeoutError as err:
            raise PixelblazeError(f"Timed out connecting to {self.url}") from err

    async def _run(self) -> None:
        backoff = RECONNECT_MIN
        while not self._stopped:
            try:
                async with self._session.ws_connect(
                    self.url, heartbeat=30, receive_timeout=90
                ) as ws:
                    self._ws = ws
                    backoff = RECONNECT_MIN
                    self._connected_evt.set()
                    self._notify()
                    _LOGGER.debug("Connected to %s", self.url)
                    await self._initial_sync()
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            self._handle_text(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            self._handle_binary(msg.data)
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - reconnect on any failure
                _LOGGER.debug("Pixelblaze connection error (%s): %s", self.url, err)
            finally:
                self._ws = None
                self._connected_evt.clear()
                self._notify()
            if self._stopped:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, RECONNECT_MAX)

    async def _initial_sync(self) -> None:
        await self.send({"getConfig": True})
        await self.send({"listPrograms": True})
        await self.send({"getVars": True})

    # ---------------------------------------------------------------- frames

    def _handle_text(self, data: str) -> None:
        try:
            msg = json.loads(data)
        except ValueError:
            return
        if not isinstance(msg, dict):
            return
        changed = False

        if "fps" in msg:
            self.fps = msg["fps"]
            # fps frames also carry storageUsed etc.; keep them in config
            for key in ("storageUsed", "storageSize", "uptime"):
                if key in msg:
                    self.config[key] = msg[key]
            changed = True

        if "vars" in msg and isinstance(msg["vars"], dict):
            self.vars = msg["vars"]
            self._got_vars.set()
            changed = True

        if "activeProgram" in msg and isinstance(msg["activeProgram"], dict):
            active = msg["activeProgram"]
            self.active_id = active.get("activeProgramId")
            self.active_name = active.get("name")
            changed = True

        if "runSequencer" in msg:
            self.sequencer_on = bool(msg["runSequencer"])
            changed = True
        if "sequencerMode" in msg:
            self.sequencer_mode = int(msg["sequencerMode"])
            changed = True

        # Settings frame (from getConfig)
        if "pixelCount" in msg or "name" in msg:
            self.config.update(msg)
            if "brightness" in msg:
                try:
                    bri = float(msg["brightness"])
                except (TypeError, ValueError):
                    bri = None
                if bri:
                    self.last_brightness = bri
            self._got_config.set()
            changed = True

        if changed:
            self._notify()

    def _handle_binary(self, data: bytes) -> None:
        if len(data) < 2 or data[0] != FRAME_PROGRAM_LIST:
            return
        flags = data[1]
        if flags & FLAG_START:
            self._list_buffer = bytearray()
        self._list_buffer.extend(data[2:])
        if flags & FLAG_END:
            patterns: dict[str, str] = {}
            for line in self._list_buffer.decode("utf-8", "replace").split("\n"):
                if "\t" in line:
                    pid, _, name = line.partition("\t")
                    if pid:
                        patterns[pid] = name
            self.patterns = patterns
            self._got_patterns.set()
            self._notify()

    def _notify(self) -> None:
        if self._on_update is not None:
            self._on_update()

    # ---------------------------------------------------------------- commands

    async def send(self, payload: dict[str, Any]) -> None:
        ws = self._ws
        if ws is None or ws.closed:
            raise PixelblazeError(f"Not connected to {self.url}")
        await ws.send_str(json.dumps(payload))

    async def poll(self) -> None:
        """Request fresh config + vars and wait for both responses."""
        self._got_config.clear()
        self._got_vars.clear()
        await self.send({"getConfig": True})
        await self.send({"getVars": True})
        try:
            await asyncio.wait_for(
                asyncio.gather(self._got_config.wait(), self._got_vars.wait()),
                REQUEST_TIMEOUT,
            )
        except TimeoutError as err:
            raise PixelblazeError("Timed out polling Pixelblaze") from err

    async def refresh_patterns(self) -> dict[str, str]:
        self._got_patterns.clear()
        await self.send({"listPrograms": True})
        try:
            await asyncio.wait_for(self._got_patterns.wait(), REQUEST_TIMEOUT)
        except TimeoutError as err:
            raise PixelblazeError("Timed out listing patterns") from err
        return self.patterns

    async def set_brightness(self, brightness: float, save: bool = False) -> None:
        brightness = min(1.0, max(0.0, brightness))
        if brightness > 0:
            self.last_brightness = brightness
        await self.send({"brightness": brightness, "save": save})
        self.config["brightness"] = brightness
        self._notify()

    async def set_active_pattern(self, pattern_id: str) -> None:
        await self.send({"activeProgramId": pattern_id})
        self.active_id = pattern_id
        self.active_name = self.patterns.get(pattern_id, self.active_name)
        self.vars = {}
        self._notify()

    async def set_vars(self, variables: dict[str, Any]) -> None:
        await self.send({"setVars": variables})
        self.vars.update(variables)
        self._notify()

    async def set_sequencer(self, run: bool, mode: int = 1) -> None:
        payload: dict[str, Any] = {"runSequencer": run}
        if run:
            payload["sequencerMode"] = mode
        await self.send(payload)
        self.sequencer_on = run
        if run:
            self.sequencer_mode = mode
        self._notify()

    def pattern_id_by_name(self, name: str) -> str | None:
        for pid, pname in self.patterns.items():
            if pname == name:
                return pid
        return None
