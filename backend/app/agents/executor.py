from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

import structlog

from app.agents.base import AgentResult, TokenStats
from app.agents.mission_catalog import MISSION_CATALOG
from app.agents.registry import get_agent
from app.agents.tools import ToolDefinition, get_tool_registry, get_company_tool_registry
from app.core.config import get_settings
from app.models.entities import AgentType

logger = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent / "prompts"
SKILLS_DIR = Path(__file__).parent / "skills"

MAX_TOOL_ITERATIONS = 5
MAX_COMPLEXITY = 5

COMPLEXITY_ROUTING: dict[int, tuple[str, str]] = {
    1: ("openai", "gpt-4o-mini"),
    2: ("openai", "gpt-4o-mini"),
    3: ("openai", "gpt-4o"),
    4: ("anthropic", "claude-sonnet-4-20250514"),
    5: ("anthropic", "claude-sonnet-4-20250514"),
}

DEFAULT_MODEL = ("openai", "gpt-4o")


def _resolve_model(mission_type: str) -> tuple[str, str]:
    """Route to the cheapest model capable of handling the mission complexity.

    Priority: catalog override > complexity routing > default.
    """
    catalog = MISSION_CATALOG.get(mission_type)
    if not catalog:
        return DEFAULT_MODEL

    if catalog.preferred_provider and catalog.preferred_model:
        return catalog.preferred_provider, catalog.preferred_model

    return COMPLEXITY_ROUTING.get(catalog.complexity, DEFAULT_MODEL)


def _load_system_prompt(agent_type: AgentType) -> str:
    path = PROMPTS_DIR / f"{agent_type.value}_system.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return f"Tu es l'agent {agent_type.value}. Produis uniquement le livrable final."


def _parse_skill_header(raw: str) -> tuple[str, str]:
    """Extract YAML frontmatter version from a skill file.

    Returns (content_without_header, version_string).
    Expected format:
        ---
        version: 2
        created: 2026-06-04
        ---
        <actual skill content>
    """
    if not raw.startswith("---"):
        return raw, "0"

    end_idx = raw.find("---", 3)
    if end_idx == -1:
        return raw, "0"

    header = raw[3:end_idx].strip()
    content = raw[end_idx + 3:].strip()

    version = "0"
    for line in header.splitlines():
        if line.strip().startswith("version:"):
            version = line.split(":", 1)[1].strip()
            break

    return content, version


def _load_skill(mission_type: str, business_type: str) -> str:
    """Load skill instructions: specific to business_type first, then generic."""
    content, _ = _load_skill_versioned(mission_type, business_type)
    return content


def _load_skill_versioned(
    mission_type: str,
    business_type: str,
    use_expert: bool = False,
) -> tuple[str, str]:
    """Load skill and return (content, version).

    When use_expert=True, look for {mission_type}_expert.md first (purchased
    via the skill shop). Falls back to the standard skill if no expert file.
    """
    if use_expert:
        expert_path = SKILLS_DIR / f"{mission_type}_expert.md"
        if expert_path.exists():
            raw = expert_path.read_text(encoding="utf-8").strip()
            content, version = _parse_skill_header(raw)
            # Still layer the business-type overlay on top of the expert skill
            overlay = SKILLS_DIR / f"{mission_type}_{business_type.lower()}.md"
            if overlay.exists():
                overlay_raw = overlay.read_text(encoding="utf-8").strip()
                overlay_content, _ = _parse_skill_header(overlay_raw)
                content = f"{content}\n\n{overlay_content}"
            logger.info(
                "expert_skill_loaded",
                mission_type=mission_type,
                skill_version=version,
            )
            return content, version

    specific = SKILLS_DIR / f"{mission_type}_{business_type.lower()}.md"
    if specific.exists():
        base = SKILLS_DIR / f"{mission_type}.md"
        base_raw = base.read_text(encoding="utf-8").strip() if base.exists() else ""
        specific_raw = specific.read_text(encoding="utf-8").strip()

        base_content, _ = _parse_skill_header(base_raw) if base_raw else ("", "0")
        specific_content, version = _parse_skill_header(specific_raw)

        if base_content:
            return f"{base_content}\n\n{specific_content}", version
        return specific_content, version

    generic = SKILLS_DIR / f"{mission_type}.md"
    if generic.exists():
        raw = generic.read_text(encoding="utf-8").strip()
        content, version = _parse_skill_header(raw)
        if mission_type == "landing_page_revision":
            base = SKILLS_DIR / "landing_page.md"
            if base.exists():
                base_raw = base.read_text(encoding="utf-8").strip()
                base_content, _ = _parse_skill_header(base_raw)
                content = f"{base_content}\n\n{content}"
        return content, version

    return "", "0"


