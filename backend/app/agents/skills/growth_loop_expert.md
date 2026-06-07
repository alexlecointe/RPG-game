# Skill Expert: Growth Loops et Viralite

## Objectif
Designer une strategie de croissance virale complete pour un produit digital, en combinant
les frameworks AARRR, Hook Model et STEPPS. L'analyse part du diagnostic de stade du produit,
identifie les leviers de retention et de viralite, et produit un plan d'action chiffre
avec des mecanismes concrets de referral et de partage.

## Framework
**AARRR (Pirate Metrics) + K-factor + Hook Model (Nir Eyal) + STEPPS (Jonah Berger)** —
quatre frameworks complementaires : AARRR structure le funnel, le Hook Model optimise la
retention, le K-factor quantifie la viralite, et STEPPS identifie les leviers psychologiques
du partage.

## Structure attendue

### 1. Diagnostic de stade

| Stade | Signaux | Priorite |
|-------|---------|----------|
| Pre-launch | Pas d'utilisateurs | Activation + premier referral loop |
| Early (0-1K) | Premiers users, pas de retention | Activation, aha moment, Hook Model |
| Growth (1K-100K) | Retention correcte, pas de viralite | K-factor, STEPPS, referral program |
| Scale (100K+) | K-factor > 0.5, retention D30 > 20% | Optimisation, expansion, network effects |

Commencer par identifier le stade du produit, puis appliquer les frameworks du stade.

### 2. Framework AARRR (Pirate Metrics)

Analyser chaque etape du funnel :

**Acquisition**
- Canaux d'acquisition identifies (organique, paid, referral, viral)
- CAC estime par canal
- Volume et qualite par source

