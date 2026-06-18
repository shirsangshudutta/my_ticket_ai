"""
doc_chain.py
Uses LLM + retrieved CIS patterns from Cosmos DB to generate content
for every section of the uploaded LLD template.
Strictly grounded — no hallucination.
"""

import os, json, re
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from cosmos_store import search, format_context

# ══════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are a senior Azure Integration Architect at a retail company.
You are producing a formal Low Level Design (LLD) Interface Architecture Document.

━━━ STRICT GROUNDING RULES ━━━
1. Use ONLY the CIS patterns in the CONTEXT section. Do NOT invent services or flows.
2. Every section must be populated using ONLY information actually present in the retrieved
   CIS patterns. If the retrieved patterns contain no relevant information for a given section,
   the value MUST be exactly the string "N/A" (no other text, no placeholders, no apologies).
   Do not guess, do not generalise from outside knowledge.
3. Return a SINGLE valid JSON object:
   - Keys   = exact section titles from TEMPLATE SECTIONS
   - Values = full content string (use \\n for line breaks, \\n- for bullets)
4. Nothing outside the JSON. No preamble, no markdown fences.

━━━ SECTION INSTRUCTIONS ━━━
Change History / Document Distribution → version table placeholders
Overview / Business Requirements → professional narrative from integration details
Technology Used → only Azure services confirmed in retrieved pattern
In-Scope / Out of Scope → what this interface covers and does not cover
Assumptions / Dependencies → standard integration assumptions
Architectural Pattern (3.3) → name pattern exactly as in context
Context Diagram (3.6) → PlantUML @startuml...@enduml block
Sequence Diagram (3.7) → PlantUML sequence @startuml...@enduml block
Overall Flow (5.1) → numbered step-by-step message flow
AKS Details → microservice role, replicas, resource limits
Service Bus config → namespace tier, topic name, TTL, subscription names
Function App → trigger type, input/output bindings, retry policy
Data Model (7) → SourceField | TargetField | Transformation rows
Logging / Error Handling → retry policy, dead-letter, alerting
Monitoring (10.1) → Azure Monitor metrics, alert thresholds
Security (10.2) → managed identity, RBAC, network policies
Glossary (13) → define: CIS, AKS, LLD, Service Bus, Event Hub

━━━ CONTEXT — Retrieved CIS Patterns ━━━
{context}
"""

USER_PROMPT = """Generate the complete LLD document for:

  Source System      : {source}
  Target System(s)   : {targets}
  Delivery Mode      : {delivery}
  Frequency          : {frequency}
  Volume             : {volume}
  Delivery Guarantee : {guarantee}
  Multiple Consumers : {multi_consumer}
  Interface ID       : {interface_id}
  Business Context   : {business_context}

TEMPLATE SECTIONS (ALL must be JSON keys):
{sections}

Return ONLY the JSON object."""


def _parse_json_response(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Find first { and extract balanced JSON
        start_idx = cleaned.find("{")
        if start_idx == -1:
            raise ValueError(f"No JSON object found in response:\n{raw[:500]}")
        
        brace_count = 0
        for i in range(start_idx, len(cleaned)):
            if cleaned[i] == "{":
                brace_count += 1
            elif cleaned[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_str = cleaned[start_idx:i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON found: {e}\n{json_str[:300]}")
        
        raise ValueError(f"Unbalanced braces in response:\n{raw[:500]}")


def generate_document_content(
    source: str,
    targets: list,
    delivery: str,
    frequency: str,
    volume: str,
    guarantee: bool,
    multi_consumer: bool,
    template_sections: list[dict],
    business_context: str = "",
    interface_id: str = "",
    **kwargs,                        # absorbs vectorstore_path etc.
) -> dict:
    """
    Main entry point — returns {section_title: ai_generated_content}.
    """
    from datetime import datetime
    if not interface_id:
        interface_id = (
            f"INT-{source.replace(' ','')[:3].upper()}-"
            f"{'-'.join(t[:3].upper() for t in targets[:2])}-"
            f"{datetime.now().strftime('%Y%m%d')}-001"
        )

    # Retrieve from Cosmos DB
    query   = f"Source: {source}. Targets: {', '.join(targets)}. Delivery: {delivery}. Frequency: {frequency}."
    results = search(query, k=3)
    context = format_context(results)

    sections_str = "\n".join(
        f"{'  ' * (s['level']-1)}{s['title']}" for s in template_sections
    )

    client = OpenAI(
        base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )

    system_filled = SYSTEM_PROMPT.format(context=context)
    user_filled   = USER_PROMPT.format(
        source=source,
        targets=", ".join(targets),
        delivery=delivery,
        frequency=frequency,
        volume=volume,
        guarantee="Yes" if guarantee else "No",
        multi_consumer="Yes" if multi_consumer else "No",
        interface_id=interface_id,
        business_context=business_context or f"{source} → {', '.join(targets)}",
        sections=sections_str,
    )

    response = client.chat.completions.create(
        model=os.environ.get("AZURE_CHAT_DEPLOYMENT", "gpt-4o-1"),
        messages=[
            {"role": "system", "content": system_filled},
            {"role": "user",   "content": user_filled},
        ],
        temperature=0,
        max_tokens=4000,
    )
    raw = response.choices[0].message.content

    return _parse_json_response(raw)