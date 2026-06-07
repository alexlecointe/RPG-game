# Conformité App Store — crédits, IAP, promesses

> Snapshot juin 2026 — à revalider avec les guidelines Apple actuelles et un avis juridique avant soumission.

## Modèle économique retenu

| Monnaie | Usage | Mécanisme Apple |
|---------|-------|-----------------|
| **Crédits** (gems) | Payer missions agents (compute) | **Consumable IAP** obligatoire si achat in-app |
| **XP / niveaux** | Progression jeu | Non achetable (évite pay-to-win pur) |
| **Budget ads** (Phase 4+) | Dépenses Meta/Google réelles | **Hors IAP** — compte utilisateur ou wallet séparé, pas de marge sur ads via Apple |

## Guideline 3.1.1 — In-App Purchase

- Tout **crédit numérique consommable** acheté dans l'app doit passer par StoreKit.
- Interdit : lien « Acheter des crédits sur le web » pour débloquer des missions iOS (sauf Reader-style exceptions — ne s'applique pas ici).
- **Abonnement** optionnel plus tard (crédits/mois + bonus) → Auto-Renewable Subscription.

## Guideline 3.1.3(f) — Enterprise / services

- Si l'app **exécute du travail pour le compte de l'utilisateur** (agents), Apple peut considérer un **service consommable** → IAP pour les crédits qui financent ce service.
- Documenter clairement : « Les crédits financent l'exécution IA sur nos serveurs, pas un bien physique. »

## Guideline 4.2 / 4.3 — Minimum functionality

- L'app doit être **utilisable sans achat** : crédits journaliers gratuits (50/jour dans le MVP).
- Éviter shell app : livrables consultables, historique missions, progression visible.

## Promesses marketing — à éviter

| ❌ Risqué | ✅ Acceptable |
|----------|---------------|
| « Gagne de l'argent pendant ton sommeil » (garantie revenu) | « Tes agents travaillent sur tes tâches pendant que l'app tourne en arrière-plan » |
| « Revenus garantis » | « Génère des livrables pour ton business » |
| « Investissement » / « ROI assuré » | « Outil de productivité gamifié » |

Classification probable : **Productivity** ou **Games** (si dominante jeu). Hybride → choisir **Games** si >50 % UI jeu ; sinon Productivity + sous-catégorie Business.

## Automatisation publicitaire (Phase 4+)

- Campagnes Meta/Google au nom de l'utilisateur : disclosures obligatoires (qui paie, qui est annonceur).
- **NanoCorp model** : annonceur tiers = complexité légale ; préférer **compte ads utilisateur** connecté via OAuth.
- Bouton d'approbation humaine avant dépense > seuil (ex. 20 €/jour).

## Données & privacy

- Privacy Nutrition Labels : données usage, identifiants, contenu utilisateur (prompts missions).
- Si prompts contiennent PII clients → chiffrement transit + rétention limitée.
- App Privacy Policy URL requise.

## Enfants & loot boxes

- Pas de loot boxes aléatoires **payantes** (crédits pour boîte inconnue) — risque réglementaire EU/Apple.
- Bonus XP aléatoire **gratuit** post-mission : OK.

## Checklist pré-soumission

- [ ] Crédits premium uniquement via StoreKit
- [ ] Restauration achats (`restoreCompletedTransactions`)
- [ ] Crédits gratuits quotidiens documentés in-app
- [ ] Pas de promesse de revenu
- [ ] Terms of Service + Privacy Policy
- [ ] Sign in with Apple si autre login social
- [ ] Mode démo / onboarding sans carte bancaire
- [ ] Export données / suppression compte (GDPR)

## Implémentation iOS (stubs)

- `StoreKitManager.swift` — produits consumables `credits_100`, `credits_500`
- Affichage prix localisé Apple
- Serveur : validation receipt (Phase 2) — endpoint stub documenté
