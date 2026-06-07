from app.agents.base import AgentResult, BaseAgent


class FinanceAgent(BaseAgent):
    agent_id = "finance"

    async def run(self, mission_type: str, company_name: str, mission_statement: str) -> AgentResult:
        if mission_type == "revenue_report":
            md = f"""# Rapport Financier -- {company_name}

## Resume mensuel
| Metrique | Valeur |
|----------|--------|
| Revenus bruts | 2 450 EUR |
| Depenses | 890 EUR |
| Marge nette | 1 560 EUR |
| MRR | 2 450 EUR |
| Clients actifs | 48 |

## Repartition des revenus
- Abonnements : 75% (1 837 EUR)
- Ventes ponctuelles : 20% (490 EUR)
- Services : 5% (123 EUR)

## Tendance
- MRR en hausse de +15% vs mois precedent
- Churn rate : 3.2%
- LTV estimee : 890 EUR

## Recommandations
- Augmenter le prix du plan Pro de 10%
- Reduire le churn avec un programme de retention
- Investir 200 EUR en ads le mois prochain
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        if mission_type == "payment_setup":
            md = f"""# Guide Integration Stripe -- {company_name}

## Checklist de configuration
- [ ] Creer un compte Stripe (stripe.com)
- [ ] Activer le mode test
- [ ] Generer les API keys (pk_test / sk_test)
- [ ] Configurer le webhook endpoint
- [ ] Creer les produits et prix dans le dashboard

## Plan de webhooks
| Event | Action |
|-------|--------|
| checkout.session.completed | Creer la commande, envoyer confirmation |
| payment_intent.succeeded | Mettre a jour le statut de paiement |
| charge.refunded | Initier le remboursement en base |
| customer.subscription.updated | Mettre a jour l'abonnement |
| invoice.payment_failed | Envoyer email de relance |

## Integration Checkout
1. Creer une session Checkout via l'API
2. Rediriger le client vers la page Stripe
3. Recevoir le webhook de confirmation
4. Afficher la page de succes

## Securite
- Activer 3D Secure pour les paiements > 50€
- Activer Radar pour la detection de fraude
- Ne jamais stocker les numeros de carte
- Utiliser HTTPS partout

## Recommandations
- Commencer en mode test, basculer en live apres validation
- Configurer les emails automatiques Stripe
- Prevoir un systeme de remboursement sous 14 jours
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        md = f"""# Suivi Budget -- {company_name}

## Budget mensuel : 1 000 EUR
## Depense : 890 EUR (89%)

### Detail depenses
| Poste | Montant | % |
|-------|---------|---|
| Serveurs | 120 EUR | 13% |
| APIs IA | 340 EUR | 38% |
| Marketing | 280 EUR | 31% |
| Outils SaaS | 150 EUR | 17% |

## Alerte : budget marketing a 93% du plafond
## Projection fin de mois : 950 EUR (+60 EUR de marge)
"""
        return AgentResult(format="markdown", content=md, metadata={"mock": True})
