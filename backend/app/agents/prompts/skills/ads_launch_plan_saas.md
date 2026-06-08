# Skill: ads_launch_plan — SaaS

## Objectif
Lancer une campagne Meta Ads optimisée pour la génération de leads SaaS (essais gratuits, démos).

## Configuration
- **Objective**: `OUTCOME_LEADS`
- **Call to action**: `LEARN_MORE` (ou `SIGN_UP` pour essai gratuit)
- **Optimization goal**: `LEAD_GENERATION`
- **Ciblage par défaut**: France, Belgique, Suisse (`["FR", "BE", "CH"]`)
- **Tranche d'âge**: 25-55 ans (décideurs, founders, managers)
- **Status initial**: `PAUSED` (review Meta avant activation)

## Angles créatifs recommandés
1. **ROI / Gain de temps** : "Économise 10h/semaine"
2. **Essai gratuit sans CB** : "14 jours gratuit, sans CB"
3. **Comparaison concurrente** : "2x moins cher que [concurrent]"

## Structure des variants
| Variant | Angle | Headline (< 40 chars) | CTA |
|---------|-------|----------------------|-----|
| A | ROI | "Gagne 10h/semaine — essaie" | LEARN_MORE |
| B | Gratuit | "14j gratuit, sans CB" | SIGN_UP |
| C | Comparaison | "2x moins cher que Notion" | LEARN_MORE |

## Séquence d'appels meta_ads_action — Phase test (J1–J7)
1. `create_campaign` (OUTCOME_LEADS, PAUSED)
2. `create_ad_set` (countries=["FR","BE","CH"], age_min=25, age_max=55)
3. `generate_video` × 3 (prompt 9:16, 30s — demo produit, ROI, essai gratuit)
4. `upload_video` × 3 (video_url depuis generate_video)
5. `create_ad_creative` × 3 (headline+body+LEARN_MORE/SIGN_UP par variant)
6. `create_ad` × 3 (une ad par variant)
7. `resume_campaign` (activation)

## Phase scale — Audience (J8+ si CPL < 10€)
1. `create_custom_audience` (audience_name="Visiteurs landing 30j", audience_subtype="WEBSITE", retention_days=30)
2. `get_custom_audience` — attendre `ready_for_targeting: true` (peut prendre 1h+)
3. `create_lookalike_audience` (custom_audience_id=..., ratio=0.02, countries=["FR","BE"])
4. `create_ad_set` avec `custom_audience_ids=[lookalike_id]` — ciblage lookalike prospects qualifiés
5. Allouer 30% du budget au nouvel ad set lookalike

## KPIs cibles (phase test, 7 jours)
- CPL (Cost Per Lead) < 10€
- CTR > 1%
- Trial-to-paid > 20%
