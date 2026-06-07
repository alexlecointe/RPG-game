from app.agents.base import AgentResult, BaseAgent


class OutreachAgent(BaseAgent):
    agent_id = "outreach"

    async def run(self, mission_type: str, company_name: str, mission_statement: str) -> AgentResult:
        if mission_type == "cold_email_sequence":
            md = f"""# Sequence Cold Email -- {company_name}

## Email 1 : Premier contact
**Objet** : {{prenom}}, une question rapide sur {{probleme}}

Bonjour {{prenom}},

J'ai vu que {{entreprise}} travaille sur {{domaine}}. On aide des equipes comme la votre a {mission_statement or "optimiser leurs processus"}.

Seriez-vous ouvert a un echange de 15 min ?

Cordialement,
L'equipe {company_name}

---

## Email 2 : Relance (J+3)
**Objet** : Re: {{prenom}}, une question rapide

Bonjour {{prenom}},

Je reviens vers vous -- avez-vous eu le temps de jeter un oeil a mon dernier message ?

Nos clients voient en moyenne +40% de productivite en 30 jours.

---

## Email 3 : Derniere relance (J+7)
**Objet** : Derniere tentative {{prenom}}

Je ne veux pas etre insistant. Si le timing n'est pas bon, pas de souci.

Si vous souhaitez explorer, je suis disponible cette semaine.
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        md = f"""# Rapport Prospection -- {company_name}

## Prospects identifies : 25
| Prospect | Secteur | Score |
|----------|---------|-------|
| TechCorp | SaaS | 85/100 |
| GrowthIO | Marketing | 78/100 |
| BuildFast | Dev Tools | 72/100 |

## Emails envoyes : 15
## Taux d'ouverture : 42%
## Reponses : 3

## Actions suivantes
- Relancer les non-repondants dans 3 jours
- Qualifier les 3 reponses positives
"""
        return AgentResult(format="markdown", content=md, metadata={"mock": True})