async def _company_has_expert_skill(company_id: str, mission_type: str) -> bool:
    """Check if a company owns an expert skill for the given mission type."""
    if not company_id:
        return False
    try:
        from app.core.database import SessionLocal
        from app.models.entities import CompanySkill, SkillShopItem
        from sqlalchemy import select

        async with SessionLocal() as session:
            result = await session.execute(
                select(CompanySkill.id)
                .join(SkillShopItem)
                .where(
                    CompanySkill.company_id == company_id,
                    SkillShopItem.mission_type == mission_type,
                    SkillShopItem.tier == "expert",
                )
                .limit(1)
            )
            has_skill = result.scalar_one_or_none() is not None

            if has_skill:
                from sqlalchemy import update
                await session.execute(
                    update(CompanySkill)
                    .where(
                        CompanySkill.company_id == company_id,
                        CompanySkill.skill_item_id.in_(
                            select(SkillShopItem.id).where(
                                SkillShopItem.mission_type == mission_type
                            )
                        ),
                    )
                    .values(times_used=CompanySkill.times_used + 1)
                )
                await session.commit()

            return has_skill
    except Exception as exc:
        logger.warning("expert_skill_check_failed", error=str(exc))
        return False


def _load_skill_version(mission_type: str, version: str) -> str:
    """Load a specific archived version of a skill (for debug/rollback)."""
    path = SKILLS_DIR / f"{mission_type}.v{version}.md"
    if path.exists():
        content, _ = _parse_skill_header(path.read_text(encoding="utf-8").strip())
        return content
    return ""


