# Beta test — 5 testeurs ecommerce

## Objectif North Star

**Un testeur termine les 5 premieres etapes de la quest chain ecommerce et utilise au moins 1 livrable dans son vrai business.**

## Profil testeur

- Fondateur solo ou side project ecommerce
- iPhone avec l'app installee (TestFlight ou build dev)
- Backend accessible (IP locale ou deploy)

## Parcours a suivre (30-45 min)

1. **Onboarding** — Choisir business type **Ecommerce**, remplir nom + description produit
2. **Quest chain** — L'ecran s'ouvre automatiquement ; lancer etape 1 (etude de marche)
3. **Attendre** — Mission en cours (~1-3 min en mock, plus en LLM reel)
4. **Loot** — A la fin, ecran LOOT s'ouvre : lire le livrable, tester **Copier** ou **Apercu HTML**
5. **Feedback beta** — Repondre au popup : as-tu utilise le livrable ? Note /5
6. **Repetition** — Enchainer etapes 2 a 5 de la chain ecommerce
7. **Journal DOCS** — Verifier le dossier entreprise assemble les livrables
8. **Upgrade** — Ameliorer un batiment niveau 2, relancer une mission et verifier la reduction credits

## Questions de validation (fin de session)

| # | Question | Reponse attendue |
|---|----------|------------------|
| 1 | As-tu utilise au moins 1 livrable dans ton business ? | Oui = succes North Star |
| 2 | Le livrable etait-il utilisable sans ChatGPT ? | Oui / partiellement / non |
| 3 | La quest chain etait-elle claire comme parcours principal ? | 1-5 |
| 4 | As-tu compris la valeur de l'upgrade batiment ? | Oui / non |
| 5 | Reviendrais-tu demain ? | Oui / non + pourquoi |

## Collecte des donnees

- **In-app** : feedback envoye via `POST /companies/{id}/feedback` apres chaque loot
- **Analytics local** : Journal → STATS → Exporter events JSON
- **Admin** : `GET /api/v1/admin/beta-feedback` pour agreger les reponses

## Criteres de succes beta

- [ ] 5/5 testeurs completent etapes 1-5
- [ ] 3/5 repondent "j'ai utilise au moins 1 livrable"
- [ ] Score qualite moyen livrables >= 7/10
- [ ] D1 retention : 3/5 reviennent le lendemain

## Notes organisateur

- Wallet initial : 80 credits, cap 150 — suffisant pour ~5 etapes chain
- Mock LLM par defaut si pas de cle API — livrables generiques mais flow testable
- Planifier 30 min debrief apres les 5 sessions
