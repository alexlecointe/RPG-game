# Skill: Configuration paiement

## Objectif
Planifier et configurer l'infrastructure de paiement (Stripe) pour commencer a encaisser.

## Structure attendue

### 1. Strategie de monetisation
- Modele retenu (one-shot, abonnement, freemium, pay-per-use)
- Grille tarifaire detaillee
- Devises supportees
- Methodes de paiement a activer (CB, Apple Pay, Google Pay, SEPA)

### 2. Configuration Stripe
- Products et Prices a creer
- Mode de facturation (recurring vs one-time)
- Periodes d'essai (duree recommandee si applicable)
- Coupons / codes promo a mettre en place
- Webhooks a configurer (payment_intent.succeeded, subscription.created, etc.)

### 3. Checkout flow
- Pages de checkout (embedded vs hosted)
- Upsells / order bumps recommandes
- Garantie et politique de remboursement
- Emails transactionnels (confirmation, facture, relance)

### 4. Taxes et conformite
- TVA / Sales tax (configuration par region)
- Mentions legales obligatoires
- CGV recommandees

### 5. Metriques a suivre
- MRR / ARR
- Taux de conversion checkout
- Churn involontaire (cartes expirees)
- Revenue par utilisateur (ARPU)
