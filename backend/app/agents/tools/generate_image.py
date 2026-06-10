"""Tool: generate_image — AI image generation via Replicate API.

Uses the flux-schnell model for fast, high-quality image generation.
Returns a URL to the generated image.
"""
from __future__ import annotations

import json

import httpx

from app.agents.tools import ToolDefinition

GENERATE_IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": (
                "Detailed description of the image to generate. "
                "Include style, mood, colors, and subject."
            ),
        },
        "width": {
            "type": "integer",
            "description": "Image width in pixels (default 1024).",
            "default": 1024,
        },
        "height": {
            "type": "integer",
            "description": "Image height in pixels (default 1024).",
            "default": 1024,
        },
    },
    "required": ["prompt"],
}

REPLICATE_API = "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"


async def _execute_generate_image(
    api_token: str,
    prompt: str,
    width: int = 1024,
    height: int = 1024,
) -> str:
    width = max(256, min(width, 1440))
    height = max(256, min(height, 1440))

    input_params: dict = {
        "prompt": prompt,
        "go_fast": True,
        "num_outputs": 1,
        "output_format": "webp",
        "output_quality": 80,
    }

    if width == height and width == 1024:
        input_params["aspect_ratio"] = "1:1"
    elif width == height:
        input_params["aspect_ratio"] = "1:1"
        input_params["width"] = width
        input_params["height"] = height
    else:
        input_params["aspect_ratio"] = "custom"
        input_params["width"] = width
        input_params["height"] = height

    async with httpx.AsyncClient(timeout=120) as client:
        create_resp = await client.post(
            REPLICATE_API,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Prefer": "wait",
            },
            json={"input": input_params},
        )
        create_resp.raise_for_status()
        data = create_resp.json()

    output = data.get("output")
    if isinstance(output, list) and output:
        image_url = output[0]
    elif isinstance(output, str):
        image_url = output
    else:
        return json.dumps({"error": "No image generated", "raw": str(data)[:500]})

    return json.dumps({
        "generated": True,
        "image_url": image_url,
        "prompt": prompt[:200],
        "dimensions": f"{width}x{height}",
    })


def create_generate_image_tool(api_token: str, company_id: str = "") -> ToolDefinition:
    async def execute(prompt: str, width: int = 1024, height: int = 1024) -> str:
        import structlog as _slog
        _log = _slog.get_logger()

        # Pre-debit 1 credit before calling Replicate (Polsia: block if no credits)
        debited = False
        if company_id:
            try:
                from app.core.database import SessionLocal
                from app.services.billing import debit_credit, get_or_create_subscription
                from app.services.company import CompanyService
                async with SessionLocal() as db:
                    company_svc = CompanyService(db)
                    company = await company_svc.get_company(company_id)
                    if company:
                        sub = await get_or_create_subscription(db, company)
                        await debit_credit(db, sub)
                        await db.commit()
                        debited = True
                        _log.info("image_credit_pre_debited", company_id=company_id)
            except ValueError:
                return json.dumps({
                    "generated": False,
                    "image_url": None,
                    "css_placeholder": (
                        "<div style=\"width:100%;max-width:480px;aspect-ratio:4/3;"
                        "background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);"
                        "border-radius:12px;display:flex;align-items:center;justify-content:center;"
                        "font-size:3em;\">🛍️</div>"
                    ),
                    "instruction": (
                        "No credits available for image generation. "
                        "IMPORTANT: use the css_placeholder HTML directly instead of an <img> tag. "
                        "You MUST still generate the complete HTML landing page and call deploy_site."
                    ),
                })
            except Exception as exc:
                _log.warning("image_credit_pre_debit_error", company_id=company_id, error=str(exc))

        try:
            result_json = await _execute_generate_image(api_token, prompt, width, height)
        except Exception as exc:
            # Generation failed — refund the pre-debited credit
            if debited and company_id:
                try:
                    from app.core.database import SessionLocal
                    from app.services.billing import get_or_create_subscription
                    from app.services.company import CompanyService
                    async with SessionLocal() as db:
                        company_svc = CompanyService(db)
                        company = await company_svc.get_company(company_id)
                        if company:
                            sub = await get_or_create_subscription(db, company)
                            sub.pack_credits = (sub.pack_credits or 0) + 1
                            await db.commit()
                            _log.info("image_credit_refunded", company_id=company_id)
                except Exception:
                    pass
            # Return a usable CSS placeholder instead of raising — the agent MUST continue
            _log.warning("generate_image_fallback", error=str(exc))
            return json.dumps({
                "generated": False,
                "image_url": None,
                "css_placeholder": (
                    "<div style=\"width:100%;max-width:480px;aspect-ratio:4/3;"
                    "background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);"
                    "border-radius:12px;display:flex;align-items:center;justify-content:center;"
                    "font-size:3em;\">🛍️</div>"
                ),
                "instruction": (
                    "Image generation is unavailable. "
                    "IMPORTANT: use the css_placeholder HTML directly in the page instead of an <img> tag. "
                    "You MUST still generate the complete HTML landing page and call deploy_site."
                ),
            })

        # Check Replicate returned an error payload — refund if so and add CSS fallback
        import json as _json
        parsed = _json.loads(result_json) if result_json else {}
        if parsed.get("error") and not parsed.get("generated"):
            if debited and company_id:
                try:
                    from app.core.database import SessionLocal
                    from app.services.billing import get_or_create_subscription
                    from app.services.company import CompanyService
                    async with SessionLocal() as db:
                        company_svc = CompanyService(db)
                        company = await company_svc.get_company(company_id)
                        if company:
                            sub = await get_or_create_subscription(db, company)
                            sub.pack_credits = (sub.pack_credits or 0) + 1
                            await db.commit()
                            _log.info("image_credit_refunded_no_output", company_id=company_id)
                except Exception:
                    pass
            return json.dumps({
                "generated": False,
                "image_url": None,
                "css_placeholder": (
                    "<div style=\"width:100%;max-width:480px;aspect-ratio:4/3;"
                    "background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);"
                    "border-radius:12px;display:flex;align-items:center;justify-content:center;"
                    "font-size:3em;\">🛍️</div>"
                ),
                "instruction": (
                    "Image generation is unavailable. "
                    "IMPORTANT: use the css_placeholder HTML directly in the page instead of an <img> tag. "
                    "You MUST still generate the complete HTML landing page and call deploy_site."
                ),
            })

        return result_json

    return ToolDefinition(
        name="generate_image",
        description=(
            "Generate an AI image from a text description using Replicate (flux-schnell). "
            "Use this to create product photos, ad creatives, logos, hero images, etc. "
            "Returns the URL of the generated image. "
            "Cost: 1 credit per image generated."
        ),
        parameters=GENERATE_IMAGE_SCHEMA,
        execute=execute,
    )
