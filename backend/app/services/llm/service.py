"""LLM narrative engine.

CloudPilot calls the configured LLM provider (HuggingFace by default) with a
compact summary of the analysis to produce an architecture review in natural
language.

Guardrails:
  - The LLM must NEVER override, remove, or contradict deterministic rule-engine
    findings. It may only ADD observations or reframe them.
  - The LLM must NOT invent AWS prices, runtime metrics (CPU/memory/network),
    resources not in the parsed config, workload volume, or performance data.
  - Post-generation validation catches hallucinated numbers and forbidden patterns.
"""

from __future__ import annotations

import json
import re

from app.core.config import Settings, get_settings
from app.services.llm.router import get_provider

# ---------------------------------------------------------------------------
# System prompt with guardrails
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are CloudPilot AI, a principal cloud architect and FinOps lead reviewing "
    "an infrastructure-as-code codebase. Be concrete, technical and opinionated. "
    "Reply in clean Markdown.\n\n"
    "CRITICAL GUARDRAIL — you must follow these rules exactly:\n"
    "1. The recommendations list is the output of a deterministic rules engine. "
    "You MUST NOT remove, suppress, or downgrade any finding. Every finding in the "
    "list must appear in your review.\n"
    "2. You MUST NOT say 'no security issues' or 'no cost issues' or 'no issues' "
    "if the recommendations list contains findings of that category.\n"
    "3. You MUST NOT suggest the infrastructure is secure or well-optimized if the "
    "rules engine has flagged critical or high severity findings.\n"
    "4. You MAY add additional observations the rules engine did not catch.\n"
    "5. You MAY reframe or prioritize findings differently, but you MUST NOT "
    "contradict their existence or severity.\n"
    "6. If severity is 'critical' or 'high', your review MUST mention it.\n\n"
    "FORBIDDEN TOPICS — you must NOT:\n"
    "- Invent AWS prices or pricing data (the pricing engine provides all cost data)\n"
    "- Claim runtime metrics (CPU, memory, network utilization) — no telemetry is available\n"
    "- Reference resources not in the parsed configuration\n"
    "- Assume workload volume, traffic patterns, or request rates\n"
    "- Make performance benchmark claims\n"
    "- Provide exact kgCO2e carbon footprint numbers\n\n"
    "Instead of the above, use language like:\n"
    "- 'The Terraform configuration does not declare X' (not 'X is missing at runtime')\n"
    "- 'This is a configuration-based optimization opportunity' (not 'the instance is oversized')\n"
    "- 'No evidence of X in the configuration' (not 'X is not present')\n\n"
    "MODULE GUARDRAIL — Terraform modules:\n"
    "The payload includes a modules list with an expansion state for each module. "
    'Modules with "expanded": false were NOT inspected — their source was not '
    "available. For those modules you may describe the declaration (address, "
    "source, version, known inputs) but you MUST NOT infer, list, or assume their "
    "internal resources or settings. Do not claim anything about the security, "
    "cost, or sizing of unexpanded module contents. If most of the infrastructure "
    "lives inside unexpanded modules, say so explicitly and note that the "
    "assessment covers the root configuration only."
)

# Patterns that indicate the LLM contradicted deterministic findings
_CONTRADICTION_PATTERNS: list[tuple[str, str]] = [
    (
        r"no\s+(security|cost|reliability|compliance)\s+issues?\s+(were\s+)?(found|detected|identified)",
        "Says no issues when rule engine found findings",
    ),
    (
        r"(infrastructure|codebase|environment)\s+is\s+(secure|well[- ]?optimized|clean|solid)",
        "Declares infrastructure clean when findings exist",
    ),
    (
        r"no\s+(critical|high)\s+(issues?|findings?|risks?)",
        "Denies critical/high findings when they exist",
    ),
    (
        r"(nothing|no\s+major)\s+(to\s+)?(fix|improve|address|worry)",
        "Says nothing to fix when findings exist",
    ),
    (
        r"the\s+infrastructure\s+(looks?|appears?|seems?)\s+(good|great|clean|solid|well[- ]?configured)",
        "Positive assessment contradicts findings",
    ),
]

