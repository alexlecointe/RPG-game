# Skill Expert: Landing Page Haute Conversion

## Objectif
Generer une landing page HTML/CSS complete, pixel-perfect et prete a deployer, qui maximise le taux de conversion en guidant le visiteur a travers un parcours psychologique precis. La page doit etre responsive, accessible, et chaque element doit servir un objectif de conversion mesurable. Le contenu doit etre 100% specifique a l'entreprise — zero placeholder.

## Framework
**AIDA (Attention, Interest, Desire, Action)** combine avec le **Above the Fold Principle**.

AIDA structure le parcours emotionnel du visiteur :
- **Attention** : capter en 3 secondes avec un hero magnetique (headline + visuel + CTA visible sans scroller)
- **Interest** : creer la connexion en nommant le probleme de la cible avec ses propres mots
- **Desire** : transformer l'interet en envie avec des benefices concrets et de la preuve sociale
- **Action** : eliminer les frictions avec FAQ, garanties, et un CTA final irresistible

Le Above the Fold Principle impose que le hero (headline + CTA + proposition de valeur) soit integralement visible sans aucun scroll sur desktop ET mobile. C'est la regle la plus critique : un visiteur qui ne comprend pas la valeur en 3 secondes quitte la page.

## Structure attendue

### 1. Architecture AIDA de la page

#### Hero section (Attention) — Au-dessus du fold
- **Headline magnetique** : max 8-10 mots, oriente benefice principal, pas le nom du produit
- **Sous-titre** : 1-2 phrases qui expliquent le "comment" (mecanisme de la solution)
- **CTA primaire** : bouton large, couleur contrastee, verbe d'action + benefice
- **Preuve sociale courte** : "Rejoint par 2,400+ entreprises" ou "Note 4.9/5 sur G2"
- **Hero visuel** : screenshot du produit, demo video, ou illustration — pas de stock photo generique
- Tout ceci DOIT etre visible sans scroller (tester a 768px de hauteur)

#### Section probleme (Interest)
- 3 pain points formules avec le langage de la cible ("Vous en avez assez de...")
- Statistiques si possible ("67% des equipes perdent 5h/semaine a...")
- Effet miroir : le visiteur doit se reconnaitre immediatement
- Transition naturelle vers la solution ("Et si vous pouviez...")

#### Section solution (Desire)
- Presentation du produit en 1 phrase
- 3-5 benefices (PAS des features) sous forme de cards avec icone
- Chaque benefice = resultat concret mesurable ("Gagnez 3h/jour", pas "IA avancee")
- Visuels du produit en contexte (screenshots, mockups)

#### Comment ca marche
- 3 etapes numerotees (simplicite = confiance)
- Icone + titre + description courte pour chaque etape
- Montrer que c'est facile et rapide

#### Social proof (Desire renforce)
- 3 temoignages minimum avec : nom reel, photo, role/entreprise, resultat chiffre
- Logos clients ou mentions presse (bande horizontale)
- Chiffres d'impact : "+150% de conversion", "10,000+ utilisateurs actifs"

#### Pricing (si applicable)
- 2-3 tiers maximum, le meilleur rapport qualite/prix mis en avant visuellement
- Toggle annuel/mensuel avec economie affichee ("Economisez 20%")
- Liste claire de ce qui est inclus par tier
- CTA par tier, le tier recommande a le bouton le plus visible

#### FAQ
- 5-8 questions couvrant : fonctionnement, prix, garantie, securite, support
- Reponses courtes (2-3 phrases max), rassurantes
- Structure accordeon si plus de 5 questions

#### Footer CTA
- Repetition de la proposition de valeur en 1 phrase
- CTA identique au hero (coherence)
- Urgence legere et ethique ("Offre de lancement — 30% les 100 premiers inscrits")
- Liens legaux (mentions, confidentialite)

### 2. Regles techniques HTML/CSS
- HTML5 semantique complet : `<!DOCTYPE html>` jusqu'a `</html>`
- Balises semantiques : `<header>`, `<main>`, `<section>`, `<footer>`, `<nav>`
- CSS dans une balise `<style>` en tete de document (pas de fichier externe)
- **Mobile-first** : styles de base pour mobile, `@media (min-width: 768px)` pour tablette, `@media (min-width: 1024px)` pour desktop
- Variables CSS pour les couleurs : `--primary`, `--accent`, `--text`, `--bg`, `--text-muted`
- Typographie : `system-ui, -apple-system, sans-serif` ou Google Fonts via CDN
- Max-width sur le contenu : `1200px` avec `margin: 0 auto`
- Accessibility : `alt` text sur toutes les images, contraste WCAG AA (ratio 4.5:1 minimum), `:focus` states visibles
- Animations CSS subtiles : `fadeInUp` au scroll, hover effects sur les boutons et cards
- Performance : pas de JS lourd, images avec `loading="lazy"`, pas de librairies externes
- Smooth scroll via CSS : `html { scroll-behavior: smooth; }`

