# RPG Agent Company

App iOS gamifiée pour piloter une micro-entreprise IA comme un jeu de gestion/RPG.

## Structure

```
docs/           Spécifications produit (boucle de jeu, agents, App Store, etc.)
backend/        API d'orchestration (missions, crédits, agents)
ios/            Client SwiftUI (base-builder + quêtes)
```

## Démarrage rapide

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Définir OPENAI_API_KEY pour les agents réels (optionnel en dev : mock)
uvicorn app.main:app --reload --port 8080
```

API : http://localhost:8080/docs

### iOS

Ouvrir `ios/RPGAgentCompany.xcodeproj` dans Xcode 15+ (iOS 17+).

Configurer `API_BASE_URL` dans le scheme ou `Info.plist` (`http://localhost:8080` en simulateur).

## Documentation

| Fichier | Contenu |
|---------|---------|
| [docs/01-core-game-loop.md](docs/01-core-game-loop.md) | Boucle de jeu principale |
| [docs/02-game-metaphor.md](docs/02-game-metaphor.md) | Métaphore UI (hybride CoC + quêtes RPG) |
| [docs/03-mvp-agents.md](docs/03-mvp-agents.md) | 3 agents MVP et livrables |
| [docs/04-backend-architecture.md](docs/04-backend-architecture.md) | Orchestrateur, crédits, jobs |
| [docs/05-app-store-compliance.md](docs/05-app-store-compliance.md) | IAP, crédits, conformité |

## MVP (Phase 1)

- Créer une **company base** avec mission
- Recruter **Builder**, **Marketer**, **Researcher**
- Lancer des **missions** (crédits, timers, XP)
- Recevoir des **livrables** réels (landing copy, ads, recherche marché)
- Pas d'ads/paiements connectés en Phase 1 (sandbox)
