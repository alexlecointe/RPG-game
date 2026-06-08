# Skill: ads_launch_plan — E-Commerce

## Objectif
Lancer une campagne Meta Ads optimisée pour un e-commerce (conversion ventes).

## Configuration
- **Objective**: `OUTCOME_SALES`
- **Call to action**: `SHOP_NOW`
- **Optimization goal**: `LINK_CLICKS`
- **Ciblage par défaut**: France, Belgique, Suisse (`["FR", "BE", "CH"]`)
- **Tranche d'âge**: 18-45 ans
- **Status initial**: `PAUSED` (review Meta avant activation)

## Angles créatifs recommandés
1. **Urgence / Offre limitée** : "Soldes -30% jusqu'à dimanche"
2. **Preuve sociale** : "3,200 clients satisfaits"
3. **Bénéfice direct** : "Livraison gratuite dès 39€"

## Structure des variants
| Variant | Angle | Headline (< 40 chars) | CTA |
|---------|-------|----------------------|-----|
| A | Urgence | "Offre Flash : -30% ce WE" | SHOP_NOW |
| B | Social proof | "Déjà 3200 clients !" | SHOP_NOW |
| C | Bénéfice | "Livraison gratuite dès 39€" | SHOP_NOW |

## Séquence d'appels meta_ads_action — Phase test (J1–J7)
1. `create_campaign` (OUTCOME_SALES, PAUSED)
2. `create_ad_set` (countries=["FR","BE","CH"], age_min=18, age_max=45)
3. `generate_video` × 3 (prompt 9:16, 15s, un par angle créatif)
4. `upload_video` × 3 (video_url depuis generate_video)
5. `create_ad_creative` × 3 (headline+body+SHOP_NOW par variant)
6. `create_ad` × 3 (une ad par variant)
7. `resume_campaign` (activation)

## Phase scale — Audience (J8+ si ROAS > 1.5x)
1. `create_custom_audience` (audience_name="Visiteurs 30j", audience_subtype="WEBSITE", retention_days=30)
2. `get_custom_audience` (custom_audience_id=...) — attendre `ready_for_targeting: true`
3. `create_lookalike_audience` (custom_audience_id=..., ratio=0.01, countries=["FR"])
4. `create_ad_set` avec `custom_audience_ids=[lookalike_id]` — nouveau ad set ciblage lookalike
5. Dupliquer les meilleures créatives vers ce nouvel ad set

## KPIs cibles (phase test, 7 jours)
- CPC < 0.50€
- CTR > 2%
- ROAS > 1.5x avant scaling
