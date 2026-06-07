# Skill: Suivi budgetaire

## Objectif
Produire un tableau de bord budgetaire clair avec alertes, comparaisons et recommandations d'optimisation. Permettre de prendre des decisions financieres rapides et informees.

## Structure attendue

### 1. Snapshot
- Depenses totales du mois en cours vs budget alloue
- Pourcentage consomme du budget mensuel
- Projection fin de mois (au rythme actuel)
- Comparaison avec le mois precedent (delta et tendance)

### 2. Par categorie
- Ventilation par poste : marketing, tools/SaaS, salaires, infrastructure
- Pour chaque categorie : montant reel, budget prevu, ecart (montant et %)
- Indicateur visuel : ✅ dans les clous, ⚠️ attention (>80%), 🔴 depassement (>100%)

### 3. Alertes
- Categories en depassement de plus de 10% du budget
- Categories sous-utilisees (< 50% du budget a mi-mois)
- Depenses imprevues ou anormales detectees
- Comparaison avec la moyenne des 3 derniers mois

### 4. Optimisations
- 2 a 3 recommandations de reallocation budgetaire
- Economies possibles identifiees (outils redondants, plans a downgrader, depenses non essentielles)
- ROI estime de chaque optimisation proposee

### 5. Cash runway
- Mois restants au burn rate actuel
- Scenario optimiste vs pessimiste
- Seuil d'alerte si runway < 6 mois

## Regles
- Chiffres precis quand disponibles, clairement marques comme estimes sinon
- Alertes visuelles pour les ecarts significatifs (emojis ou marqueurs)
- Toujours comparer au mois precedent pour donner du contexte
- Recommandations actionnables : pas de "reduire les couts" mais "passer le plan Slack de Business+ a Pro = -200€/mois"
