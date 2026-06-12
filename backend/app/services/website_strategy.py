from __future__ import annotations

import json
import re
from typing import Any

import structlog

logger = structlog.get_logger()


PLAYBOOKS: dict[str, dict[str, Any]] = {
    "ecommerce_wellness_skincare": {
        "label": "E-commerce wellness / skincare",
        "best_for": ["creme", "soin", "skincare", "wellness", "sante", "nutrition", "supplement"],
        "vibe": "premium, naturel, rassurant, science + nature",
        "visual_system": {
            "palette": ["#f8f3ea", "#264533", "#d9825b", "#fefefe"],
            "typography": "serif editorial headlines + clean sans body",
            "photo_style": "photo produit premium en lumiere naturelle, pierre, ombres douces",
        },
        "sections": [
            "hero produit", "probleme", "benefices", "comment utiliser",
            "ingredients/preuves", "avis", "offre", "faq",
        ],
        "conversion_rules": [
            "prix visible au-dessus du fold", "CTA achat unique",
            "garantie et livraison visibles",
        ],
    },
    "ecommerce_fashion_lifestyle": {
        "label": "E-commerce fashion / lifestyle",
        "best_for": ["mode", "vetement", "bijou", "accessoire", "lifestyle", "maroquinerie"],
        "vibe": "editorial, desirabilite, luxe accessible, storytelling",
        "visual_system": {
            "palette": ["#faf7f2", "#111111", "#8a1538", "#d8c3a5"],
            "typography": "serif fin + sans minimaliste",
            "photo_style": "editorial magazine, flat lay ou mannequin, composition aerienne",
        },
        "sections": [
            "hero editorial", "collection", "matiere", "style guide",
            "preuve sociale", "offre", "faq",
        ],
        "conversion_rules": [
            "produit porte ou mis en scene", "benefice de style concret", "CTA achat clair",
        ],
    },
    "ecommerce_food_beverage": {
        "label": "E-commerce food / beverage",
        "best_for": ["food", "boisson", "snack", "cafe", "the", "sauce", "repas", "alimentaire"],
        "vibe": "gourmand, transparent, origine tracee, fun premium",
        "visual_system": {
            "palette": ["#fff8e7", "#243b2f", "#f2a541", "#c44536"],
            "typography": "humaniste, friendly, tres lisible",
            "photo_style": "overhead ingredients, lifestyle repas, couleurs appetissantes",
        },
        "sections": [
            "hero gourmand", "origine", "gout/benefices", "ingredients", "avis", "offre",
            "faq",
        ],
        "conversion_rules": [
            "mettre le gout en premier", "origine et qualite visibles", "CTA achat simple",
        ],
    },
    "ecommerce_tech_gadget": {
        "label": "E-commerce tech / gadget",
        "best_for": ["tech", "gadget", "outil", "objet connecte", "home", "device", "electronique"],
        "vibe": "clair, precis, innovation accessible, design produit",
        "visual_system": {
            "palette": ["#f7f8fb", "#15171a", "#246bfe", "#dfe5ee"],
            "typography": "Inter / Manrope, titres nets",
            "photo_style": "produit sur fond propre, close-up details, lifestyle utile",
        },
        "sections": [
            "hero produit", "probleme", "features", "details", "comparaison", "avis",
            "offre", "faq",
        ],
        "conversion_rules": [
            "montrer le produit en action", "benefices mesurables", "CTA achat visible",
        ],
    },
    "saas_b2b_productivity": {
        "label": "SaaS B2B productivity",
        "best_for": ["saas", "b2b", "productivite", "dashboard", "crm", "automation", "workflow"],
        "vibe": "sharp, fiable, productivite, execution moderne",
        "visual_system": {
            "palette": ["#f8fafc", "#111827", "#4f46e5", "#10b981"],
            "typography": "Inter / Plus Jakarta Sans",
            "photo_style": "mockup dashboard, UI cards, graphes, integrations",
        },
        "sections": [
            "hero avec mockup", "pain", "workflow", "features", "integrations",
            "pricing", "security", "faq",
        ],
        "conversion_rules": ["CTA trial/demo", "mockup UI obligatoire", "pricing ou demo visible"],
    },
    "saas_ai_tooling": {
        "label": "SaaS AI / tooling",
        "best_for": ["ai", "ia", "agent", "automation", "developer", "outil", "api", "data"],
        "vibe": "tech premium, rapide, intelligent, credible",
        "visual_system": {
            "palette": ["#080b12", "#f9fafb", "#7c3aed", "#22d3ee"],
            "typography": "Geist / Inter, contraste fort",
            "photo_style": "interface produit, terminal/dashboard stylise, glow subtil",
        },
        "sections": [
            "hero produit", "demo flow", "cas d'usage", "features", "integrations",
            "pricing", "faq",
        ],
        "conversion_rules": [
            "montrer l'output du produit", "CTA start/demo", "preuve technique credible",
        ],
    },
    "mobile_app": {
        "label": "Mobile app",
        "best_for": ["app", "mobile", "ios", "android", "application"],
        "vibe": "simple, tactile, lifestyle, benefice immediat",
        "visual_system": {
            "palette": ["#f7fbff", "#101828", "#2f80ed", "#ff7a59"],
            "typography": "rounded sans / Inter",
            "photo_style": "mockups iPhone avec ecrans cles, contexte humain",
        },
        "sections": [
            "hero mockup telephone", "benefices", "screens", "onboarding", "avis",
            "store CTA", "faq",
        ],
        "conversion_rules": [
            "mockup telephone obligatoire", "badges store ou waitlist", "3 screens simules",
        ],
    },
    "service_local_consultant": {
        "label": "Service local / consultant",
        "best_for": ["service", "consultant", "coach", "agence", "local", "freelance", "cabinet"],
        "vibe": "expert, humain, direct, confiance",
        "visual_system": {
            "palette": ["#fbfaf7", "#1f2933", "#b7791f", "#e2e8f0"],
            "typography": "serif sobre + sans lisible",
            "photo_style": "portrait/atelier/bureau, preuve terrain, ambiance professionnelle",
        },
        "sections": [
            "hero promesse", "problemes", "methode", "preuves", "offres",
            "temoignages", "contact",
        ],
        "conversion_rules": [
            "CTA appel/contact", "preuves et methode", "benefice business explicite",
        ],
    },
    "creator_personal_brand": {
        "label": "Creator / personal brand",
        "best_for": [
            "creator", "createur", "newsletter", "formation", "communaute",
            "personal brand", "coach",
        ],
        "vibe": "personnel, distinctif, communaute, autorite accessible",
        "visual_system": {
            "palette": ["#fffaf0", "#18181b", "#e11d48", "#facc15"],
            "typography": "display forte + sans claire",
            "photo_style": "portrait, preuve sociale, contenu, coulisses",
        },
        "sections": [
            "hero personnel", "credibilite", "offre", "contenu", "temoignages",
            "newsletter/achat", "faq",
        ],
        "conversion_rules": ["voix de marque forte", "preuve sociale", "CTA subscribe/buy"],
    },
}