def _build_user_prompt(
    mission_type: str,
    company_name: str,
    mission_statement: str,
    product_description: str = "",
    target_audience: str = "",
    business_type: str = "ecommerce",
    output_format: str = "markdown",
    chain_context: list[dict] | None = None,
    memory_context: list[dict] | None = None,
    competitor_url: str = "",
    website_profile: str = "",
    website_brief: str = "",
    website_strategy: str = "",
    product_image_url: str = "",
    existing_site_html: str = "",
    revision_request: str = "",
) -> str:
    parts = [
        f'Company: "{company_name}"',
        f"Type de business: {business_type}",
        f"Mission: {mission_statement}" if mission_statement else "",
        f"Produit: {product_description}" if product_description else "",
        f"Audience cible: {target_audience}" if target_audience else "",
        f"URL concurrent a analyser: {competitor_url}" if competitor_url else "",
    ]

    if website_profile:
        parts.append(
            "\n--- COMPANY PROFILE WEBSITE (SOURCE PRINCIPALE) ---\n"
            f"{website_profile}\n"
            "--- FIN COMPANY PROFILE ---\n"
            "Utilise ce company profile comme source principale pour le positionnement, "
            "le hero, le copy, les objections, les preuves et le ton. "
            "Ne le remplace pas par un template générique."
        )

    if website_brief:
        parts.append(f"\n--- BRIEF CREATIF WEBSITE ---\n{website_brief}\n--- FIN BRIEF ---")

    if website_strategy:
        parts.append(
            "\n--- SITE SPEC / WEBSITE STRATEGY (OBLIGATOIRE) ---\n"
            f"{website_strategy}\n"
            "--- FIN SITE SPEC ---\n"
            "Tu dois utiliser ce SITE SPEC comme source principale pour la direction artistique, "
            "la structure, les CTA, les trust signals et le style visuel."
        )

    if existing_site_html:
        parts.append(
            "\n--- SITE EXISTANT A REVISER ---\n"
            f"{existing_site_html[:12000]}\n"
            "--- FIN SITE EXISTANT ---"
        )

    if revision_request:
        parts.append(
            "\n--- DEMANDE UTILISATEUR POUR LA REVISION ---\n"
            f"{revision_request}\n"
            "--- FIN DEMANDE ---\n"
            "Applique cette demande précisément. Garde le produit, l'offre et les CTA cohérents."
        )

    if product_image_url:
        parts.append(
            f"\n--- IMAGE PRODUIT PRÉ-GÉNÉRÉE ---\n"
            f"URL: {product_image_url}\n"
            f"OBLIGATOIRE: intègre cette URL directement dans le HTML via <img src=\"{product_image_url}\" alt=\"{company_name}\">.\n"
            "Place-la dans la section hero ET dans la section produit. Ne génère PAS d'autre image produit.\n"
            "--- FIN IMAGE PRODUIT ---"
        )

    if memory_context:
        parts.append("\n--- MEMOIRE DE L'ENTREPRISE ---")
        for mem in memory_context:
            parts.append(
                f"[{mem['category'].upper()}] {mem['key']} :\n{mem['content']}"
            )
        parts.append("--- FIN MEMOIRE ---\n")
        parts.append(
            "Utilise la memoire de l'entreprise ci-dessus comme contexte principal. "
            "Ton livrable doit etre coherent avec ces donnees."
        )
    elif chain_context:
        parts.append("\n--- CONTEXTE DES ETAPES PRECEDENTES ---")
        for ctx in chain_context:
            parts.append(
                f"\n### Etape {ctx['step_number']} : {ctx['title']} ({ctx['mission_type']})\n"
                f"{ctx['deliverable'][:2000]}"
            )
        parts.append("\n--- FIN DU CONTEXTE ---\n")
        parts.append(
            "Utilise le contexte des etapes precedentes pour rendre ton livrable "
            "coherent avec ce qui a deja ete produit."
        )

    parts.extend([
        "\n--- CONTRAINTE DE COHERENCE OBLIGATOIRE ---",
        "Tu dois travailler exclusivement sur l'idee, le produit, l'audience et le type de business fournis ci-dessus.",
        "Ne change jamais le produit, le secteur, le probleme utilisateur ou le business model.",
        "Si le contexte est court ou ambigu, enrichis-le prudemment sans inventer une nouvelle idee.",
        "Tous les exemples, concurrents, features, prix, canaux et recommandations doivent rester coherents avec ce contexte.",
        "--- FIN CONTRAINTE ---\n",
        f"Tache: {mission_type}",
        f"Format attendu: {output_format}",
        "Produis uniquement le livrable final, sans preambule ni explication.",
    ])
    return "\n".join(p for p in parts if p)


def _resolve_tools(
    mission_type: str,
    settings,
    company_id: str = "",
    company_slug: str = "default",
) -> list[ToolDefinition]:
    """Return the list of tools available for this mission, respecting the feature flag."""
    if not settings.tools_enabled:
        return []
    if company_id:
        registry = get_company_tool_registry(company_id, company_slug)
    else:
        registry = get_tool_registry()
    return registry.get_tools_for_mission(mission_type)


