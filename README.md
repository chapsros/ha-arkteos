# Arkteos Heat Pump — Intégration Home Assistant

Intégration Home Assistant pour les pompes à chaleur **Arkteos Zuran 3 / REG3** (anciennement AJTech).  
Protocole TCP local, pas de cloud, pas de MQTT.

---

## Appareils supportés

- Arkteos Zuran 3
- Arkteos Baguio 3
- Arkteos AJPAC 3
- Tout appareil avec module REG3 connecté (port 9641)

---

## Prérequis

- PAC connectée au réseau local (ethernet)
- Port **9641** accessible depuis Home Assistant
- Home Assistant 2023.1 ou supérieur
- **Une seule connexion à la fois** : si l'app officielle Arkteos est connectée, l'intégration HA sera en attente (et vice-versa)

---

## Installation

### Via HACS (recommandé)
1. HACS → Intégrations → ⋮ → Dépôts personnalisés
2. Ajouter l'URL du dépôt GitHub, catégorie **Intégration**
3. Rechercher "Arkteos" → Installer
4. Redémarrer Home Assistant

### Manuellement
1. Copier `custom_components/arkteos/` dans `/config/custom_components/`
2. Redémarrer Home Assistant

---

## Configuration

1. **Paramètres → Appareils & services → Ajouter une intégration**
2. Rechercher "Arkteos"
3. Entrer l'IP de la PAC (ex: `192.168.1.88`) et le port (`9641`)
4. Valider

---

## Entités créées

### Thermostat — Radiateur (`climate.radiateur`)
| Fonctionnalité | Supporté |
|---|---|
| Température ambiante actuelle | ✅ |
| Consigne de température | ✅ |
| Mode Chaud (HEAT) | ✅ |
| Mode Arrêt (OFF) | ✅ |
| Plage de consigne | 5°C — 30°C |

### Thermostat — Plancher (`climate.plancher`)
Identique au radiateur.

### Chauffe-eau (`water_heater.chauffe_eau`)
| Fonctionnalité | Supporté |
|---|---|
| Température actuelle du ballon | ✅ |
| Consigne de température | ✅ (30°C — 70°C) |
| Température de relance | ✅ (attribut + service) |
| Mode Marche/Prog | ✅ |
| Mode Arrêt | ✅ |

### Capteurs (`sensor.*`)
| Capteur | Description |
|---|---|
| `temp_exterieure` | Température extérieure |
| `temp_retour_circuit` | Retour circuit chauffage |
| `pression` | Pression circuit (bar) |
| `temp_condenseur` | Température condenseur |
| `temp_evaporateur` | Température évaporateur |
| `temp_refoulement` | Température refoulement compresseur |
| `radiateur_temp` | Température ambiante radiateur |
| `radiateur_consigne` | Consigne radiateur |
| `plancher_temp` | Température ambiante plancher |
| `plancher_consigne` | Consigne plancher |
| `plancher_depart` | Départ plancher chauffant |
| `plancher_retour` | Retour plancher chauffant |
| `ecs_temp` | Température ballon ECS |
| `ecs_consigne` | Consigne ECS |
| `ecs_relance` | Température de relance ECS |
| `puissance` | Puissance instantanée (W) |
| `energie` | Énergie cumulée (kWh) — **total_increasing** |

---

## Dashboard Énergie HA

Le capteur `sensor.arkteos_energie` est compatible avec le tableau de bord Énergie de Home Assistant :

**Paramètres → Tableaux de bord → Énergie → Appareils électriques individuels → Ajouter**  
→ Sélectionner `sensor.arkteos_energie`

HA calcule automatiquement la consommation par heure, jour et mois.

### Import de l'historique de consommation

L'intégration peut récupérer l'historique mensuel stocké dans la PAC (12 derniers mois).  
Un service `arkteos.import_historique` est disponible dans **Outils de développement → Services**.

> **Note** : L'historique contient la consommation mensuelle de la PAC. Les données sont importées dans les statistiques de HA et apparaissent dans le dashboard Énergie.

---

## Automatisations recommandées

### Programmer le chauffage avec HA (remplacer la programmation interne)

```yaml
# Passage en mode nuit à 22h
alias: Arkteos - Mode nuit
trigger:
  - platform: time
    at: "22:00:00"
action:
  - service: climate.set_temperature
    target:
      entity_id: climate.radiateur
    data:
      temperature: 17
```

### Régler la relance ECS

```yaml
service: arkteos.set_relance_ecs
data:
  temperature: 47.5
```

---

## Notes importantes

### Connexion unique
La PAC REG3 n'accepte **qu'une seule connexion TCP à la fois**. Si l'app Arkteos officielle est connectée, l'intégration HA sera en attente de reconnexion automatique (toutes les 10 secondes).

### Commandes
Les commandes (changement de consigne, mode) sont basées sur le protocole capturé depuis l'app officielle Arkteos. Elles ont été testées et validées sur un Arkteos Zuran 3 / REG3.

### Consommation électrique
La puissance instantanée est calculée depuis un compteur interne de la PAC (offset 156 de la trame 227 octets), avec une précision de 0.1 Wh par incrément toutes les ~3 secondes.

---

## Basé sur

- Travaux de [cyrilpawelko/arkteos_reg3](https://github.com/cyrilpawelko/arkteos_reg3)
- Reverse engineering du protocole REG3 par capture réseau
- Discussions [Home Assistant Community](https://community.home-assistant.io/t/how-to-connect-to-my-arkteos-ajtech-heat-pump/250968)

---

## Contribuer

Ouvrir une issue ou une PR sur GitHub pour :
- Supporter d'autres modèles Arkteos
- Améliorer le décodage de l'historique
- Ajouter la programmation horaire depuis HA
