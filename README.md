# Point de rosée pour Home Assistant

Intégration personnalisée (installable avec HACS) qui calcule le **point de rosée** à partir d'une température et d'une humidité relative.

- **Détection automatique** : un capteur « Point de rosée » est ajouté sur chaque appareil qui possède à la fois un capteur de température et un capteur d'humidité. Les appareils ajoutés plus tard sont pris en compte sans redémarrage.
- **Paire manuelle** : pour combiner deux capteurs quelconques, par exemple un thermomètre et un hygromètre appartenant à deux appareils différents.

Tout se configure depuis l'interface, sans YAML.

## Installation

### Avec HACS

1. Dans HACS, ouvrez le menu ⋮ puis **Dépôts personnalisés**.
2. Ajoutez `https://github.com/stereo973/ha-dew-point` avec le type **Intégration**.
3. Recherchez « Dew Point », téléchargez-le, puis redémarrez Home Assistant.

### À la main

Copiez le dossier `custom_components/dew_point` dans le dossier `custom_components` de votre configuration Home Assistant, puis redémarrez.

Version minimale de Home Assistant : **2025.8**.

## Configuration

**Paramètres → Appareils et services → Ajouter une intégration → Point de rosée**, puis choisissez :

| Choix | Effet |
|---|---|
| Détection automatique | Crée un capteur sur chaque appareil compatible. À ajouter une seule fois. |
| Paire manuelle | Demande un nom, un capteur de température et un capteur d'humidité. À répéter autant de fois que nécessaire. Si les deux capteurs font partie du même appareil, le point de rosée y est rattaché et son nom est précédé de celui de l'appareil. |

Une fois la détection automatique en place, « Ajouter une entrée » propose directement le formulaire de paire manuelle.

## Détection automatique : les règles

Pour chaque appareil, l'intégration regarde les entités `sensor` activées, non diagnostiques, dont la classe d'appareil est *température* ou *humidité*.

| Situation sur l'appareil | Résultat |
|---|---|
| Une température et une humidité | Un capteur « Point de rosée » |
| Plusieurs températures ou humidités | Appariement par le nom : « Température extérieure » va avec « Humidité extérieure ». Un capteur par paire, par exemple « Point de rosée extérieure ». |
| Les noms ne permettent pas de trancher | Rien n'est créé : utilisez une paire manuelle. |
| L'appareil fournit déjà un point de rosée | Rien n'est créé. |
| Une seule des deux mesures | Rien n'est créé. |

Le capteur créé est rattaché à l'appareil : il apparaît sur sa page et suit sa pièce. L'appareil reste la propriété de son intégration d'origine.

- **Exclure un appareil** : désactivez son capteur de point de rosée dans les paramètres de l'entité.
- **Capteur supprimé ou désactivé** : si la température ou l'humidité source disparaît, le point de rosée correspondant est retiré.
- **Renommage** : changer l'identifiant d'un capteur source ne casse rien, le point de rosée suit.
- **Capteur non reconnu** : seuls les capteurs dont la classe d'appareil est *température* ou *humidité* sont pris en compte, en détection automatique comme dans le formulaire de paire manuelle.

## Le capteur

| Propriété | Valeur |
|---|---|
| Unité | °C, convertie par Home Assistant selon vos préférences d'affichage |
| Classe d'appareil | Température, avec statistiques à long terme |
| Mise à jour | À chaque changement de la température ou de l'humidité |
| Attributs | `temperature_entity` et `humidity_entity` : les deux capteurs utilisés |
| Indisponible | Quand l'un des deux capteurs source est indisponible |
| Inconnu | Quand une source n'a pas de valeur numérique, ou que l'humidité vaut 0 % |

Les températures source exprimées en °F ou en K sont converties avant le calcul.

## Formule

Formule de Magnus avec les coefficients d'Alduchov et Eskridge (1996), où `T` est la température en °C et `HR` l'humidité relative en % :

```
γ  = ln(HR / 100) + a·T / (b + T)
Td = b·γ / (a − γ)          a = 17,625   b = 243,04 °C
```

Entre −20 °C et +50 °C et de 10 % à 100 % d'humidité, l'écart avec l'équation de Buck reste inférieur à 0,1 °C (vérifié par les tests).

## Développement

```bash
pip install -r requirements_test.txt
pytest
```

Le workflow GitHub `Validate` lance `hassfest` et la validation HACS à chaque push. La validation HACS exige que le dépôt GitHub ait une description et des *topics*.
