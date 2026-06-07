# RPG Agent Company — iOS

App iOS SwiftUI style pixel art rétro (Game Boy / Pokémon).

## Ouvrir le projet

```bash
open RPGAgentCompany.xcodeproj
```

> **Pré-requis** : Xcode 15+, iOS 17+ Simulator ou device.
> Si `xcode-select` pointe sur CommandLineTools, exécuter :
> `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`

## Structure

```
RPGAgentCompany/
├── RPGAgentCompanyApp.swift    # Point d'entrée @main
├── AppState.swift              # État global (user, company, missions)
├── Models/
│   └── Models.swift            # Codable structs (User, Company, Mission…)
├── Theme/
│   └── PixelTheme.swift        # Couleurs, typo mono, composants pixel
├── Services/
│   ├── APIClient.swift         # HTTP client → backend FastAPI
│   └── StoreKitManager.swift   # IAP crédits (stub Phase 1)
├── Views/
│   ├── RootView.swift          # Routing onboarding ↔ base
│   ├── OnboardingView.swift    # "Nouvelle partie" + nom company
│   ├── Base/
│   │   ├── BaseView.swift      # Village avec bâtiments + HUD
│   │   └── BuildingDetailView.swift  # Quêtes par bâtiment
│   └── Missions/
│       ├── MissionBoardView.swift    # Catalogue complet
│       └── LootRevealView.swift      # Écran récompense
├── Assets.xcassets/
└── Info.plist
```

## Backend

L'app attend un serveur FastAPI sur `http://127.0.0.1:8080`.
Voir `../backend/` pour lancer le serveur.

```bash
cd ../backend
pip install -e ".[dev]"
uvicorn app.main:app --port 8080
```
