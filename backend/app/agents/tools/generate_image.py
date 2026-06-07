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


def create_generate_image_tool(api_token: str) -> ToolDefinition:
    async def execute(prompt: str, width: int = 1024, height: int = 1024) -> str:
        return await _execute_generate_image(api_token, prompt, width, height)

    return ToolDefinition(
        name="generate_image",
        description=(
            "Generate an AI image from a text description using Replicate (flux-schnell). "
            "Use this to create product photos, ad creatives, logos, hero images, etc. "
            "Returns the URL of the generated image."
        ),
        parameters=GENERATE_IMAGE_SCHEMA,
        execute=execute,
    )
