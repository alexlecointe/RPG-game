from app.agents.base import AgentResult, BaseAgent


class BuilderAgent(BaseAgent):
    agent_id = "builder"

    async def run(self, mission_type: str, company_name: str, mission_statement: str) -> AgentResult:
        if mission_type == "landing_page":
            html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>{company_name}</title>
  <style>
    body {{ font-family: system-ui; max-width: 640px; margin: 2rem auto; padding: 0 1rem; }}
    h1 {{ color: #1a1a2e; }}
    .cta {{ display: inline-block; background: #e94560; color: white; padding: 12px 24px;
            border-radius: 8px; text-decoration: none; margin-top: 1rem; }}
  </style>
</head>
<body>
  <h1>{company_name}</h1>
  <p>{mission_statement or "Votre solution, livrée plus vite."}</p>
  <a class="cta" href="#waitlist">Rejoindre la waitlist</a>
</body>
</html>"""
            return AgentResult(format="html", content=html, metadata={"mock": True})
        # product_brief
        md = f"""# Brief produit — {company_name}

## Vision
{mission_statement or "À définir"}

## Problème
Les utilisateurs perdent du temps sur des tâches répétitives.

## Solution
{company_name} automatise avec des agents IA gamifiés.

## MVP
- 3 agents (Builder, Marketer, Researcher)
- Missions à crédits + livrables réels

## Métriques
- Missions complétées / semaine
- Rétention J7
"""
        return AgentResult(format="markdown", content=md, metadata={"mock": True})
