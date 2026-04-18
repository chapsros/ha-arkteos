"""Arkteos REG3 protocol - V2 avec offsets identifiés."""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 9641
RECONNECT_DELAY = 10
INIT_BYTES = bytes.fromhex("0a")

FRAME_HEADER = 0x55
FRAME_FOOTER = 0xAA
FRAME_SIZE_227 = 227
FRAME_SIZE_163 = 163
FRAME_SIZE_95 = 95

MODE_ARRET = 0
MODE_CHAUD = 1
MODE_AUTO = 2
MODE_HORS_GEL = 3
MODE_APPOINT = 4
MODE_ECS_MARCHE = 1
MODE_ECS_APPOINT = 2

TEMP_MIN = 5.0
TEMP_MAX = 90.0


@dataclass
class ZoneData:
    present: bool = False
    temp_ambiante: Optional[float] = None
    temp_consigne: Optional[float] = None
    mode: Optional[int] = None
    derogation_active: bool = False
    derogation_duree: int = 1
    derogation_consigne: Optional[float] = None


@dataclass
class ECSData:
    present: bool = False
    temp_actuelle: Optional[float] = None
    temp_consigne: Optional[float] = None
    temp_relance: Optional[float] = None
    mode: Optional[int] = None
    derogation_active: bool = False


@dataclass
class ArkteosData:
    radiateur: ZoneData = field(default_factory=ZoneData)
    plancher: ZoneData = field(default_factory=ZoneData)
    ecs: ECSData = field(default_factory=ECSData)
    temp_exterieure: Optional[float] = None
    temp_retour_circuit: Optional[float] = None
    pression: Optional[float] = None
    temp_condenseur: Optional[float] = None
    temp_evaporateur: Optional[float] = None
    temp_refoulement: Optional[float] = None
    depart_plancher: Optional[float] = None
    retour_plancher: Optional[float] = None
    mode_global: Optional[int] = None
    marche: bool = False
    available: bool = False


def _s16(data: bytes, off: int) -> Optional[float]:
    if off + 1 >= len(data):
        return None
    raw = data[off] | (data[off + 1] << 8)
    if raw > 32767:
        raw -= 65536
    val = raw / 10.0
    return round(val, 1) if -50.0 <= val <= 150.0 else None


def _plausible(val: Optional[float], lo=TEMP_MIN, hi=TEMP_MAX) -> bool:
    return val is not None and lo <= val <= hi


def decode_frame_227(data: bytes, r: ArkteosData) -> None:
    if len(data) < FRAME_SIZE_227:
        return
    r.temp_exterieure = _s16(data, 58)
    r.temp_retour_circuit = _s16(data, 110)
    r.temp_condenseur = _s16(data, 110)
    r.temp_evaporateur = _s16(data, 119)
    r.temp_refoulement = _s16(data, 142)
    raw_p = data[46] | (data[47] << 8)
    r.pression = round(raw_p / 10.0, 1) if 0 < raw_p < 50 else None

    t_rad = _s16(data, 68)
    t_pla = _s16(data, 88)
    t_ecs = _s16(data, 108)

    if _plausible(t_rad, 5, 40):
        r.radiateur.present = True
        r.radiateur.temp_ambiante = t_rad
    if _plausible(t_pla, 5, 40):
        r.plancher.present = True
        r.plancher.temp_ambiante = t_pla
    if _plausible(t_ecs, 20, 90):
        r.ecs.present = True
        r.ecs.temp_actuelle = t_ecs

    r.marche = data[8] != 0


def decode_frame_163(data: bytes, r: ArkteosData) -> None:
    if len(data) < FRAME_SIZE_163:
        return
    r.mode_global = data[8]

    c_rad = _s16(data, 24)
    c_pla = _s16(data, 50)
    c_ecs = _s16(data, 40)
    c_rel = _s16(data, 62)
    r.depart_plancher = _s16(data, 74)
    r.retour_plancher = _s16(data, 76)

    if _plausible(c_rad, 5, 35):
        r.radiateur.temp_consigne = c_rad
    if _plausible(c_pla, 5, 35):
        r.plancher.temp_consigne = c_pla
    if _plausible(c_ecs, 30, 90):
        r.ecs.temp_consigne = c_ecs
    if _plausible(c_rel, 20, 80):
        r.ecs.temp_relance = c_rel

    mode = data[8]
    r.radiateur.mode = MODE_ARRET if mode == 0 else MODE_AUTO
    r.plancher.mode = MODE_ARRET if mode == 0 else MODE_AUTO
    r.ecs.mode = MODE_ARRET if mode == 0 else MODE_ECS_MARCHE


def find_frame(buf: bytes) -> tuple[bytes | None, bytes]:
    while len(buf) >= 3:
        if buf[0] != FRAME_HEADER:
            buf = buf[1:]
            continue
        for size in (FRAME_SIZE_227, FRAME_SIZE_163, FRAME_SIZE_95):
            if len(buf) >= size and buf[size - 1] == FRAME_FOOTER:
                return buf[:size], buf[size:]
        if len(buf) < FRAME_SIZE_227:
            break
        buf = buf[1:]
    return None, buf


def build_command(cmd_type: int, zone: int, value: int) -> bytes:
    return bytes([
        FRAME_HEADER, 0x00, 0x10, 0xff,
        0x23, 0x40, 0x03,
        cmd_type, zone,
        value & 0xff, (value >> 8) & 0xff,
        0x00, FRAME_FOOTER,
    ])


class ArkteosProtocol:
    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._data = ArkteosData()
        self._callbacks: list = []
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def data(self) -> ArkteosData:
        return self._data

    def register_callback(self, cb) -> None:
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def remove_callback(self, cb) -> None:
        if cb in self._callbacks:
            self._callbacks.remove(cb)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        await self._disconnect()

    async def send_command(self, cmd_type: int, zone: int, value: int) -> bool:
        if not self._writer:
            return False
        try:
            self._writer.write(build_command(cmd_type, zone, value))
            await self._writer.drain()
            return True
        except Exception as e:
            _LOGGER.error("Erreur commande: %s", e)
            return False

    async def _connect(self) -> bool:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=10
            )
            self._writer.write(INIT_BYTES)
            await self._writer.drain()
            _LOGGER.info("Arkteos connecté %s:%s", self.host, self.port)
            return True
        except Exception as e:
            _LOGGER.warning("Connexion impossible: %s", e)
            return False

    async def _disconnect(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

    async def _run_loop(self) -> None:
        buf = b""
        while self._running:
            if not self._writer:
                self._data.available = False
                self._notify()
                if not await self._connect():
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue
                buf = b""
            try:
                chunk = await asyncio.wait_for(self._reader.read(4096), timeout=30)
                if not chunk:
                    raise ConnectionResetError
                buf += chunk
                while True:
                    frame, buf = find_frame(buf)
                    if frame is None:
                        break
                    if len(frame) == FRAME_SIZE_227:
                        decode_frame_227(frame, self._data)
                        self._data.available = True
                        self._notify()
                    elif len(frame) == FRAME_SIZE_163:
                        decode_frame_163(frame, self._data)
                        self._data.available = True
                        self._notify()
            except asyncio.TimeoutError:
                await self._disconnect()
            except Exception as e:
                _LOGGER.warning("Erreur boucle: %s", e)
                await self._disconnect()
                await asyncio.sleep(RECONNECT_DELAY)

    def _notify(self) -> None:
        for cb in self._callbacks:
            try:
                cb()
            except Exception as e:
                _LOGGER.error("Erreur callback: %s", e)