BENCHMARK_PATTERNS = [
    "hero avec promesse ultra claire, preuve courte et CTA au-dessus du fold",
    "visuel principal qui montre le produit, l'interface ou le résultat final",
    "sections scannables avec titres courts, bénéfices concrets et micro-preuves",
    "pricing/offre visible sans chercher, avec garantie ou réduction de risque",
    "design system cohérent: palette courte, typo définie, espacements généreux",
]


PLAYBOOK_DNA: dict[str, dict[str, Any]] = {
    "ecommerce_wellness_skincare": {
        "hero_pattern": "split editorial: copy rassurante + photo produit premium très grande",
        "layout_recipe": "fonds ivoire, sections aérées, cartes fines, badges science/nature",
        "mandatory_visuals": ["photo produit hero", "product showcase", "badges confiance"],
        "section_blueprint": [
            "nav sticky minimal", "hero produit + prix", "douleur cible", "bénéfices sensoriels",
            "mode d'utilisation", "ingrédients/preuves", "avis", "offre + garantie", "faq",
        ],
        "quality_rules": [
            "le produit doit être visible au premier écran",
            "le prix ou l'offre doit être proche du CTA",
            "le ton doit être premium et précis, jamais médical non prouvé",
        ],
        "anti_patterns": ["fond générique bleu/violet SaaS", "emoji produit", "waitlist"],
    },
    "ecommerce_fashion_lifestyle": {
        "hero_pattern": "hero magazine avec nom de collection, visuel lifestyle et CTA boutique",
        "layout_recipe": "grille éditoriale, grands blancs, détails matière, typo luxe",
        "mandatory_visuals": ["image produit portée ou flat lay", "détails matière", "look/style block"],
        "section_blueprint": [
            "nav boutique", "hero editorial", "collection", "matière", "style guide",
            "social proof", "offre", "faq",
        ],
        "quality_rules": [
            "le site doit donner envie avant d'expliquer",
            "le copy doit parler de style, usage et désirabilité",
            "les sections doivent ressembler à une marque, pas à un SaaS",
        ],
        "anti_patterns": ["cartes features trop tech", "couleurs startup", "copy trop utilitaire"],
    },
    "ecommerce_food_beverage": {
        "hero_pattern": "hero gourmand avec produit + ingrédients + promesse goût",
        "layout_recipe": "couleurs appétissantes, formes organiques, preuves d'origine",
        "mandatory_visuals": ["packshot produit", "ingrédients", "moment de consommation"],
        "section_blueprint": [
            "nav courte", "hero goût", "origine", "bénéfices", "ingrédients",
            "avis", "offre", "faq",
        ],
        "quality_rules": [
            "le goût et l'origine doivent être compréhensibles immédiatement",
            "les ingrédients doivent être concrets",
            "le CTA doit rester achat, pas inscription",
        ],
        "anti_patterns": ["ton médical", "site froid corporate", "absence de produit visuel"],
    },
    "ecommerce_tech_gadget": {
        "hero_pattern": "hero produit net avec close-up, bénéfice mesurable et CTA achat",
        "layout_recipe": "surface claire, contraste précis, fiches détails, comparaison",
        "mandatory_visuals": ["produit en action", "close-up détail", "comparaison avant/après"],
        "section_blueprint": [
            "nav product-led", "hero produit", "problème", "features utiles",
            "détails techniques", "comparaison", "avis", "offre",
        ],
        "quality_rules": [
            "chaque feature doit être liée à un résultat utilisateur",
            "la page doit montrer comment le produit s'utilise",
            "le design doit être clean, pas gadget cheap",
        ],
        "anti_patterns": ["trop de jargon", "visuel abstrait", "pricing caché"],
    },
    "saas_b2b_productivity": {
        "hero_pattern": "hero SaaS avec dashboard mockup, promesse business et double CTA",
        "layout_recipe": "UI preview dense, logos/intégrations, pricing cards, section sécurité",
        "mandatory_visuals": ["mockup dashboard", "workflow UI", "logos intégrations"],
        "section_blueprint": [
            "nav SaaS", "hero + mockup", "pain business", "workflow", "features",
            "integrations", "pricing", "security", "faq",
        ],
        "quality_rules": [
            "un mockup UI doit apparaître au-dessus du fold",
            "les bénéfices doivent être mesurables",
            "trial/demo/pricing doivent être clairs",
        ],
        "anti_patterns": ["site e-commerce", "pas de UI produit", "promesse vague d'IA"],
    },
    "saas_ai_tooling": {
        "hero_pattern": "hero dark/premium avec démo output, agent flow ou terminal/dashboard",
        "layout_recipe": "contraste fort, UI cards, snippets, use cases, preuves techniques",
        "mandatory_visuals": ["output produit", "flow IA", "mockup interface"],
        "section_blueprint": [
            "nav dev/pro", "hero demo", "cas d'usage", "flow", "features",
            "integrations/API", "pricing", "faq",
        ],
        "quality_rules": [
            "montrer ce que l'IA produit concrètement",
            "éviter les promesses IA génériques",
            "inclure une preuve de workflow ou d'intégration",
        ],
        "anti_patterns": ["AI buzzwords sans démo", "fond gradient vide", "pas de CTA"],
    },
    "mobile_app": {
        "hero_pattern": "hero avec iPhone mockup et 2-3 écrans simulés",
        "layout_recipe": "layout tactile, cards arrondies, onboarding, badges store/waitlist",
        "mandatory_visuals": ["mockup téléphone", "screens app", "onboarding preview"],
        "section_blueprint": [
            "nav app", "hero téléphone", "bénéfices", "screens", "onboarding",
            "avis", "store CTA", "faq",
        ],
        "quality_rules": [
            "le téléphone doit être visible au premier écran",
            "les screens doivent expliquer l'app sans lire tout le texte",
            "le CTA doit être download, waitlist ou essai",
        ],
        "anti_patterns": ["page sans mockup", "site SaaS desktop", "features trop longues"],
    },
    "service_local_consultant": {
        "hero_pattern": "hero expert humain avec résultat promis, preuve et CTA contact",
        "layout_recipe": "confiance, méthode en étapes, preuves terrain, offres simples",
        "mandatory_visuals": ["portrait ou scène métier", "méthode", "témoignages"],
        "section_blueprint": [
            "nav confiance", "hero promesse", "problèmes", "méthode", "preuves",
            "offres", "témoignages", "contact",
        ],
        "quality_rules": [
            "la méthode doit être claire",
            "les preuves doivent être crédibles",
            "le CTA doit inviter à appeler, réserver ou demander un devis",
        ],
        "anti_patterns": ["trop startup", "pricing SaaS", "absence d'humain"],
    },
    "creator_personal_brand": {
        "hero_pattern": "hero personnel avec point de vue fort, preuve sociale et CTA communauté",
        "layout_recipe": "voix distinctive, blocs contenu, social proof, offre claire",
        "mandatory_visuals": ["portrait ou signature visuelle", "contenus", "preuve sociale"],
        "section_blueprint": [
            "nav creator", "hero personnel", "crédibilité", "contenu", "offre",
            "témoignages", "newsletter/achat", "faq",
        ],
        "quality_rules": [
            "la voix doit sembler humaine et singulière",
            "la crédibilité doit apparaître vite",
            "le CTA doit être subscribe, rejoindre ou acheter",
        ],
        "anti_patterns": ["ton corporate", "site sans personnalité", "copy générique"],
    },
}


