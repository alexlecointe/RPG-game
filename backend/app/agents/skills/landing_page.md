# Skill: Landing page

## Objectif
Generer une landing page HTML/CSS complete, prete a deployer, optimisee pour la conversion.

## Structure de la page

### 1. Navigation
- Logo + nom de marque a gauche
- CTA principal a droite ("Commander" / "Essayer gratuit" / "S'inscrire")
- Sticky on scroll

### 2. Hero section
- Headline percutant (max 8 mots, oriente benefice)
- Sous-titre explicatif (1-2 phrases)
- CTA principal (bouton large, couleur d'accent)
- Preuve sociale courte ("Rejoint par X+ utilisateurs" ou "Note 4.8/5")

### 3. Probleme / Douleur
- Decrire le probleme en 2-3 points
- Utiliser le langage de la cible, pas du jargon

### 4. Solution / Benefices
- 3-4 cards avec icone, titre, description courte
- Chaque benefice = un resultat concret, pas une fonctionnalite

### 5. Comment ca marche
- 3 etapes numerotees (simplicite)
- Icone + titre + description pour chaque etape

### 6. Preuve sociale
- Temoignages (3 minimum, avec nom et contexte)
- Logos clients ou mentions presse si pertinent
- Chiffres cles (utilisateurs, avis, resultats)

### 7. Pricing / Offre
- Prix clair et visible
- Ce qui est inclus (liste)
- Garantie si applicable
- CTA de conversion

### 8. FAQ
- 4-6 questions frequentes
- Reponses courtes et rassurantes

### 9. Footer CTA
- Dernier rappel de la proposition de valeur
- CTA final

## Regles techniques
- HTML complet de <!DOCTYPE html> a </html>
- CSS inline (pas de fichier externe)
- Mobile-first, responsive (media queries)
- Typographie : system-ui ou Google Fonts via CDN
- Couleurs : utiliser OBLIGATOIREMENT la palette du BRIEF CREATIF WEBSITE si presente dans le contexte
- Animations CSS subtiles (fade-in, hover effects)
- Pas de JavaScript requis (sauf scroll smooth)
- Pas de placeholder / lorem ipsum — tout le contenu doit etre reel

## Utilisation du brief creatif
Si un "BRIEF CREATIF WEBSITE" est present dans le contexte :
- La palette, la typographie et le style photo sont OBLIGATOIRES — ne pas les ignorer
- Le "BRIEF IMAGE PRODUIT" decrit le style visuel souhaite
- La structure de page recommandee remplace la structure generique ci-dessus
- Le CTA et les trust signals sont adaptes au vrai produit — utilise-les

## Utilisation du SITE SPEC
Si un "SITE SPEC / WEBSITE STRATEGY" est present dans le contexte :
- Traite-le comme une maquette obligatoire, pas comme une inspiration optionnelle.
- Respecte le playbook_key, le hero_pattern, le layout_recipe et la palette.
- Les mandatory_visuals doivent etre visibles dans le HTML final.
- Les quality_rules doivent etre satisfaites explicitement dans les sections.
- Les anti_patterns sont interdits.
- Le hero doit montrer le produit, l'interface ou le resultat final des le premier ecran.
- La page doit sembler creee pour cette marque precise, pas pour n'importe quelle startup.

## Utilisation du COMPANY PROFILE
Si un "COMPANY PROFILE WEBSITE" est present dans le contexte :
- C'est la source principale du positionnement et du copy.
- Le hero doit reprendre le hero_claim ou le reformuler sans le rendre generique.
- Les sections doivent repondre aux pain_points, objections, alternatives_to_beat et desired_outcome.
- Le ton doit suivre voice.
- N'invente pas de preuves fortes qui ne sont pas dans proof_points.
- Si une information est dans unknowns, ne la presente pas comme un fait.

## Image produit
- Si "IMAGE PRODUIT PRÉ-GÉNÉRÉE" est presente dans le contexte : utilise cette URL en <img> dans le hero ET product showcase.
- Si aucune image n'est disponible : utilise un placeholder CSS elegant (gradient + emoji adapte au produit).
- L'image est generee en amont par le systeme — tu n'as PAS besoin de la generer toi-meme.

## Niveau visuel attendu
- Utilise une grille responsive, de vrais espacements, une hierarchie typographique nette et des sections contrastees.
- Ajoute des details de design utiles : badges, preuves, micro-copy, cartes, mockups CSS si aucun asset n'existe.
- Pour SaaS : cree un mockup dashboard/interface en HTML/CSS dans le hero.
- Pour app : cree un mockup telephone en HTML/CSS avec 2-3 ecrans simules.
- Pour e-commerce : l'image produit, le prix/offre, la garantie/livraison et le CTA achat doivent etre visibles rapidement.
- Evite les phrases generiques comme "solution innovante", "boostez votre croissance" ou "transformez votre business".

## Sortie
- Ta reponse DOIT etre le HTML complet (<!DOCTYPE html>...</html>). Rien d'autre.
- Le systeme publie automatiquement ton HTML. N'appelle PAS deploy_site.