async def execute_agent(
    agent_type: AgentType,
    mission_type: str,
    company_name: str,
    mission_statement: str,
    product_description: str = "",
    target_audience: str = "",
    log_callback: Optional[Callable[[str, str], object]] = None,
    chain_context: list[dict] | None = None,
    business_type: str = "ecommerce",
    memory_context: list[dict] | None = None,
    quality_feedback: str | None = None,
    company_id: str = "",
    company_slug: str = "default",
    competitor_url: str = "",
    website_profile: str = "",
    website_brief: str = "",
    website_strategy: str = "",
    product_image_url: str = "",
    existing_site_html: str = "",
    revision_request: str = "",
) -> AgentResult:
    settings = get_settings()
    catalog = MISSION_CATALOG.get(mission_type)
    output_format = catalog.output_format if catalog else "markdown"

    if catalog and catalog.complexity > MAX_COMPLEXITY:
        raise ValueError(
            f"Mission {mission_type} complexity ({catalog.complexity}) exceeds max ({MAX_COMPLEXITY}). "
            "Split into smaller sub-tasks."
        )

    tool_iterations = catalog.max_tool_iterations if catalog else MAX_TOOL_ITERATIONS

    system_prompt = _load_system_prompt(agent_type)

    use_expert = await _company_has_expert_skill(company_id, mission_type)
    skill_content, skill_version = _load_skill_versioned(
        mission_type, business_type, use_expert=use_expert,
    )
    if skill_content:
        skill_label = "SKILL EXPERT" if use_expert else "SKILL"
        system_prompt = f"{system_prompt}\n\n--- {skill_label} ---\n{skill_content}\n--- FIN {skill_label} ---"
        logger.info(
            "skill_loaded",
            mission_type=mission_type,
            skill_version=skill_version,
            expert=use_expert,
        )

    user_prompt = _build_user_prompt(
        mission_type, company_name, mission_statement,
        product_description, target_audience, business_type, output_format,
        chain_context=chain_context,
        memory_context=memory_context,
        competitor_url=competitor_url,
        website_profile=website_profile,
        website_brief=website_brief,
        website_strategy=website_strategy,
        product_image_url=product_image_url,
        existing_site_html=existing_site_html,
        revision_request=revision_request,
    )

    if quality_feedback:
        user_prompt += f"\n\n{quality_feedback}"

    if log_callback:
        await log_callback("context", f"Analyse du contexte de {company_name}...")

    if settings.agent_mode == "mock":
        agent = get_agent(agent_type)
        if log_callback:
            await log_callback("mock_run", "Mode mock actif — livrable template")
        return await agent.run(mission_type, company_name, mission_statement)

    tools = _resolve_tools(mission_type, settings, company_id, company_slug)

    resolved_registry = None
    if tools:
        resolved_registry = get_company_tool_registry(company_id, company_slug) if company_id else get_tool_registry()
        resolved_registry.set_mission_context(mission_id=company_id, company_id=company_id)

    resolved_provider, resolved_model = _resolve_model(mission_type)
    if settings.agent_mode in ("openai", "anthropic"):
        resolved_provider = settings.agent_mode
        resolved_model = (
            settings.anthropic_model if settings.agent_mode == "anthropic"
            else settings.openai_model
        )

    logger.info(
        "model_routing",
        mission_type=mission_type,
        provider=resolved_provider,
        model=resolved_model,
        complexity=catalog.complexity if catalog else 3,
    )

    providers = _ordered_providers(resolved_provider)

    provider_errors: list[str] = []

    for provider in providers:
        try:
            model = resolved_model if provider == resolved_provider else (
                settings.anthropic_model if provider == "anthropic" else settings.openai_model
            )
            if log_callback:
                tools_info = f" + {len(tools)} tools" if tools else ""
                await log_callback("agent_call", f"Appel {provider} ({model}{tools_info})...")

            result = await _call_provider(
                provider, system_prompt, user_prompt, output_format,
                settings, tools, log_callback, tool_iterations, model,
                tool_registry=resolved_registry,
            )

            if log_callback:
                word_count = len(result.content.split())
                tc_info = f", {len(result.tool_calls)} tool calls" if result.tool_calls else ""
                await log_callback("deliverable_ready", f"Livrable pret — {word_count} mots{tc_info}")

            return result

        except Exception as exc:
            provider_errors.append(f"{provider}: {str(exc)[:240]}")
            logger.warning("provider_failed", provider=provider, error=str(exc))
            if log_callback:
                await log_callback("fallback", f"{provider} echoue, tentative suivante...")
            continue

    if settings.app_env != "development":
        detail = "; ".join(provider_errors) if provider_errors else "no_provider_configured"
        if log_callback:
            await log_callback("provider_failed", f"Aucun provider IA disponible : {detail[:300]}")
        raise RuntimeError(f"ai_provider_unavailable: {detail}")

    logger.info("all_providers_failed_falling_back_to_mock", mission_type=mission_type)
    if log_callback:
        await log_callback("mock_fallback", "Fallback sur livrable template")
    agent = get_agent(agent_type)
    return await agent.run(mission_type, company_name, mission_statement)