**Activation**
- Definition du aha moment (l'action la plus correlee a la retention)
- Time to value : duree entre l'inscription et le aha moment
- Taux de completion de l'onboarding
- Optimisations pour reduire le time to value

**Retention**
- Metriques : D1 / D7 / D30 retention
- Frequence de session (DAU/MAU ratio)
- Appliquer le Hook Model (section 3) pour renforcer les boucles

**Referral**
- K-factor actuel ou estime (section 4)
- Mecanismes de partage existants
- Viral cycle time (duree d'un cycle complet invitation → activation)

**Revenue**
- ARPU et ARPPU
- Taux de conversion free → paid
- LTV et ratio LTV/CAC (cible > 3)

### 3. Hook Model pour la retention

Construire les 4 phases de la boucle pour le produit :

**Trigger (declencheur)**
- Externe : push notification, email, SMS, social media
- Interne : ennui, FOMO, curiosite, habitude, besoin social
- Objectif : migrer des triggers externes vers les triggers internes

**Action (comportement minimal)**
- L'action la plus simple que l'utilisateur peut faire (ouvrir l'app, scroller, poster, reagir)
- Appliquer B=MAP (Fogg) : Behavior = Motivation × Ability × Prompt
- Reduire la friction au maximum (moins de taps, moins de decisions)

**Variable Reward (recompense variable)**
- Social : likes, commentaires, reactions, validation des pairs
- Hunt : decouverte de contenu, feed personnalise, nouveaute
- Self : progression, mastery, accomplissement, streak

**Investment (investissement)**
- Donnees personnelles, contenu cree, reputation, preferences, skill
- L'investissement rend le prochain cycle meilleur (feed personnalise, historique, reseau)
- Plus l'utilisateur investit, plus le cout de switching augmente

### 4. K-factor et viralite

#### Formule

```
K = i × c
```

- `i` = nombre moyen d'invitations envoyees par utilisateur
- `c` = taux de conversion d'une invitation en nouvel utilisateur actif
- **K > 1** = croissance virale organique (chaque user amene plus d'un user)
- **K = 0.5-1** = croissance aidee (viralite + acquisition payante)
- **K < 0.5** = pas de viralite significative

#### STEPPS pour maximiser le partage

Appliquer les 6 leviers psychologiques de Jonah Berger :

| Levier | Question a se poser | Mecanisme |
|--------|---------------------|-----------|
| Social Currency | Est-ce que partager donne l'air cool/intelligent/in ? | Badges exclusifs, early access, contenu rare |
| Triggers | Qu'est-ce qui rappelle le produit au quotidien ? | Associations contextuelles, rituels |
| Emotion | Quelle emotion forte le produit declenche ? | Surprise, amusement, fierte, nostalgie |
| Public | Est-ce que l'usage est visible par les autres ? | "Powered by", share cards, profils publics |
| Practical Value | Est-ce utile au point de le recommander ? | Tips, economie, gain de temps |
| Stories | Le produit s'integre-t-il dans une histoire racontable ? | User stories, narratifs, antes/apres |

#### Mecanismes concrets de viralite

- Invite friends (avec incitation symetrique)
- Share achievements / milestones
- "Powered by [App]" sur le contenu genere
- Referral rewards (donner ET recevoir)
- Contenu partageable natif (share cards, stories, images)
- Collaborative features (inviter pour collaborer, pas juste utiliser)

### 5. Programme de referral

#### Structure

| Element | Detail |
|---------|--------|
| Trigger | Quand proposer ? (apres un moment positif, jamais pendant l'onboarding) |
| Incentive parrain | Ce que le parrain recoit (credits, premium, feature unlock) |
| Incentive filleul | Ce que le filleul recoit (bonus de bienvenue, trial etendu) |
| Mecanisme | Lien unique, code promo, in-app share, QR code |
| Attribution | Deep link avec tracking (Airbridge, Branch, Firebase Dynamic Links) |

#### Design principles

- **Double incentive** : toujours recompenser les deux cotes
- **Valeur prouvee d'abord** : ne proposer qu'apres le aha moment
- **Friction minimale** : 1-2 taps pour partager
- **Transparence** : montrer clairement ce que chacun recoit
- **Urgence douce** : "Invite 3 amis cette semaine" > "Invite tes amis"

#### Benchmarks

- 5-15% des utilisateurs actifs deviennent des referrers
- LTV des utilisateurs referes : +16-25% vs acquisition payante
- Viral cycle time optimal : < 48h pour les apps sociales

#### Anti-patterns

- Proposer le referral avant que l'utilisateur ait eu son aha moment
- Incentive asymetrique (parrain recoit tout, filleul rien)
- Friction dans le flow de partage (trop d'etapes, obligation de saisir un email)
- Gamifier le referral sans valeur reelle (badges vides)
- Spammer les contacts de l'utilisateur

### 6. Metriques et plan d'action

#### Dashboard de suivi

| Metrique | Formule / Source | Cible |
|----------|------------------|-------|
| K-factor | invitations × conversion | > 0.5 (early), > 1.0 (growth) |
| Viral cycle time | duree moyenne invitation → activation | < 48h |
| D1 retention | users actifs J+1 / cohorte | > 35% |
| D7 retention | users actifs J+7 / cohorte | > 15% |
| D30 retention | users actifs J+30 / cohorte | > 8% |
| Referral rate | referrers actifs / MAU | > 5% |
| Share rate | partages / sessions | > 2% |

#### Plan 30 jours

Proposer 3 experiments priorises par impact × facilite :

| Semaine | Experiment | Hypothese | Metrique cible | Go/No-go |
|---------|------------|-----------|----------------|----------|
| S1-S2 | [Experiment 1] | [Si X alors Y] | [Metrique] | [Seuil minimal] |
| S2-S3 | [Experiment 2] | [Si X alors Y] | [Metrique] | [Seuil minimal] |
| S3-S4 | [Experiment 3] | [Si X alors Y] | [Metrique] | [Seuil minimal] |

Critere go/no-go : definir a l'avance le seuil minimal pour considerer l'experiment reussi
(ex : "referral rate > 5% avec p < 0.05 sur 500 users").

## Criteres de qualite (score 10/10)

1. **Growth loop decrit** avec diagramme ou description detaillee du cycle complet (trigger → action → distribution → conversion → re-trigger)
2. **K-factor calcule** avec hypotheses chiffrees (nombre d'invitations, taux de conversion) et cible explicite
3. **Programme de referral designe** avec incentives, mecanisme, et timing precis
4. **Share triggers identifies** — au moins 5 moments specifiques au produit ou le partage est naturel
5. **Metriques virales et cibles** — dashboard avec K-factor, viral cycle time, D1/D7/D30, referral rate et seuils

## Exemple de sortie

```
## Diagnostic

Stade : Early (500 utilisateurs)
Priorite : Activation + Hook Model + premier referral loop

## K-factor actuel

Hypotheses :
- Invitations par user actif (i) : 2.5 (via share + contacts)
- Taux de conversion invitation (c) : 12%
- K = 2.5 × 0.12 = 0.30

→ Pas de viralite organique. Objectif : K > 0.5 en 30 jours.

Leviers :
- Augmenter i : ajouter 2 share triggers (apres milestone + contenu genere) → i cible = 4.0
- Augmenter c : ameliorer la landing de referral (social proof + incentive) → c cible = 15%
- K cible = 4.0 × 0.15 = 0.60 ✅

## Programme de referral

| Element | Design |
|---------|--------|
| Trigger | Apres la 3e session reussie (aha moment valide) |
| Parrain | 1 mois premium gratuit par ami actif |
| Filleul | 7 jours premium a l'inscription |
| Mecanisme | Lien unique + share card Instagram/WhatsApp |
| Attribution | Deep link Firebase Dynamic Links |

## Hook Model

| Phase | Implementation |
|-------|---------------|
| Trigger externe | Push a 19h : "[Ami] a publie quelque chose" |
| Trigger interne | Curiosite ("qu'est-ce que mes amis ont fait ?") |
| Action | Ouvrir l'app, scroller le feed (1 tap) |
| Variable Reward | Nouveau contenu personnalise (hunt) + reactions (social) |
| Investment | Poster du contenu, ajouter des amis, personnaliser le profil |
```

## Erreurs a eviter

1. **Referral program sans valeur prouvee** — proposer de partager avant que l'utilisateur ait eu son aha moment tue le K-factor
2. **K-factor sans donnees** — toujours poser des hypotheses chiffrees, meme estimees, pour calculer un K concret
3. **Confondre viralite et marketing** — la viralite c'est les utilisateurs qui propagent, pas l'entreprise qui achete des ads
4. **Growth loop generique** — chaque boucle doit etre specifique au produit, pas un template copie-colle
5. **Ignorer la retention** — pas de viralite durable sans retention, un K > 1 avec D7 < 5% est un chateau de cartes
6. **Copier un programme de referral** sans l'adapter au contexte (Dropbox ≠ app sociale ≠ SaaS B2B)
7. **Pas de metriques de suivi** — chaque experiment doit avoir un critere go/no-go defini a l'avance

## Regles

1. Toujours commencer par le diagnostic de stade — les priorites different radicalement entre pre-launch et scale
2. Le K-factor doit etre calcule avec des hypotheses chiffrees, jamais laisse en "a determiner"
3. Le referral ne doit etre propose qu'apres le aha moment — jamais pendant l'onboarding
4. Chaque mecanisme de partage doit beneficier aux deux parties (parrain ET filleul)
5. Proposer un plan d'action sur 30 jours avec exactement 3 experiments priorises et des criteres go/no-go
6. Les metriques cibles doivent etre adaptees au stade (D30 > 20% n'est pas realiste pour un produit early stage)
