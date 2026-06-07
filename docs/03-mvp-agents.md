# Agents MVP — scope Phase 1

## Les 3 agents

| ID | Nom jeu | Bâtiment | Rôle | Livrables réels |
|----|---------|----------|------|-----------------|
| `builder` | Forgeron | Forge | Produit & tech | Landing page HTML, structure produit, user stories |
| `marketer` | Barde | Tour Market | Distribution | 3 variantes Meta ad copy, 5 tweets, email cold template |
| `researcher` | Érudit | Bibliothèque | Discovery | Rapport marché, 10 idées angles, persona synthétique |

## Missions par agent

### Builder

| Mission | Crédits | Durée estimée | Output |
|---------|---------|---------------|--------|
| `landing_page` | 15 | 5–10 min | `index.html` + copy hero/CTA |
| `product_brief` | 12 | 3–5 min | Markdown PRD light (5 sections) |

### Marketer

| Mission | Crédits | Durée estimée | Output |
|---------|---------|---------------|--------|
| `ad_copy_pack` | 20 | 5–8 min | JSON 3 headlines × 3 descriptions Meta |
| `social_batch` | 15 | 3–5 min | 5 posts Twitter/LinkedIn |

### Researcher

| Mission | Crédits | Durée estimée | Output |
|---------|---------|---------------|--------|
| `market_scan` | 10 | 4–6 min | Markdown : TAM signals, 3 competitors, gaps |
| `idea_storm` | 8 | 2–4 min | 10 hooks produit + cible |

## Contrat agent (backend)

```python
class AgentDeliverable(TypedDict):
    mission_id: str
    agent_id: str
    format: Literal["html", "markdown", "json"]
    content: str
    metadata: dict  # tokens_used, model, duration_ms
```

## Mode sandbox vs live

| Mode | Comportement |
|------|--------------|
| `AGENT_MODE=mock` | Templates statiques + substitution `{company_name}`, `{mission}` |
| `AGENT_MODE=openai` | Appel `gpt-4o-mini` avec prompts dans `backend/app/agents/prompts/` |

**Phase 1** : mock par défaut ; OpenAI si clé présente.

## Hors scope MVP

- Meta Ads API, Google Ads
- Stripe / vrais paiements business
- GitHub PR automatiques
- Support inbox IMAP
- Agents Finance, Support, Ads (Polsia-like) → Phase 4+

## Fichiers code

- `backend/app/agents/builder.py`
- `backend/app/agents/marketer.py`
- `backend/app/agents/researcher.py`
- `backend/app/agents/registry.py`