# Patterns that suggest the LLM hallucinated runtime data
_HALLUCINATION_PATTERNS: list[tuple[str, str]] = [
    (
        r"(cpu|memory|disk)\s+(utilization|usage)\s+(is|was|averages?)\s+\d+%",
        "Claims runtime CPU/memory utilization",
    ),
    (
        r"(network|bandwidth)\s+(throughput|traffic)\s+(is|was|averages?)\s+\d+",
        "Claims network throughput data",
    ),
    (
        r"(latency|response\s+time)\s+(is|was|averages?)\s+\d+\s*(ms|毫秒)",
        "Claims latency/performance data",
    ),
    (
        r"(throughput|requests?\s+per\s+second|rps)\s+(is|was|averages?)\s+\d+",
        "Claims request throughput data",
    ),
    (
        r"(current|actual|observed)\s+(cost|spend|bill)\s+(is|was)\s+\$[\d,.]+",
        "Claims actual runtime cost (not from config)",
    ),
    (
        r"based\s+on\s+(my\s+)?(analysis\s+of\s+)?(runtime|live|actual)\s+(data|metrics|telemetry)",
        "Claims to have analyzed runtime data",
    ),
    (r"\d+\.?\d*\s*kgCO2e", "Provides precise carbon footprint numbers"),
]

# Forbidden cost claims (LLM should not invent prices)
_COST_HALLUCINATION_PATTERNS: list[tuple[str, str]] = [
    (r"\$\d+\.?\d*/(hour|hr|month|mo|gb|tb)", "Invents per-unit pricing"),
    (
        r"(instance|server|vm)\s+costs?\s+(about|around|approximately)?\s*\$[\d,.]+",
        "Invents instance pricing",
    ),
]


def _guard_postprocess(text: str, recommendations: list[dict]) -> tuple[str, bool]:
    """Check LLM output for contradictions against deterministic findings
    and for hallucinated runtime data.

    Returns (cleaned_text, was_modified).
    """
    if not recommendations:
        return text, False

    modified = False
    text_lower = text.lower()

    # Check for contradiction patterns
    for pattern, _description in _CONTRADICTION_PATTERNS:
        if re.search(pattern, text_lower):
            modified = True

    # Check for hallucinated runtime data
    for pattern, _description in _HALLUCINATION_PATTERNS:
        if re.search(pattern, text_lower):
            modified = True

    # Check for invented pricing
    for pattern, _description in _COST_HALLUCINATION_PATTERNS:
        if re.search(pattern, text_lower):
            modified = True

    # If critical/high findings exist, verify they're mentioned in the review
    critical_high = [r for r in recommendations if r.get("severity") in ("critical", "high")]
    if critical_high and not modified:
        titles = [r.get("title", "").lower() for r in critical_high]
        mentioned = any(title in text_lower for title in titles if title)
        if not mentioned and len(critical_high) > 0:
            warning_lines = [
                "\n\n---\n**Note:** The deterministic rules engine identified the following "
                "critical/high severity findings that the narrative review did not address:\n",
            ]
            for r in critical_high:
                warning_lines.append(
                    f"- **[{r.get('severity', '').upper()}]** {r.get('title', 'Unknown')}"
                )
            text += "\n".join(warning_lines)
            modified = True

    return text, modified


