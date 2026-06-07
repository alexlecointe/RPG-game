from app.agents.base import AgentResult, BaseAgent


class OrchestratorAgent(BaseAgent):
    agent_id = "orchestrator"

    async def run(self, mission_type: str, company_name: str, mission_statement: str) -> AgentResult:
        if mission_type == "morning_plan":
            md = f"""# Plan du matin -- {company_name}

## Priorites du jour
1. Analyser les metriques de la veille
2. Lancer les missions en attente
3. Verifier les livrables en cours

## KPIs a surveiller
- Taux de completion des missions
- Credits depenses vs budget
- XP et progression

## Recommandations
- {mission_statement or "Continuer a developper la strategie produit"}
- Focus sur l'acquisition et la retention
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        if mission_type == "analytics_tracking":
            md = f"""# Plan de Tracking -- {company_name}

## Events a tracker
| Event | Trigger | Parametres |
|-------|---------|-----------|
| page_view | Chargement de page | url, referrer |
| product_view | Vue fiche produit | product_id, price |
| add_to_cart | Ajout au panier | product_id, quantity |
| begin_checkout | Debut checkout | cart_value |
| purchase | Achat confirme | order_id, revenue |
| signup | Inscription | source, method |

## KPIs par etape du funnel
| Etape | KPI | Objectif |
|-------|-----|----------|
| Acquisition | Visiteurs uniques | 1000/sem |
| Activation | Taux d'inscription | > 5% |
| Conversion | Taux de conversion | > 2% |
| Retention | Taux de retour J7 | > 30% |

## Dashboard specs
- Widget 1 : Funnel de conversion temps reel
- Widget 2 : Revenue par source de trafic
- Widget 3 : Heatmap des clics sur landing page
- Widget 4 : Cohortes de retention hebdomadaires

## Outils recommandes
- **Analytics** : GA4 + Mixpanel
- **Heatmaps** : Hotjar
- **Ads tracking** : Meta Pixel + CAPI
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        if mission_type == "optimization_audit":
            md = f"""# Audit d'Optimisation -- {company_name}

## Performance site
- Temps de chargement : 2.8s (objectif < 2s)
- Score Lighthouse : 72/100
- Taux de rebond : 45%

## Analyse funnel
| Etape | Taux | Drop-off |
|-------|------|----------|
| Landing -> Produit | 60% | 40% |
| Produit -> Panier | 25% | 35% |
| Panier -> Checkout | 55% | 20% |
| Checkout -> Achat | 70% | 30% |

## Top 10 recommandations
1. **Optimiser les images** — compression WebP (-40% taille)
2. **CTA plus visible** — couleur contrastee, taille augmentee
3. **Ajouter des reviews** — social proof sur page produit
4. **Simplifier le checkout** — reduire a 2 etapes
5. **A/B test headlines** — tester 3 variantes
6. **Retargeting abandons** — email + ads J1/J3/J7
7. **Optimiser mobile** — boutons plus gros, scroll simplifie
8. **Ajouter urgence** — stock limite, timer promo
9. **Ameliorer la FAQ** — top 5 objections adressees
10. **Reduire le CPC** — affiner les audiences, exclure non-pertinents

## Plan d'action (2 semaines)
- **Semaine 1** : Items 1-5
- **Semaine 2** : Items 6-10
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        md = f"""# Rapport du soir -- {company_name}

## Resume de la journee
- Missions lancees : 3
- Missions completees : 2
- Credits utilises : 35

## Points cles
- {mission_statement or "Progression selon le plan"}
- Les agents ont bien travaille aujourd'hui

## Prochaines etapes
- Revoir la strategie demain matin
- Prioriser les missions haute valeur
"""
        return AgentResult(format="markdown", content=md, metadata={"mock": True})