def _with_design_dna(key: str, playbook: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(playbook)
    enriched["benchmark_patterns"] = BENCHMARK_PATTERNS
    enriched.update(PLAYBOOK_DNA.get(key, {}))
    return enriched


def infer_playbook_key(business_type: str, text: str) -> str:
    haystack = f"{business_type} {text}".lower()
    if business_type == "saas":
        if any(k in haystack for k in ["ai", "ia", "agent", "developer", "api", "data"]):
            return "saas_ai_tooling"
        return "saas_b2b_productivity"
    if business_type == "app":
        return "mobile_app"
    for key, playbook in PLAYBOOKS.items():
        if key.startswith("ecommerce") and any(k in haystack for k in playbook["best_for"]):
            return key
    if any(k in haystack for k in PLAYBOOKS["service_local_consultant"]["best_for"]):
        return "service_local_consultant"
    if any(k in haystack for k in PLAYBOOKS["creator_personal_brand"]["best_for"]):
        return "creator_personal_brand"
    return (
        "ecommerce_wellness_skincare"
        if business_type == "ecommerce"
        else "saas_b2b_productivity"
    )


def fallback_site_spec(
    *,
    company_name: str,
    mission_statement: str,
    product_description: str,
    target_audience: str,
    business_type: str,
    stripe_checkout_url: str = "",
    revision_request: str = "",
    previous_spec_json: str = "",
) -> dict[str, Any]:
    text = " ".join([
        company_name, mission_statement, product_description, target_audience, revision_request,
    ])
    key = infer_playbook_key(business_type, text)
    playbook = _with_design_dna(key, PLAYBOOKS[key])
    product_image_prompt = build_product_image_prompt(
        company_name=company_name,
        product_description=product_description,
        target_audience=target_audience,
        business_type=business_type,
        visual_style=playbook["visual_system"]["photo_style"],
    )
    return {
        "playbook_key": key,
        "playbook_label": playbook["label"],
        "business_type": business_type,
        "brand_vibe": playbook["vibe"],
        "visual_system": playbook["visual_system"],
        "benchmark_patterns": playbook["benchmark_patterns"],
        "hero_pattern": playbook["hero_pattern"],
        "layout_recipe": playbook["layout_recipe"],
        "sections": playbook["sections"],
        "section_blueprint": playbook["section_blueprint"],
        "cta": {
            "primary_label": "Commander" if business_type == "ecommerce" else "Essayer maintenant",
            "primary_url": stripe_checkout_url or (
                "https://buy.stripe.com/PLACEHOLDER"
                if business_type == "ecommerce"
                else "#contact"
            ),
        },
        "trust_signals": playbook["conversion_rules"],
        "mandatory_visuals": playbook["mandatory_visuals"],
        "quality_rules": playbook["quality_rules"],
        "anti_patterns": playbook["anti_patterns"],
        "asset_direction": playbook["visual_system"]["photo_style"],
        "image_prompt": product_image_prompt,
        "copy_angles": [
            "problème spécifique de la cible",
            "résultat concret après usage",
            "preuve ou réduction de risque",
        ],
        "revision_request": revision_request,
        "previous_spec_available": bool(previous_spec_json),
    }


async def generate_site_spec(
    *,
    company_name: str,
    mission_statement: str,
    product_description: str,
    target_audience: str,
    business_type: str,
    market_scan: str = "",
    stripe_checkout_url: str = "",
    revision_request: str = "",
    previous_spec_json: str = "",
) -> str:
    from app.agents.llm_client import call_simple
    from app.core.config import get_settings

    fallback = fallback_site_spec(
        company_name=company_name,
        mission_statement=mission_statement,
        product_description=product_description,
        target_audience=target_audience,
        business_type=business_type,
        stripe_checkout_url=stripe_checkout_url,
        revision_request=revision_request,
        previous_spec_json=previous_spec_json,
    )
    settings = get_settings()
    if not settings.openai_api_key and not settings.anthropic_api_key:
        return json.dumps(fallback, ensure_ascii=False, indent=2)

    provider = "openai" if settings.openai_api_key else "anthropic"
    playbook_summaries = {
        key: {
            "label": value["label"],
            "best_for": value["best_for"],
            "vibe": enriched["vibe"],
            "sections": enriched["sections"],
            "visual_system": enriched["visual_system"],
            "conversion_rules": enriched["conversion_rules"],
            "hero_pattern": enriched["hero_pattern"],
            "layout_recipe": enriched["layout_recipe"],
            "mandatory_visuals": enriched["mandatory_visuals"],
            "quality_rules": enriched["quality_rules"],
            "anti_patterns": enriched["anti_patterns"],
        }
        for key, value in PLAYBOOKS.items()
        for enriched in [_with_design_dna(key, value)]
    }
    system_prompt = (
        "Tu es un directeur artistique senior et CRO strategist. "
        "Tu transformes un business en spec de landing page premium, specifique et executable. "
        "Tu reponds uniquement en JSON valide."
    )
    user_msg = f"""
Business: {company_name}
Type: {business_type}
Mission: {mission_statement}
Produit: {product_description or '(non precise)'}
Audience: {target_audience or '(non precisee)'}
Checkout URL: {stripe_checkout_url or '(aucune)'}
Demande de revision: {revision_request or '(premiere generation)'}

Playbooks disponibles:
{json.dumps(playbook_summaries, ensure_ascii=False)}

Extrait market scan:
{market_scan[:1200] if market_scan else '(aucun)'}

Spec precedente, si revision:
{previous_spec_json[:3000] if previous_spec_json else '(aucune)'}

Retourne un JSON avec exactement ces cles:
playbook_key, playbook_label, business_type, brand_vibe, visual_system,
benchmark_patterns, hero_pattern, layout_recipe, sections, section_blueprint,
cta, trust_signals, mandatory_visuals, quality_rules, anti_patterns,
asset_direction, image_prompt, copy_angles, revision_request.

Regles:
- Choisis UN playbook_key dans la liste.
- Sois tres specifique au produit, jamais generique.
- Pour ecommerce: CTA achat, prix/offre si possible, image produit centrale.
- Pour ecommerce: image_prompt doit decrire un packshot produit exact, pas une scene lifestyle.
- Pour ecommerce: interdit dans image_prompt: personne, sportif, cycliste, avant/apres, selfie, photo client, mannequin, visage.
- Pour SaaS: mockup UI, trial/demo, pricing ou demo.
- Pour app: mockup telephone et screens simules.
- Le hero_pattern, mandatory_visuals et quality_rules sont obligatoires.
- L'image_prompt doit être un brief photo/UI précis, pas une phrase générique.
- Si revision_request est presente, garde ce qui marche et change seulement ce qui est demande.
"""
    try:
        resp = await call_simple(system_prompt, user_msg, provider=provider, max_tokens=1400)
        content = resp.content.strip()
        if "```" in content:
            match = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL)
            if match:
                content = match.group(1).strip()
        parsed = json.loads(content)
        if parsed.get("playbook_key") not in PLAYBOOKS:
            parsed["playbook_key"] = fallback["playbook_key"]
            parsed["playbook_label"] = fallback["playbook_label"]
        visual_system = parsed.get("visual_system") if isinstance(parsed.get("visual_system"), dict) else {}
        parsed["image_prompt"] = build_product_image_prompt(
            company_name=company_name,
            product_description=product_description,
            target_audience=target_audience,
            business_type=business_type,
            visual_style=str(
                visual_system.get("photo_style")
                or parsed.get("asset_direction")
                or fallback.get("asset_direction")
                or ""
            ),
        )
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("site_spec_generation_failed", error=str(exc))
        return json.dumps(fallback, ensure_ascii=False, indent=2)