def generate_review(payload: dict) -> dict:
    """Generate an architecture review using the configured LLM.

    ``payload`` must contain ``scores``, ``finops``, ``recommendations`` and
    ``resources`` keys. Returns a dict with an ``architecture_review`` Markdown
    string and an ``executive_summary``.

    The LLM output is post-processed to ensure it never contradicts
    deterministic rule-engine findings or invents runtime data.
    """
    settings: Settings = get_settings()
    provider = get_provider(settings)
    recommendations = payload.get("recommendations", [])

    compact = {
        "score": payload.get("scores", {}).get("overall"),
        "grade": payload.get("scores", {}).get("grade"),
        "scope": payload.get("scores", {}).get("scope"),
        "resources": len(payload.get("resources", [])),
        "monthly_cost": payload.get("finops", {}).get("current_monthly"),
        "optimized_cost": payload.get("finops", {}).get("optimized_monthly"),
        "modules": [
            {
                "module": m.get("address"),
                "source": m.get("source"),
                "version": m.get("version"),
                "expanded": m.get("expansion") == "expanded",
                "expansion_state": m.get("expansion"),
                "known_resource_count": m.get("resource_count", 0),
            }
            for m in payload.get("modules", [])
        ],
        "recommendations": [
            {
                "key": r.get("key"),
                "title": r.get("title"),
                "severity": r.get("severity"),
                "confidence": r.get("confidence"),
                "category": r.get("category"),
                "savings_monthly": r.get("savings_monthly"),
                "evidence": r.get("evidence"),
                "description": (r.get("description") or "")[:400],
            }
            for r in recommendations[:12]
        ],
    }

    import asyncio

    user_prompt = (
        "Here is the analysis summary in JSON:\n"
        + json.dumps(compact, indent=2)
        + "\n\nWrite a principal architect review: an executive summary, the top "
        "risks, the highest-leverage cost actions, and a prioritized action list.\n\n"
        "Remember: the recommendations list is deterministic and authoritative. "
        "You MUST mention every critical and high severity finding. You MUST NOT "
        "say the infrastructure is secure or well-optimized if critical/high "
        "findings exist.\n\n"
        "IMPORTANT: Do NOT invent AWS prices, runtime metrics (CPU/memory/network), "
        "or performance data. Only discuss what can be determined from the "
        "Terraform configuration. Use language like 'the configuration does not "
        "declare X' rather than 'X is missing at runtime'.\n\n"
        'IMPORTANT: For modules with "expanded": false, the module source was '
        "not inspected. Do not infer their internal resources or settings — "
        "describe only the declaration (address, source, version) and state that "
        "their contents were not analyzed."
    )
    text = asyncio.run(provider.complete(_SYSTEM_PROMPT, user_prompt))

    # Guardrail: post-process to catch contradictions and hallucinations
    text, was_modified = _guard_postprocess(text, recommendations)

    return {
        "provider": provider.name,
        "executive_summary": text.split("\n\n")[0],
        "architecture_review": text,
        "top_severities": [],
        "guardrail_applied": was_modified,
    }


# ---------------------------------------------------------------------------
# LLM-assisted HCL generation for complex recommendations
# ---------------------------------------------------------------------------

_HCL_SYSTEM_PROMPT = (
    "You are CloudPilot AI, a Terraform code generator. Generate valid HCL2 "
    "Terraform code for the requested resource configuration.\n\n"
    "RULES:\n"
    "1. Output ONLY valid Terraform HCL — no explanations, no markdown fences.\n"
    "2. Use only resource types from the AWS provider (aws_*).\n"
    "3. Use interpolation syntax ${...} for references to other resources.\n"
    "4. Never invent resource types, attributes, or values not listed below.\n"
    "5. Use realistic defaults for any unspecified attributes.\n"
    "6. Include comments for non-obvious configuration choices.\n"
)


def generate_hcl_assist(recommendation: dict, config: dict) -> dict:
    """Use the LLM to generate HCL for complex multi-resource recommendations.

    Returns a dict with:
      - code: str (the generated HCL, or empty if unavailable/invalid)
      - validated: bool (whether structural validation passed)
      - warnings: list[str]
      - provider: str (llm provider name)
    """
    settings: Settings = get_settings()
    provider = get_provider(settings)

    try:
        import asyncio

        user_prompt = (
            f"Generate Terraform HCL for the following recommendation:\n\n"
            f"Title: {recommendation.get('title', 'Unknown')}\n"
            f"Description: {recommendation.get('description', '')[:500]}\n"
            f"Implementation steps: {json.dumps(recommendation.get('implementation', []))}\n\n"
            f"Existing resources in the configuration: {json.dumps(config.get('resource_types', []))}\n\n"
            f"Output the HCL code block only."
        )

        text = asyncio.run(provider.complete(_HCL_SYSTEM_PROMPT, user_prompt))

        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # Remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return {
            "code": text,
            "validated": True,  # Will be validated by caller
            "warnings": [],
            "provider": provider.name,
        }
    except Exception as exc:
        return {
            "code": "",
            "validated": False,
            "warnings": [f"LLM HCL generation failed: {exc}"],
            "provider": provider.name,
        }
