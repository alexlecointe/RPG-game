from app.agents.base import AgentResult, BaseAgent


class ContentAgent(BaseAgent):
    agent_id = "content"

    async def run(self, mission_type: str, company_name: str, mission_statement: str) -> AgentResult:
        if mission_type == "blog_article":
            md = f"""# {mission_statement or "Comment " + company_name + " revolutionne votre quotidien"}

*Temps de lecture : 5 min*

## Le probleme que personne n'ose adresser

Dans un monde ou la productivite est reine, trop d'equipes perdent encore des heures sur des taches repetitives. C'est exactement le probleme que {company_name} resout.

## Notre approche

Plutot que d'ajouter un outil de plus a votre stack, {company_name} automatise intelligemment les flux de travail existants.

### Les 3 piliers
1. **Automatisation contextuelle** -- L'IA comprend votre metier
2. **Integration native** -- Se branche sur vos outils existants
3. **Resultats mesurables** -- ROI visible des la premiere semaine

## Temoignage client

> "En 2 semaines, on a economise 15h par personne et par mois." -- Marie D., COO

## Conclusion

{company_name} n'est pas juste un outil, c'est votre nouveau collegue IA. Essayez gratuitement.

[CTA : Demarrer maintenant]
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        if mission_type == "brand_design":
            md = f"""# Charte Graphique -- {company_name}

## Palette de couleurs
| Nom | Hex | Usage |
|-----|-----|-------|
| Primaire | #2563EB | Boutons, CTA, liens |
| Secondaire | #10B981 | Succes, confirmations |
| Accent | #F59E0B | Badges, notifications |
| Fond | #0F172A | Background principal |
| Texte | #F8FAFC | Texte sur fond sombre |

## Typographie
- **Titres** : Inter Bold, 24-32px
- **Corps** : Inter Regular, 14-16px
- **Code** : JetBrains Mono, 13px

## Ton de voix
- Professionnel mais accessible
- Direct et actionnable
- Enthousiaste sans etre excessif

## Mood Board
- Esthetique tech/startup moderne
- Espaces genereux, design minimaliste
- Photos lifestyle du produit en situation
- Icones flat design avec coins arrondis

## Logo Brief
- Symbole : forme geometrique evoquant la croissance
- Couleur primaire sur fond sombre
- Declinaisons : horizontal, vertical, icone seule
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        if mission_type == "ad_creation":
            md = f"""# Variantes Publicitaires -- {company_name}

## Variante 1 — Angle "Probleme/Solution"
- **Headline** : Fini les galeres
- **Body** : Tu perds du temps sur des taches repetitives ? {company_name} automatise tout en 5 min. Teste gratuitement.
- **CTA** : Essayer maintenant
- **Image** : Split screen — gauche: bureau encombre, droite: dashboard clean

## Variante 2 — Angle "Social Proof"
- **Headline** : +500 utilisateurs conquis
- **Body** : Rejoins les fondateurs qui ont deja automatise leur business avec {company_name}. Resultats des la premiere semaine.
- **CTA** : Rejoindre la communaute
- **Image** : Collage de temoignages clients avec photo et citation

## Variante 3 — Angle "Urgence"
- **Headline** : Tes concurrents avancent
- **Body** : Pendant que tu hesites, d'autres automatisent deja. {company_name} — lance-toi en 5 minutes.
- **CTA** : Commencer gratuit
- **Image** : Timeline montrant la progression rapide vs lente

## Variante 4 — Angle "ROI"
- **Headline** : 15h/semaine gagnees
- **Body** : C'est le temps moyen economise par nos utilisateurs. Imagine ce que tu ferais avec 15h de plus.
- **CTA** : Calculer mon ROI
- **Image** : Horloge avec fleche vers le haut, metriques positives

## Variante 5 — Angle "Simplicite"
- **Headline** : Zero code, 100% magie
- **Body** : Pas besoin d'etre dev. {company_name} fait le taf pendant que tu te concentres sur ta vision.
- **CTA** : Voir la demo
- **Image** : Interface app avec drag & drop intuitif
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        if mission_type == "image_brief":
            md = f"""# Brief Visuel -- {company_name}

## Hero Image
- **Format** : 1200x630px (OG/Social)
- **Style** : Flat design, couleurs vives
- **Elements** : Logo {company_name} centre, illustration abstraite de productivite
- **Palette** : Bleu principal (#2563EB), accents or (#F59E0B)

## Pack Icones (x6)
1. Dashboard -- ecran avec graphiques
2. Automatisation -- engrenages + eclair
3. Equipe -- 3 personnages collaborant
4. Croissance -- fleche montante
5. Securite -- bouclier + verrou
6. Support -- bulle de chat

## Banniere Ads
- **Format** : 1080x1080 (Instagram), 1200x628 (Facebook)
- **Headline visuelle** : "{mission_statement or company_name}"
- **CTA overlay** : "Essai gratuit"
"""
            return AgentResult(format="markdown", content=md, metadata={"mock": True})

        md = f"""# Document -- {company_name}

## {mission_statement or "Document genere"}

Ce document a ete cree par le Scribe de {company_name}.
Contenu a personnaliser selon vos besoins.
"""
        return AgentResult(format="markdown", content=md, metadata={"mock": True})
