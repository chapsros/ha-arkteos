# Arkteos Heat Pump - Intégration Home Assistant

Intégration Home Assistant pour les pompes à chaleur **Arkteos Zuran 3 / REG3** (anciennement AJTech).

## Appareils supportés
- Arkteos Zuran 3
- Arkteos Baguio 3
- Arkteos AJPAC 3
- Tout appareil avec module REG3 connecté

## Prérequis
- PAC connectée au réseau local (ethernet)
- Port **9641** accessible depuis Home Assistant
- Home Assistant 2023.1 ou supérieur

## Installation

### Via HACS (recommandé)
1. Ouvrez HACS dans Home Assistant
2. Cliquez sur **Intégrations**
3. Cliquez sur les 3 points en haut à droite → **Dépôts personnalisés**
4. Ajoutez l'URL du dépôt GitHub, catégorie **Intégration**
5. Recherchez "Arkteos" et installez
6. Redémarrez Home Assistant

### Manuellement
1. Copiez le dossier `custom_components/arkteos/` dans votre dossier `/config/custom_components/`
2. Redémarrez Home Assistant

## Configuration
1. Allez dans **Paramètres → Appareils & services → Ajouter une intégration**
2. Recherchez "Arkteos"
3. Entrez l'IP de votre PAC (ex: `192.168.1.88`) et le port (`9641`)
4. Cliquez sur **Valider**

## Entités créées

### Capteurs (sensors)
| Entité | Description |
|--------|-------------|
| `sensor.temp_eau_depart` | Température départ circuit chauffage |
| `sensor.temp_eau_retour` | Température retour circuit chauffage |
| `sensor.temp_exterieure` | Température extérieure |
| `sensor.temp_ballon_ecs` | Température ballon eau chaude sanitaire |
| `sensor.temp_condenseur` | Température condenseur |
| `sensor.temp_evaporateur` | Température évaporateur |
| `sensor.temp_refoulement` | Température refoulement compresseur |
| `sensor.temp_zone1` | Température ambiante zone 1 |
| `sensor.temp_zone2` | Température ambiante zone 2 |
| `sensor.temp_depart_plancher` | Température départ plancher chauffant |
| `sensor.temp_retour_plancher` | Température retour plancher chauffant |

### Thermostat (climate)
| Entité | Description |
|--------|-------------|
| `climate.arkteos` | Contrôle principal : mode + consigne température |

**Modes disponibles :**
- `heat` — Chauffage
- `cool` — Climatisation
- `auto` — Automatique
- `off` — Arrêt

## Notes importantes

### Lecture des données
La lecture des capteurs fonctionne de manière fiable via le protocole TCP REG3 (trames binaires décodées).

### Contrôle (consigne + mode)
⚠️ Le format exact des trames de commande n'a pas encore été confirmé par capture réseau. Si le changement de consigne ne fonctionne pas, capturez vos trames avec le script de diagnostic et ouvrez une issue sur GitHub.

### Capture des trames de commande
Pour capturer les trames envoyées par l'app officielle Arkteos (afin d'affiner le contrôle) :
```bash
# Sur Mac/Linux, lancez le proxy sur votre machine
python3 custom_components/arkteos/tools/proxy.py 192.168.1.88 9641
# Puis pointez l'app Arkteos vers votre IP machine sur le port 9641
# Toutes les trames seront affichées
```

## Contribuer
Ce projet est ouvert à contributions, notamment pour :
- Confirmer les trames de commande (consigne, mode)
- Supporter d'autres modèles Arkteos
- Ajouter le support ECS (mode boost, consigne)

## Basé sur
- Travaux de [cyrilpawelko/arkteos_reg3](https://github.com/cyrilpawelko/arkteos_reg3)
- Discussions [Home Assistant Community](https://community.home-assistant.io/t/how-to-connect-to-my-arkteos-ajtech-heat-pump/250968)