def _ordered_providers(preferred: str) -> list[str]:
    settings = get_settings()
    available = []
    if settings.anthropic_api_key:
        available.append("anthropic")
    if settings.openai_api_key:
        available.append("openai")

    if not available:
        return []

    if preferred in available:
        available.remove(preferred)
        return [preferred] + available
    return available


async def _call_provider(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    output_format: str,
    settings,
    tools: list[ToolDefinition] | None = None,
    log_callback: Optional[Callable] = None,
    max_iterations: int = MAX_TOOL_ITERATIONS,
    model: str = "",
    tool_registry=None,
) -> AgentResult:
    if provider == "anthropic":
        return await _call_anthropic(
            system_prompt, user_prompt, output_format, settings, tools, log_callback,
            max_iterations, model=model or settings.anthropic_model,
            tool_registry=tool_registry,
        )
    return await _call_openai(
        system_prompt, user_prompt, output_format, settings, tools, log_callback,
        max_iterations, model=model or settings.openai_model,
        tool_registry=tool_registry,
    )


# ---------------------------------------------------------------------------
# Anthropic with tool-use loop
# ---------------------------------------------------------------------------

async def _call_anthropic(
    system_prompt: str,
    user_prompt: str,
    output_format: str,
    settings,
    tools: list[ToolDefinition] | None = None,
    log_callback: Optional[Callable] = None,
    max_iterations: int = MAX_TOOL_ITERATIONS,
    model: str = "",
    tool_registry=None,
) -> AgentResult:
    from app.agents.llm_client import call_anthropic_raw, COMPLEX_TIMEOUT_S

    use_model = model or settings.anthropic_model
    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    tool_calls_log: list[dict] = []
    all_token_stats: list[TokenStats] = []

    api_tools = [t.to_anthropic_schema() for t in tools] if tools else []
    registry = tool_registry if (tool_registry and tools) else (get_tool_registry() if tools else None)

    is_html_mission = output_format == "html"

    async def force_final_synthesis(current_response=None) -> tuple[str, int]:
        synth_messages = list(messages)
        if current_response is not None and getattr(current_response, "content", None):
            synth_messages.append({"role": "assistant", "content": current_response.content})
        synth_messages.append({
            "role": "user",
            "content": (
                f"Redige maintenant le livrable final complet au format {output_format}. "
                "Utilise les resultats d'outils deja fournis dans cette conversation. "
                "N'appelle plus aucun outil. Ne renvoie pas de preambule."
            ),
        })
        synth_response, synth_latency = await call_anthropic_raw(
            system_prompt, synth_messages, max_tokens=16384 if is_html_mission else 4096,
            tools=None, timeout_s=COMPLEX_TIMEOUT_S,
        )
        synth_text_parts = [b.text for b in synth_response.content if hasattr(b, "text")]
        synth_usage = synth_response.usage
        all_token_stats.append(TokenStats(
            provider="anthropic",
            model=use_model,
            input_tokens=synth_usage.input_tokens,
            output_tokens=synth_usage.output_tokens,
            total_tokens=synth_usage.input_tokens + synth_usage.output_tokens,
        ))
        return "\n".join(synth_text_parts).strip(), synth_latency

    for iteration in range(max_iterations + 1):
        _max_tok = 16384 if is_html_mission else 4096
        response, latency = await call_anthropic_raw(
            system_prompt, messages, max_tokens=_max_tok,
            tools=api_tools or None, timeout_s=COMPLEX_TIMEOUT_S,
        )

        usage = response.usage
        all_token_stats.append(TokenStats(
            provider="anthropic",
            model=use_model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + usage.output_tokens,
        ))

        if response.stop_reason != "tool_use" or not registry:
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            content = "\n".join(text_parts).strip()
            if not content and tool_calls_log:
                logger.info("empty_tool_synthesis_forcing_final_answer", provider="anthropic")
                content, latency = await force_final_synthesis(current_response=response)
            return AgentResult(
                format=output_format,
                content=content,
                metadata={"provider": "anthropic", "model": use_model, "latency_ms": latency},
                tool_calls=tool_calls_log,
                token_stats=all_token_stats,
            )

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            if log_callback:
                await log_callback("tool_call", f"Outil: {block.name}({json.dumps(block.input, ensure_ascii=False)[:80]})")

            result_str = await registry.execute_tool(block.name, block.input)
            tool_calls_log.append({
                "tool": block.name,
                "args": block.input,
                "result": result_str[:500],
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_str,
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    # Tool loop exhausted — last response still has tool_use blocks.
    # Force one final call without tools to get the synthesis.
    text_parts = [b.text for b in response.content if hasattr(b, "text")]
    if not text_parts:
        logger.info("tool_loop_exhausted_forcing_synthesis", provider="anthropic")
        content, _ = await force_final_synthesis()
    else:
        content = "\n".join(text_parts).strip()
    return AgentResult(
        format=output_format,
        content=content,
        metadata={"provider": "anthropic", "model": use_model},
        tool_calls=tool_calls_log,
        token_stats=all_token_stats,
    )


# ---------------------------------------------------------------------------
# OpenAI with tool-use loop
# ---------------------------------------------------------------------------

async def _call_openai(
    system_prompt: str,
    user_prompt: str,
    output_format: str,
    settings,
    tools: list[ToolDefinition] | None = None,
    log_callback: Optional[Callable] = None,
    max_iterations: int = MAX_TOOL_ITERATIONS,
    model: str = "",
    tool_registry=None,
) -> AgentResult:
    from app.agents.llm_client import call_openai_raw, COMPLEX_TIMEOUT_S

    use_model = model or settings.openai_model
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tool_calls_log: list[dict] = []
    all_token_stats: list[TokenStats] = []

    api_tools = [t.to_openai_schema() for t in tools] if tools else None
    registry = tool_registry if (tool_registry and tools) else (get_tool_registry() if tools else None)

    for iteration in range(max_iterations + 1):
        response, latency = await call_openai_raw(
            system_prompt, user_prompt,
            messages=messages, max_tokens=4096,
            tools=api_tools, timeout_s=COMPLEX_TIMEOUT_S,
        )
        choice = response.choices[0]

        if response.usage:
            all_token_stats.append(TokenStats(
                provider="openai",
                model=use_model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ))

        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls or not registry:
            content = choice.message.content or ""
            return AgentResult(
                format=output_format,
                content=content,
                metadata={"provider": "openai", "model": use_model, "latency_ms": latency},
                tool_calls=tool_calls_log,
                token_stats=all_token_stats,
            )

        assistant_msg = {
            "role": "assistant",
            "content": choice.message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ],
        }
        messages.append(assistant_msg)

        for tc in choice.message.tool_calls:
            args = json.loads(tc.function.arguments)

            if log_callback:
                await log_callback("tool_call", f"Outil: {tc.function.name}({json.dumps(args, ensure_ascii=False)[:80]})")

            result_str = await registry.execute_tool(tc.function.name, args)
            tool_calls_log.append({
                "tool": tc.function.name,
                "args": args,
                "result": result_str[:500],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    # Tool loop exhausted — last response had tool_calls, force final synthesis.
    content = choice.message.content or ""
    if not content and tool_calls_log:
        logger.info("tool_loop_exhausted_forcing_synthesis", provider="openai")
        synth_response, _ = await call_openai_raw(
            system_prompt, user_prompt,
            messages=messages, max_tokens=4096,
            tools=None, timeout_s=COMPLEX_TIMEOUT_S,
        )
        content = synth_response.choices[0].message.content or ""
        if synth_response.usage:
            all_token_stats.append(TokenStats(
                provider="openai",
                model=use_model,
                input_tokens=synth_response.usage.prompt_tokens,
                output_tokens=synth_response.usage.completion_tokens,
                total_tokens=synth_response.usage.total_tokens,
            ))
    return AgentResult(
        format=output_format,
        content=content,
        metadata={"provider": "openai", "model": use_model},
        tool_calls=tool_calls_log,
        token_stats=all_token_stats,
    )
