# Skill Expert: Optimisation ASO (App Store Optimization)

## Objectif
Produire une strategie ASO complete et actionable pour n'importe quelle application mobile.
L'analyse couvre les 6 dimensions critiques d'une fiche App Store — keywords, metadata,
assets visuels, ratings, signaux de conversion — avec un scoring quantitatif sur 100 et
des recommandations priorisees par impact.

## Framework
**ASO Scoring System (6 dimensions)** — methode de scoring pondere qui evalue chaque
composante de la fiche store independamment, puis agrege en un score global comparable
dans le temps et entre concurrents.

## Structure attendue

### 1. Systeme de scoring ASO (6 dimensions)

| # | Dimension | Poids | Ce qu'elle couvre |
|---|-----------|-------|-------------------|
| 1 | Titre et sous-titre | 20% | Keywords, clarte, equilibre brand + keyword |
| 2 | Description | 15% | 3 premieres lignes, structure, CTA |
| 3 | Assets visuels | 25% | Screenshots, video, icone |
| 4 | Ratings et reviews | 20% | Note, volume, reponses dev |
| 5 | Metadata et fraicheur | 10% | Categorie, MAJ, localisations |
| 6 | Signaux de conversion | 10% | Valeur percue, pricing, social proof |

#### Grilles de notation (0-10 par dimension)

Pour chaque dimension, scorer selon cette echelle :
- **9-10** : Optimise au maximum, best practices appliquees, rien a corriger
- **7-8** : Bonne base, quelques optimisations claires a faire
- **5-6** : Lacunes visibles, impact partiel sur la decouverte/conversion
- **3-4** : Sous-optimise, manque de strategie evidente
- **1-2** : Absent ou contre-productif

Reperes specifiques par dimension :

| Dimension | 9-10 (reference haute) | 3-4 (reference basse) |
|-----------|----------------------|----------------------|
| Titre/sous-titre | Brand + keyword fort, usage max des chars, objectif instantane | Brand seul, sous-titre absent ou faible |
| Description | Accroche percutante, structure complete, CTA, promotional text | Bloc de texte, pas de value prop au-dessus du fold |
| Assets visuels | 8-10 screenshots avec captions, video preview, storytelling | 3-4 screenshots sans captions, icone generique |
| Ratings | 4.5+ etoiles, 10K+ ratings, reponses aux negatifs | 3.0-3.4 etoiles, <500 ratings, plaintes non traitees |
| Metadata | MAJ < 1 mois, 10+ localisations, in-app events actifs | MAJ 3-6 mois, 1-2 localisations |
| Conversion | Valeur claire, pricing transparent, social proof visible | Pas clair ce que l'utilisateur obtient |

#### Calcul du score final

```
Score final = (Titre * 0.20 + Description * 0.15 + Visuels * 0.25
             + Ratings * 0.20 + Metadata * 0.10 + Conversion * 0.10) * 10
```

Resultat sur 100.

| Score | Grade | Signification |
|-------|-------|---------------|
| 85-100 | A | Bien optimise — focus A/B testing et iteration |
| 70-84 | B | Bonne base — opportunites claires d'amelioration |
| 50-69 | C | Lacunes significatives — les corrections prioritaires auront un fort impact |
| 30-49 | D | Optimisation majeure necessaire sur plusieurs dimensions |
| 0-29 | F | Refonte complete de la fiche necessaire |

### 2. Strategie de keywords

#### Framework de selection

Evaluer chaque keyword sur 3 axes (score 1-5 chacun) :

