# Métaphore de jeu — choix : **hybride**

## Décision

**Recommandation retenue : hybride Base-Builder (Clash of Clans) + quêtes/missions RPG.**

| Option | Pour | Contre | Verdict |
|--------|------|--------|---------|
| Pokémon overworld | Narration, rencontres « invités » | Peu adapté à « gérer une boîte » ; dev lourd (carte, combats) | Phase 2+ |
| Clash of Clans pur | Familier, timers, upgrades bâtiments | Moins de sentiment « aventure » | **Cœur UI** |
| Hybride CoC + quêtes | Base = entreprise ; quêtes = missions agents | Un peu plus de design | **MVP** |

## Écran principal : la Base

```
┌─────────────────────────────────────┐
│  Niv.12  ⚡ 47/50    💎 120         │
├─────────────────────────────────────┤
│     [Forge]      [Tour Market]      │
│        🏭            📣              │
│     Builder Lv3   Marketer Lv2      │
│                                     │
│   [Bibliothèque]    [Quartier HQ]    │
│        📚            🏛️             │
│   Researcher Lv2   Mission board    │
├─────────────────────────────────────┤
│  Quêtes actives: ████░░ 2/3         │
│  [ Lancer une mission ]             │
└─────────────────────────────────────┘
```

## Mapping jeu ↔ business

| Élément UI | Rôle business |
|------------|---------------|
| Forge | Agent **Builder** — produit, landing, code |
| Tour Market | Agent **Marketer** — copy ads, posts, email |
| Bibliothèque | Agent **Researcher** — veille, personas, idées |
| Quartier HQ | Tableau des missions + historique livrables |
| Mur / défenses (plus tard) | Budget ads, limites dépenses |
| Héros (plus tard) | Agents premium rares |

## Flux quête (couche RPG)

1. Tap sur bâtiment → liste de **quêtes** (missions typées).
2. Carte quête avec **coût**, **durée**, **récompense XP** preview.
3. Pendant le run : animation worker + timer (comme upgrade CoC).
4. À la fin : écran **loot** (scroll du livrable + boutons Partager / Copier).

## Pourquoi pas Pokémon en MVP

- La carte overworld et les combats quiz (LennyRPG) ajoutent 4–8 semaines de scope.
- La métaphore **village** communique mieux « je construis mon entreprise » au grand public.
- Les **rencontres Pokémon** peuvent devenir un mode « Campagne » (Phase 3) : chaque « boss » = milestone business (premier client, 1k MRR).

## Implémentation iOS

- `BaseView` : grille de `BuildingCard` (SwiftUI).
- `MissionBoardView` : liste + détail quête.
- `LootRevealView` : confetti léger + markdown rendu.
- Pas de SpriteKit en Phase 1 — animations `withAnimation` + SF Symbols.

Voir `ios/RPGAgentCompany/Views/Base/`.