def build_product_image_prompt(
    *,
    company_name: str,
    product_description: str,
    target_audience: str = "",
    business_type: str = "ecommerce",
    visual_style: str = "",
) -> str:
    product = (product_description or company_name or "the product").strip()
    audience = (target_audience or "customers").strip()
    style = (visual_style or "premium studio product photography").strip()

    if business_type == "ecommerce":
        return (
            f"Premium studio packshot of the actual product: {product}. "
            f"Brand name on packaging: {company_name}. "
            "Show only the packaged product as a clean commercial product photo, "
            "for example a tube, jar, bottle, box, or applicator depending on the product. "
            f"Visual style: {style}. "
            "Soft natural light, clean premium background, realistic ecommerce hero image, "
            "sharp focus, no clutter. "
            f"Intended audience context: {audience}, but do not show people. "
            "STRICT NEGATIVE: no humans, no faces, no athletes, no cyclist, no bicycle, "
            "no selfie, no mirror photo, no before-after transformation, no stock photo, "
            "no body parts unless the product itself requires a small neutral usage detail, "
            "no unrelated lifestyle scene, no random sports outfit."
        )

    if business_type == "saas":
        return (
            f"Premium UI mockup for {company_name}, a software product about {product}. "
            "Show a realistic dashboard interface, charts, cards, workflow panels, "
            "clean SaaS hero composition, no people, no stock photo."
        )

    if business_type == "app":
        return (
            f"Premium mobile app mockup for {company_name}, product: {product}. "
            "Show smartphone screens with a realistic UI, clean background, no people."
        )

    return (
        f"Premium brand visual for {company_name}: {product}. "
        f"Visual style: {style}. Clean professional composition, no unrelated stock photo."
    )
