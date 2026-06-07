# Skill: Templates de support client

## Objectif
Generer une bibliotheque de templates de reponses support client prets a l'emploi. Chaque template est personnalisable, empathique et guide le client vers une resolution claire.

## Structure attendue

### 1. Templates essentiels
- 10 templates minimum couvrant les cas suivants :
  - Bienvenue / premier contact
  - Accuse de reception d'une demande
  - Demande d'informations complementaires
  - Resolution positive (probleme resolu)
  - Resolution negative (impossible de resoudre)
  - Remboursement accepte
  - Remboursement refuse
  - Bug connu (workaround disponible)
  - Escalation vers un niveau superieur
  - Enquete de satisfaction post-resolution

### 2. Par template
- Objet de l'email (court, clair, pas de jargon)
- Corps du message avec tokens de personnalisation :
  - [prenom] : prenom du client
  - [probleme] : description du probleme rapporte
  - [solution] : solution apportee ou workaround
  - [delai] : temps estime de resolution
  - [lien] : lien vers ressource, article, ou page
- Ton : empathique, professionnel, humain
- Next step : action attendue du client ou de l'equipe

### 3. Personnalisation
- Liste des variables disponibles et leur description
- Quand personnaliser au-dela du template (cas complexes, VIP, escalation)
- Quand le template standard suffit (cas courants, volume eleve)

### 4. Guidelines
- Ton empathique : reconnaitre le probleme avant de proposer une solution
- Pas de jargon technique : ecrire comme on parle a un ami
- Toujours proposer un next step : ne jamais laisser le client sans direction
- Temps de reponse cible par type :
  - Urgent (bug bloquant, perte de donnees) : < 1h
  - Important (bug non bloquant, question facturation) : < 4h
  - Standard (question, feature request) : < 24h

## Regles
- Chaque template < 200 mots : respect du temps du client
- Toujours inclure un next step clair dans chaque template
- Ton humain, pas robotique : bannir les "Cher client" et les formules corporate
- Variables clairement marquees entre crochets [variable] pour faciliter le remplacement
