from app.agents.base import AgentResult, BaseAgent


class ResearcherAgent(BaseAgent):
    agent_id = "researcher"

    async def run(self, mission_type: str, company_name: str, mission_statement: str) -> AgentResult:
        if mission_type == "market_scan":
            md = f"""# Scan marché — {company_name}

## Signaux TAM
- Marché des outils « AI company » en croissance (Polsia, NanoCorp, Cofounder).
- Mobile-first + gamification peu exploités dans ce segment.

## Concurrents
| Acteur | Force | Faiblesse |
|--------|-------|-----------|
| Polsia | Full-stack ops, agents nombreux | Web-only, peu game |
| NanoCorp | Autonomie, budget/revenue framing | Web-only |
| LennyRPG | Fun, contenu podcast | Pas de vrai business |

## Gaps
- UX consommateur type jeu mobile
- Crédits/gems alignés sur coût compute

## Recommandation
Positionner {company_name} sur « Clash of Clans pour fondateurs ».
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})
        if mission_type == "supplier_sourcing":
            md = f"""# Recherche Fournisseurs -- {company_name}

## Top 5 fournisseurs identifies

| # | Fournisseur | Plateforme | Prix unit. | MOQ | Delai | Score |
|---|-------------|-----------|------------|-----|-------|-------|
| 1 | ShenzhenTech Co. | Alibaba | 2.50€ | 500 | 15-20j | ★★★★★ |
| 2 | GuangzhouSupply | Alibaba | 3.10€ | 200 | 12-18j | ★★★★ |
| 3 | FastDrop HK | AliExpress | 5.80€ | 1 | 7-12j | ★★★ |
| 4 | EuroSource DE | Grossiste | 4.20€ | 100 | 5-8j | ★★★★ |
| 5 | TurkMaker | Alibaba | 2.80€ | 1000 | 20-25j | ★★★ |

## Analyse comparative
- **Meilleur rapport qualite/prix** : ShenzhenTech (mais MOQ eleve)
- **Meilleur pour MVP** : FastDrop HK (pas de MOQ, ideal pour tester)
- **Meilleur pour scaling** : EuroSource DE (livraison rapide EU)

## Recommandation
Commencer avec FastDrop HK pour valider le produit, puis migrer vers ShenzhenTech pour la production a echelle.
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        ideas = "\n".join(
            [
                f"1. **Hook** — « {company_name} : la base qui travaille la nuit »",
                "2. Cible solo founders sans équipe technique",
                "3. Angle TikTok : screen recording mission + loot reveal",
                "4. Partenariat newsletters indie hackers",
                "5. Mode streak quotidien = 1 mission/jour",
                "6. Referral = gems bonus (symétrique)",
                "7. Template « première landing en 10 min »",
                "8. Classement villes (leaderboard local)",
                "9. Boss fight = premier client payant",
                "10. Season pass crédits (IAP)",
            ]
        )
        md = f"# Tempête d'idées — {company_name}\n\n{ideas}\n"
        return AgentResult(format="markdown", content=md, metadata={"mock": True})
