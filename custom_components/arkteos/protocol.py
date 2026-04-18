"""Arkteos REG3 TCP protocol decoder."""
from __future__ import annotations
import asyncio
import logging
import struct
from dataclasses import dataclass, field
from typing import Optional

_LOGGER = logging.getLogger(__name__)

FRAME_HEADER = 0x55
FRAME_FOOTER = 0xAA
FRAME_SIZE_227 = 227
FRAME_SIZE_163 = 163
FRAME_SIZE_95 = 95

DEFAULT_PORT = 9641
RECONNECT_DELAY = 10
POLL_INTERVAL = 5

# Handshake initial
INIT_BYTES = bytes.fromhex("0a")


@dataclass
class ArkteosData:
    """Données décodées de la PAC Arkteos."""

    # Températures trame 227
    temp_eau_depart: Optional[float] = None       # off54 - température départ circuit
    temp_eau_retour: Optional[float] = None       # off56 - température retour circuit
    temp_exterieure: Optional[float] = None       # off58 - température extérieure
    temp_ballon_ecs: Optional[float] = None       # off108 - température ballon ECS
    temp_condenseur: Optional[float] = None       # off110 - température condenseur
    temp_evaporateur: Optional[float] = None      # off119 - température évaporateur
    temp_refoulement: Optional[float] = None      # off142 - température refoulement

    # Températures trame 163
    temp_zone1: Optional[float] = None            # off24 - température ambiante zone 1
    temp_zone2: Optional[float] = None            # off50 - température ambiante zone 2
    consigne_zone1: Optional[float] = None        # off10 - consigne zone 1
    consigne_ecs: Optional[float] = None          # off62 - consigne ECS
    temp_depart_plancher: Optional[float] = None  # off74 - départ plancher chauffant
    temp_retour_plancher: Optional[float] = None  # off76 - retour plancher chauffant

    # États
    mode_operation: Optional[int] = None          # off8 t163 - mode (1=chauf, 2=clim, 3=ECS)
    compresseur_actif: Optional[bool] = None
    pompe_active: Optional[bool] = None

    # Disponibilité
    available: bool = False


def _decode_temp_s16(data: bytes, offset: int) -> Optional[float]:
    """Décode une température signée 16 bits little-endian en dixièmes de degré."""
    if offset + 1 >= len(data):
        return None
    raw = data[offset] | (data[offset + 1] << 8)
    if raw > 32767:
        raw -= 65536
    val = raw / 10.0
    if -50 <= val <= 150:
        return round(val, 1)
    return None


def _decode_temp_u8(data: bytes, offset: int) -> Optional[float]:
    """Décode une température non signée 8 bits."""
    if offset >= len(data):
        return None
    val = data[offset]
    if 0 <= val <= 100:
        return float(val)
    return None


def decode_frame_227(data: bytes, result: ArkteosData) -> None:
    """Décode la trame principale de 227 octets."""
    if len(data) < 227:
        return

    result.temp_eau_depart = _decode_temp_s16(data, 54)
    result.temp_eau_retour = _decode_temp_s16(data, 56)
    result.temp_exterieure = _decode_temp_s16(data, 58)
    result.temp_ballon_ecs = _decode_temp_s16(data, 108)
    result.temp_condenseur = _decode_temp_s16(data, 110)
    result.temp_evaporateur = _decode_temp_s16(data, 119)
    result.temp_refoulement = _decode_temp_s16(data, 142)


def decode_frame_163(data: bytes, result: ArkteosData) -> None:
    """Décode la trame secondaire de 163 octets."""
    if len(data) < 163:
        return

    result.mode_operation = data[8] if data[8] in (0, 1, 2, 3, 4, 5) else None
    result.consigne_zone1 = _decode_temp_s16(data, 10)
    result.temp_zone1 = _decode_temp_s16(data, 24)
    result.temp_zone2 = _decode_temp_s16(data, 50)
    result.consigne_ecs = _decode_temp_s16(data, 62)
    result.temp_depart_plancher = _decode_temp_s16(data, 74)
    result.temp_retour_plancher = _decode_temp_s16(data, 76)


def find_frame(buffer: bytes) -> tuple[bytes | None, bytes]:
    """Cherche et extrait une trame valide du buffer."""
    while len(buffer) >= 3:
        if buffer[0] != FRAME_HEADER:
            buffer = buffer[1:]
            continue

        # Vérifie le dernier octet connu
        for size in (FRAME_SIZE_227, FRAME_SIZE_163, FRAME_SIZE_95):
            if len(buffer) >= size and buffer[size - 1] == FRAME_FOOTER:
                return buffer[:size], buffer[size:]

        # Pas encore assez de données
        if len(buffer) < max(FRAME_SIZE_227, FRAME_SIZE_163, FRAME_SIZE_95):
            break
        buffer = buffer[1:]

    return None, buffer


class ArkteosProtocol:
    """Gestionnaire de connexion TCP avec la PAC Arkteos."""

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

    def register_callback(self, callback) -> None:
        self._callbacks.append(callback)

    def remove_callback(self, callback) -> None:
        self._callbacks.discard(callback)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        await self._disconnect()

    async def _connect(self) -> bool:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=10
            )
            self._writer.write(INIT_BYTES)
            await self._writer.drain()
            _LOGGER.info("Connecté à Arkteos %s:%s", self.host, self.port)
            return True
        except Exception as e:
            _LOGGER.warning("Impossible de se connecter à Arkteos: %s", e)
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
        buffer = b""
        while self._running:
            if not self._writer:
                self._data.available = False
                self._notify()
                if not await self._connect():
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue
                buffer = b""

            try:
                chunk = await asyncio.wait_for(
                    self._reader.read(4096), timeout=30
                )
                if not chunk:
                    raise ConnectionResetError("Connexion fermée")

                buffer += chunk

                while True:
                    frame, buffer = find_frame(buffer)
                    if frame is None:
                        break

                    size = len(frame)
                    if size == FRAME_SIZE_227:
                        decode_frame_227(frame, self._data)
                        self._data.available = True
                        self._notify()
                    elif size == FRAME_SIZE_163:
                        decode_frame_163(frame, self._data)
                        self._data.available = True
                        self._notify()

            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout lecture Arkteos, reconnexion...")
                await self._disconnect()
            except Exception as e:
                _LOGGER.warning("Erreur connexion Arkteos: %s", e)
                await self._disconnect()
                await asyncio.sleep(RECONNECT_DELAY)

    def _notify(self) -> None:
        for cb in self._callbacks:
            cb()
