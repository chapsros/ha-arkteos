"""Services Arkteos - import historique et relance ECS."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import UnitOfEnergy

from . import DOMAIN
from .protocol import ArkteosProtocol

_LOGGER = logging.getLogger(__name__)

# Requêtes d'historique identifiées par reverse engineering
HIST_REQUESTS = {
    'pac_mensuel':   bytes.fromhex('550008fff74004011285000028ceaa'),
    'ecs_mensuel':   bytes.fromhex('550008fff740040112870000890eaa'),
    'chauf_mensuel': bytes.fromhex('550008fff740040112860000d8ceaa'),
}

SCHEMA_RELANCE = vol.Schema({
    vol.Required('temperature'): vol.All(float, vol.Range(min=20, max=70)),
})


async def async_setup_services(hass: HomeAssistant) -> None:
    """Enregistre les services Arkteos."""

    async def handle_import_historique(call: ServiceCall) -> None:
        """Importe l'historique de consommation depuis la PAC."""
        for entry_id, protocol in hass.data.get(DOMAIN, {}).items():
            await _import_historique(hass, protocol, entry_id)

    async def handle_set_relance(call: ServiceCall) -> None:
        """Règle la température de relance ECS."""
        temp = call.data['temperature']
        for protocol in hass.data.get(DOMAIN, {}).values():
            ecs = protocol.data.ecs
            consigne = ecs.temp_consigne or 54.0
            ok = await protocol.set_ecs(consigne, temp)
            if ok:
                ecs.temp_relance = temp
                _LOGGER.info("Relance ECS réglée à %.1f°C", temp)

    hass.services.async_register(DOMAIN, 'import_historique', handle_import_historique)
    hass.services.async_register(DOMAIN, 'set_relance_ecs', handle_set_relance, schema=SCHEMA_RELANCE)


async def _import_historique(hass: HomeAssistant, protocol: ArkteosProtocol, entry_id: str) -> None:
    """Récupère et importe l'historique mensuel de la PAC."""
    import asyncio

    _LOGGER.info("Début import historique Arkteos")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(protocol.host, protocol.port), timeout=10
        )
        writer.write(bytes.fromhex('0a'))
        await writer.drain()

        # Attendre les données initiales
        await asyncio.sleep(2)
        await reader.read(4096)  # vider le buffer

        # Demander l'historique PAC mensuel
        writer.write(HIST_REQUESTS['pac_mensuel'])
        await writer.drain()
        await asyncio.sleep(0.5)

        data = await asyncio.wait_for(reader.read(4096), timeout=5)
        writer.close()

        # Décoder les données mensuelles
        # Format identifié: trame 211 octets, type 0x05
        # off16-25: 5 valeurs u16 = kWh x10 des mois avec conso
        kwh_data = _decode_monthly_kwh(data)

        if kwh_data:
            await _inject_statistics(hass, entry_id, kwh_data)
            _LOGGER.info("Import historique OK: %d mois importés", len(kwh_data))
        else:
            _LOGGER.warning("Aucune donnée historique trouvée")

    except Exception as e:
        _LOGGER.error("Erreur import historique: %s", e)


def _decode_monthly_kwh(data: bytes) -> list[tuple[datetime, float]]:
    """
    Décode les données mensuelles de consommation.
    Retourne une liste de (datetime, kwh).
    """
    results = []

    # Chercher la trame type 0x05 (211 octets)
    i = 0
    while i < len(data) - 211:
        if (data[i] == 0x55 and
                len(data) >= i + 211 and
                data[i + 8] == 0x12 and
                data[i + 9] == 0x05 and
                data[i + 210] == 0xAA):

            frame = data[i:i + 211]
            # off16-25: valeurs u16 LE en kWh*10
            now = datetime.now(timezone.utc)
            current_month = now.month
            current_year = now.year

            for j, off in enumerate(range(16, 26, 2)):
                val = frame[off] | (frame[off + 1] << 8)
                if val > 0:
                    kwh = val / 10.0
                    # Calcul du mois correspondant (ordre décroissant depuis maintenant)
                    month_offset = len(range(16, 26, 2)) - j - 1
                    month = current_month - month_offset
                    year = current_year
                    while month <= 0:
                        month += 12
                        year -= 1
                    try:
                        dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
                        results.append((dt, kwh))
                    except ValueError:
                        pass
            break
        i += 1

    return results


async def _inject_statistics(
    hass: HomeAssistant,
    entry_id: str,
    kwh_data: list[tuple[datetime, float]]
) -> None:
    """Injecte les données dans les statistiques HA."""
    statistic_id = f"{DOMAIN}:pac_energie_mensuelle_{entry_id[:8]}"

    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        name="Arkteos - Énergie PAC (historique)",
        source=DOMAIN,
        statistic_id=statistic_id,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )

    cumulative = 0.0
    statistics = []
    for dt, kwh in sorted(kwh_data):
        cumulative += kwh
        statistics.append(StatisticData(
            start=dt,
            sum=cumulative,
            state=kwh,
        ))

    if statistics:
        async_add_external_statistics(hass, metadata, statistics)
        _LOGGER.info("Statistiques historiques injectées: %s", statistic_id)
