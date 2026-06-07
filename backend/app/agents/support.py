from app.agents.base import AgentResult, BaseAgent


class SupportAgent(BaseAgent):
    agent_id = "support"

    async def run(self, mission_type: str, company_name: str, mission_statement: str) -> AgentResult:
        if mission_type == "inbox_review":
            md = f"""# Revue Inbox -- {company_name}

## Messages traites : 8

### Tickets resolus (5)
1. **Bug connexion** -- Guide envoye, probleme resolu
2. **Question prix** -- Lien vers la page tarifs
3. **Demande feature** -- Note pour l'equipe produit
4. **Remboursement** -- Traite sous 24h
5. **Onboarding** -- Tutoriel envoye

### En attente (3)
1. Demande partenariat -- necessite validation CEO
2. Bug technique complexe -- escalade au Forgeron
3. Question facturation -- en attente info Banquier

## Temps de reponse moyen : 2h
## Satisfaction client : 4.5/5
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        if mission_type == "support_setup":
            md = f"""# Setup Support Client -- {company_name}

## FAQ (10 questions)
1. **Comment ca marche ?** — {company_name} automatise la gestion de votre business grace a des agents IA.
2. **Combien ca coute ?** — Consultez notre page tarifs pour les details.
3. **Puis-je annuler ?** — Oui, a tout moment depuis vos parametres.
4. **Delai de livraison ?** — Variable selon le produit, generalement 5-15 jours.
5. **Comment obtenir un remboursement ?** — Contactez-nous sous 14 jours.
6. **Mon compte est bloque** — Verifiez votre email ou contactez le support.
7. **Comment modifier ma commande ?** — Contactez-nous avant l'expedition.
8. **Livrez-vous a l'international ?** — Oui, dans 30+ pays.
9. **Comment suivre ma commande ?** — Un email avec le tracking vous sera envoye.
10. **Probleme de paiement ?** — Verifiez votre carte ou essayez un autre moyen de paiement.

## Templates de reponse (10)
### Accueil
> Bonjour ! Merci de contacter {company_name}. Comment puis-je vous aider ?

### Probleme technique
> Merci de nous signaler ce probleme. Pouvez-vous nous envoyer une capture d'ecran ?

### Remboursement accepte
> Votre remboursement a ete initie. Delai : 5-7 jours ouvrables.

### Suivi commande
> Votre commande est en route ! Voici votre numero de suivi : [TRACKING]

### Escalade
> Je transfère votre demande a notre equipe specialisee. Reponse sous 24h.

## Workflow d'escalade
- **Niveau 1 (auto)** : FAQ, statut commande, infos generales
- **Niveau 2 (humain)** : Problemes techniques, reclamations
- **Niveau 3 (urgence)** : Remboursements > 100€, litiges, problemes de securite

## Metriques de suivi
| KPI | Objectif |
|-----|----------|
| Temps de reponse | < 4h |
| CSAT | > 4.5/5 |
| Resolution rate | > 85% |
| Escalation rate | < 15% |
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        md = f"""# Templates Support -- {company_name}

## Reponse type : Bienvenue
Bonjour ! Bienvenue chez {company_name}. {mission_statement or ""}
Comment puis-je vous aider ?

## Reponse type : Bug
Merci de signaler ce probleme. Notre equipe technique est informee.
Nous revenons vers vous sous 24h.

## Reponse type : Remboursement
Votre remboursement a ete initie. Vous recevrez le montant sous 5-7 jours ouvrables.

## FAQ automatisee
- Comment commencer ? -> Guide de demarrage
- Quels sont les tarifs ? -> Page pricing
- Comment annuler ? -> Parametres > Abonnement
"""
        return AgentResult(format="markdown", content=md, metadata={"mock": True})