### 3. Regles de copywriting
- **Formule headline** : [Resultat desire] sans [douleur principale] — ex: "Doublez vos ventes sans tripler votre equipe"
- **Bullet points** : toujours benefice > feature — pas "Nous avons une IA", mais "Vous gagnez 3h par jour"
- **CTA** : verbe d'action + benefice — "Commencer gratuitement", "Voir la demo", pas "S'inscrire" ou "Envoyer"
- **Ton** : confiant mais pas arrogant, specifique, conversationnel
- **Urgence** : ethique uniquement — offre de lancement limitee, places limitees si reel, jamais de faux compte a rebours
- **Microcopy** : sous les CTAs, rassurer — "Pas de carte bancaire requise", "Annulable a tout moment"

## Criteres de qualite (score 10/10)
- **HTML complet et valide** : de `<!DOCTYPE html>` a `</html>`, sans erreurs de syntaxe, balises semantiques
- **Hero section claire** : headline percutant + sous-titre + CTA visible au-dessus du fold, pas besoin de scroller
- **Responsive / mobile-friendly** : CSS mobile-first avec media queries, aucune largeur fixe en px sur les containers
- **Sections multiples** : hero, probleme, benefices, social proof, pricing, FAQ, footer CTA — structure AIDA complete
- **Contenu specifique** : zero placeholder, zero lorem ipsum, tout le texte est adapte a l'entreprise et son marche

## Exemple de sortie

```html
<section class="hero">
  <div class="container">
    <h1>Doublez vos reservations sans augmenter votre budget pub</h1>
    <p class="subtitle">
      Notre IA analyse vos disponibilites en temps reel et optimise
      automatiquement vos annonces sur 12 plateformes.
    </p>
    <a href="#pricing" class="cta-button">Essayer 14 jours gratuitement</a>
    <p class="microcopy">Pas de carte bancaire requise — Setup en 5 minutes</p>
    <div class="social-proof-bar">
      <span>⭐ 4.9/5 sur G2</span>
      <span>•</span>
      <span>2,400+ hotels nous font confiance</span>
    </div>
  </div>
</section>
```

```css
.hero {
  padding: 4rem 1.5rem;
  text-align: center;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
}
.hero h1 { font-size: clamp(1.8rem, 5vw, 3rem); max-width: 700px; margin: 0 auto; }
.cta-button {
  display: inline-block; padding: 1rem 2.5rem; border-radius: 8px;
  background: var(--accent); color: white; font-weight: 700;
  text-decoration: none; transition: transform 0.2s;
}
.cta-button:hover { transform: translateY(-2px); }
```

## Erreurs a eviter
- **Hero sans CTA visible** : le bouton d'action doit etre au-dessus du fold, pas cache 3 scrolls plus bas
- **Texte generique** : "Bienvenue sur notre site", "La meilleure solution du marche" — ca ne dit rien a personne
- **Features au lieu de benefices** : "IA avancee avec NLP" vs "Gagnez 3h par jour sur vos emails" — le visiteur veut le resultat
- **Pas de social proof** : sans temoignages ni chiffres, aucune credibilite — meme un "100+ utilisateurs" vaut mieux que rien
- **Design non responsive** : largeurs fixes en `px`, texte qui deborde sur mobile, boutons trop petits au touch
- **Trop de CTAs differents** : 1 action principale par page — "Commander" ET "S'inscrire" ET "Nous contacter" = confusion
- **Lorem ipsum ou placeholder** : tout le contenu doit etre reel et specifique a l'entreprise, jamais de texte d'attente

## Regles
- Le hero section doit etre integralement visible sans scroll sur un ecran de 768px de haut
- Tout le HTML doit etre dans un seul fichier, du `<!DOCTYPE html>` au `</html>`
- Le contenu doit etre 100% specifique a l'entreprise du contexte — aucun texte generique
- Chaque section doit avoir un objectif clair dans le parcours AIDA
- Le CTA principal doit apparaitre au minimum 2 fois : hero et footer
- Les couleurs doivent utiliser des variables CSS pour permettre la personnalisation facile
