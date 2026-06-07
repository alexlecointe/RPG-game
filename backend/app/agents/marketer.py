import json

from app.agents.base import AgentResult, BaseAgent


class MarketerAgent(BaseAgent):
    agent_id = "marketer"

    async def run(self, mission_type: str, company_name: str, mission_statement: str) -> AgentResult:
        if mission_type == "ad_copy_pack":
            payload = {
                "company": company_name,
                "variants": [
                    {
                        "headline": f"Découvrez {company_name}",
                        "description": mission_statement[:90] if mission_statement else "Lancez plus vite.",
                        "cta": "Essayer gratuitement",
                    },
                    {
                        "headline": "Votre équipe IA en poche",
                        "description": "Agents qui travaillent pendant que vous jouez.",
                        "cta": "Télécharger",
                    },
                    {
                        "headline": "De l'idée au livrable",
                        "description": f"{company_name} transforme les missions en assets.",
                        "cta": "Commencer",
                    },
                ],
            }
            return AgentResult(format="json", content=json.dumps(payload, indent=2, ensure_ascii=False), metadata={"mock": True})
        if mission_type == "competitor_ads_analysis":
            md = f"""# Analyse Pubs Concurrents -- {company_name}

## Top 5 pubs analysees

### 1. ConcurrentA — "Automatise tout"
- **Plateforme** : Meta (Facebook + Instagram)
- **Angle** : Gain de temps, productivite
- **Visuel** : Avant/apres interface
- **Budget estime** : 50-100€/jour
- **Performance** : CTR eleve, engagement fort

### 2. ConcurrentB — "Rejoint +1000 utilisateurs"
- **Plateforme** : Meta (Instagram)
- **Angle** : Social proof, FOMO
- **Visuel** : Temoignages clients en carousel
- **Budget estime** : 30-60€/jour

### 3. ConcurrentC — "ROI garanti"
- **Plateforme** : Google Ads
- **Angle** : ROI chiffre, resultats concrets
- **Budget estime** : 80-150€/jour

### 4. ConcurrentD — "Essai gratuit 14j"
- **Plateforme** : Meta + TikTok
- **Angle** : Freemium, zero risque
- **Budget estime** : 40-80€/jour

### 5. ConcurrentE — "La solution #1"
- **Plateforme** : LinkedIn Ads
- **Angle** : Autorite, leadership
- **Budget estime** : 60-120€/jour

## Angles les plus porteurs a adapter
1. **Social proof + chiffres** — temoignages avec metriques concretes
2. **Avant/apres** — montrer la transformation
3. **Urgence douce** — "pendant que tu hesites..."
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        if mission_type == "ads_launch_plan":
            md = f"""# Plan Lancement Meta Ads -- {company_name}

## Budget
- **Budget quotidien** : 30€/jour
- **Budget mensuel** : 900€
- **Duree test** : 14 jours puis optimisation

## Structure des Ad Sets
| Ad Set | Audience | Budget | Objectif |
|--------|----------|--------|----------|
| Cold - Lookalike | Lookalike 1% clients | 10€/j | Trafic |
| Cold - Interets | Interets startup/tech | 10€/j | Trafic |
| Retargeting | Visiteurs site 7j | 5€/j | Conversion |
| Engagement | Engages Instagram 30j | 5€/j | Conversion |

## Calendar (30 jours)
- **J1-J3** : Lancement 5 variantes creatives
- **J4-J7** : Analyse CTR, couper les pires
- **J8-J14** : Scale les 2 meilleures
- **J15-J21** : Test nouvelles audiences
- **J22-J30** : Optimisation ROAS

## KPIs cibles
| KPI | Objectif |
|-----|----------|
| CPC | < 1.50€ |
| CTR | > 1.5% |
| CPM | < 15€ |
| ROAS | > 2.5x |
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        posts = "\n\n".join(
            [
                f"🚀 {company_name} — mission du jour : shipper sans recruter.",
                f"🎮 Gérer sa boîte comme un jeu mobile. C'est {company_name}.",
                "⚡ 3 agents. 1 base. Des livrables réels chaque mission.",
                f"📣 {mission_statement[:100]}..." if mission_statement else "📣 Qui construit encore sa boîte comme un tableur ?",
                f"✅ Première mission complétée sur {company_name}. XP +15.",
            ]
        )
        return AgentResult(format="markdown", content=posts, metadata={"mock": True})