| Axe | Critere |
|-----|---------|
| Volume | Nombre de recherches mensuelles (> 30 = bon signal) |
| Pertinence | Lien direct avec le produit (le keyword decrit-il ce que l'app fait ?) |
| Competition | Difficulte de classement (< 40 difficulty = opportunite) |

**Formule** : `Score = Volume x Pertinence x (6 - Competition)`

Ne retenir que les keywords avec **Score >= 40**.

#### Keyword mapping par champ

| Champ | Limite | Strategie |
|-------|--------|-----------|
| Titre | 30 chars (iOS) | Brand + keyword primaire le plus fort |
| Sous-titre | 30 chars (iOS) | Proposition de valeur unique + keyword secondaire |
| Keyword field | 100 bytes (pas chars) | Keywords separes par virgule, pas de repetition titre/sous-titre |

Regles du keyword field :
- 100 **bytes**, pas 100 caracteres — les scripts non-latins (arabe, CJK) consomment 2-3 bytes par caractere
- Utiliser le singulier (Apple indexe les deux formes)
- Pas de prepositions (de, pour, avec)
- Pas de repetition de mots deja dans titre ou sous-titre
- Separer par des virgules sans espaces
- Mixer langues si pertinent (les utilisateurs recherchent souvent en anglais)

#### Categories de keywords

Couvrir systematiquement ces 4 familles :

- **Coeur de metier** : ce que l'app fait (verbes, noms fonctionnels)
- **Cas d'usage** : les situations concretes ou l'utilisateur a besoin de l'app
- **Emotionnel** : les benefices ressentis (fun, tranquillite, confiance)
- **Concurrents** : alternatives connues et termes de categorie

#### Keywords saisonniers

| Periode | Keywords a activer | Action |
|---------|-------------------|--------|
| Saint-Valentin (fev) | couple, amour, cadeau, surprise | Keyword field + promotional text |
| Ete (juin-aout) | vacances, voyage, partage, ete | Screenshots thematiques |
| Rentree (sept) | nouveau, organisation, productivite | Push social proof |
| Fetes (dec) | noel, nouvel an, voeux, cadeau | Promotional text festif |

### 3. Titre et sous-titre optimises

- Formule titre : `[Brand] - [Keyword Primaire]` (max 30 chars iOS)
- Formule sous-titre : `[Proposition de valeur] + [Keyword secondaire]` (max 30 chars)
- Produire 3 variantes A/B pour chacun avec rationale (volume, differentiation, CTA)

### 4. Description App Store

Structure optimale :

```
[ACCROCHE - 1 phrase percutante, visible avant "Plus"]

[EXPLICATION - 2-3 phrases concept unique]

[FONCTIONNALITES - 5-7 bullet points benefice-orientes]

[SOCIAL PROOF - chiffre ou temoignage]

[PREMIUM TEASER si applicable]

[CTA FINAL]
```

Le premier paragraphe (avant le fold "Plus") est crucial : il doit contenir le keyword
primaire ET donner envie de lire la suite.

### 5. Strategie screenshots

- 6-10 screenshots recommandes, par screenshot definir : role, contenu, copy overlay (max 5-7 mots)
- Ordre : Hook > Core feature > Social proof > Personnalisation > CTA
- Best practices : police lisible contrastee, keywords dans les captions (indexes par Apple depuis juin 2025), format edge-to-edge, chaque overlay autonome

### 6. Ratings et reviews

#### Quand demander un avis

Identifier 3-5 moments positifs specifiques au produit (ex : apres un succes, un milestone, une recompense).

Regles :
- Jamais pendant l'onboarding
- Jamais apres un bug ou echec
- Max 3 demandes par an (contrainte Apple via SKStoreReviewController)
- Espacer d'au moins 30 jours

#### Template reponse avis negatif

```
Salut [prenom si visible] ! Merci pour ton retour.
[Reconnaissance du probleme en 1 phrase]
[Action concrete prise ou prevue]
[Invitation a recontacter : "Ecris-nous a [email support]"]
```

Ton : empathique, concis, proactif. Repondre sous 24h.

### 7. Checklist pre-soumission

- [ ] Keyword field mis a jour (100 bytes, pas de repetition titre/sous-titre)
- [ ] Titre et sous-titre respectent les limites (30 chars chacun iOS)
- [ ] Description : premier paragraphe contient le keyword primaire
- [ ] Screenshots : 6 minimum, premier screenshot = hook
- [ ] Captions screenshots : keywords integres dans les overlays
- [ ] App Preview video : 15-30s, H.264 ou ProRes, pas de contenu interdit Apple
- [ ] Localisation a jour pour les marches cibles
- [ ] Promotional text actualise si evenement saisonnier (170 chars, modifiable sans release)
- [ ] "Quoi de neuf" redige (features, pas de jargon technique)
- [ ] Categorie primaire et secondaire optimales
- [ ] Privacy labels a jour
- [ ] Rating age correct
- [ ] Preview sur differentes tailles d'ecran (6.9", 6.1", iPad si applicable)
- [ ] Pas de screenshot avec des donnees placeholder ou lorem ipsum

## Criteres de qualite (score 10/10)

1. **30+ keywords** avec estimations de volume, difficulte et pertinence dans un tableau structure
2. **Titre et sous-titre optimises** avec 3 variantes A/B et rationale pour chacune
3. **Description longue complete** structuree (accroche, features, social proof, CTA) avec keywords integres naturellement
4. **Strategie keyword field iOS** : 100 bytes optimises, aucune repetition avec titre/sous-titre, singulier uniquement
5. **Strategie screenshots** avec 6+ screenshots decrits (role, contenu, copy overlay) et recommandations video

## Exemple de sortie

```
## Recherche de keywords

| Mot-cle | Volume | Difficulte | Pertinence | Score |
|---------|--------|------------|------------|-------|
| meditation guidee | 4/5 | 2/5 | 5/5 | 80 |
| relaxation sommeil | 3/5 | 2/5 | 4/5 | 48 |
| musique zen | 3/5 | 3/5 | 3/5 | 27 ❌ |
| respiration anti-stress | 2/5 | 1/5 | 5/5 | 50 |
| bien-etre mental | 3/5 | 3/5 | 4/5 | 36 ❌ |
| coherence cardiaque | 3/5 | 1/5 | 5/5 | 75 |

## Titre optimise

| Option | Titre | Rationale |
|--------|-------|-----------|
| A | ZenApp - Meditation Guidee | Keyword #1 volume, comprehension immediate |
| B | ZenApp - Sommeil & Serenite | Benefice emotionnel, double keyword |
| C | ZenApp : Respire & Dors Mieux | CTA direct, tonalite bienveillante |

Recommandation : Option A pour le lancement (volume max), A/B test avec C apres 30 jours.

## Sous-titre

| Option | Sous-titre | Rationale |
|--------|-----------|-----------|
| A | Sommeil, stress, serenite | Triple benefice, keywords forts |

## Keyword field (iOS)

meditation,sommeil,relaxation,stress,respiration,calme,coherence,serenite,anxiete,zen,
dormir,insomnie,yoga,pleine,conscience,detente,nuit,bienetre,soin,mental
→ 94 bytes (6 bytes restants)
```

## Erreurs a eviter

1. **Keyword stuffing dans le titre** — Apple penalise les titres artificiels, equilibrer brand et keywords
2. **Repetition de mots entre titre et keyword field** — gaspillage de bytes, Apple indexe deja le titre
3. **Description generique "Bienvenue dans..."** — les 3 premieres lignes doivent accrocher, pas saluer
4. **Screenshots = captures UI brutes sans messaging** — chaque screenshot doit communiquer un benefice avec un overlay
5. **Ignorer que le keyword field est en bytes** — 100 bytes ≠ 100 chars, surtout avec des caracteres speciaux
6. **Pas de video preview** — perte de 20-40% de conversion potentielle
7. **Keyword field avec des espaces apres les virgules** — chaque espace gaspille un byte utile

## Regles

1. Toujours scorer les 6 dimensions avant de proposer des optimisations — le diagnostic precede la prescription
2. Le keyword field iOS est de 100 **bytes** pas 100 caracteres — verifier la taille reelle
3. Ne jamais repeter dans le keyword field un mot deja present dans le titre ou le sous-titre
4. Chaque screenshot doit avoir un role distinct et un copy overlay de max 7 mots
5. Les recommandations doivent etre adaptees au produit specifique — pas de conseils generiques applicables a toute app
6. Fournir des variantes A/B testables pour le titre et le sous-titre avec une recommandation argumentee
