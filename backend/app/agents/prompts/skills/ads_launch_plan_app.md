# Skill: ads_launch_plan — App Mobile

## Objectif
Lancer une campagne Meta Ads optimisée pour l'install d'une app mobile.

## Configuration
- **Objective**: `OUTCOME_APP_INSTALLS`
- **Call to action**: `DOWNLOAD`
- **Optimization goal**: `APP_INSTALLS`
- **Ciblage par défaut**: France, Belgique (`["FR", "BE"]`)
- **Tranche d'âge**: 18-35 ans (early adopters tech)
- **Status initial**: `PAUSED` (review Meta avant activation)

## Angles créatifs recommandés
1. **Problème → Solution** : "Fini de galérer avec X"
2. **Démonstration screen** : Capture d'écran de l'app en action
3. **Social proof** : "Noté 4.8/5 sur l'App Store"

## Structure des variants
| Variant | Angle | Headline (< 40 chars) | CTA |
|---------|-------|----------------------|-----|
| A | Problème | "Fini de perdre du temps !" | DOWNLOAD |
| B | Demo | "Essaie 14 jours gratuit" | DOWNLOAD |
| C | Social proof | "4.8 ★ — 10k+ utilisateurs" | DOWNLOAD |

## Séquence d'appels meta_ads_action — Phase test (J1–J7)
1. `create_campaign` (OUTCOME_APP_INSTALLS, PAUSED)
2. `create_ad_set` (countries=["FR","BE"], age_min=18, age_max=35)
3. `generate_video` × 3 (prompt 9:16, 15s — screen demo, problème, social proof)
4. `upload_video` × 3 (video_url depuis generate_video)
5. `create_ad_creative` × 3 (headline+body+DOWNLOAD par variant)
6. `create_ad` × 3 (une ad par variant)
7. `resume_campaign` (activation)

## Phase scale — Audience (J8+ si CPI < 2€)
1. `create_custom_audience` (audience_name="Engagés page app", audience_subtype="ENGAGEMENT", retention_days=60)
2. `get_custom_audience` — attendre `ready_for_targeting: true`
3. `create_lookalike_audience` (custom_audience_id=..., ratio=0.02, countries=["FR"])
4. `create_ad_set` avec `custom_audience_ids=[lookalike_id]` — ciblage lookalike early adopters
5. Augmenter budget × 1.5 sur l'ad set lookalike

## KPIs cibles (phase test, 7 jours)
- CPI (Cost Per Install) < 2€
- CTR > 1.5%
- Day-1 retention > 40%
