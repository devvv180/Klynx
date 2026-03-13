"""
Generate top 3 emerging risk narratives for client.
Sends filtered events + client profile to LLM to produce intelligence narratives.
Stores output in data/client_risk_narratives.json

Usage: python generate_risk_narratives.py
"""

import json
import os
import time

import requests

# ── Config ──────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"
RATE_LIMIT   = 4          # seconds between calls
BASE_DIR     = os.path.dirname(__file__)


def call_groq(prompt: str, temperature: float = 0.2, max_tokens: int = 4096) -> str:
    """Call Groq chat completions via requests."""
    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_client_brief(profile: dict) -> str:
    ov = profile["companyOverview"]
    return f"""CLIENT BRIEF — Meridian Lifesciences
Industry: {ov['primaryIndustry']} / {ov['secondaryIndustry']}
Regions: {', '.join(ov['selectedRegions'])}

Operations:
• Manufacturing: 2 FDA-approved plants in India (Hyderabad, Vizag). 100 % of production.
• Sourcing: Critical APIs from China (single-region, 12-month qualification for alternates).
• Revenue: US 40 %, Europe 18 %, India domestic rest.
• Product: Generic medicines.

Top Vulnerabilities:
1. FDA regulatory dependency — 400 crore revenue at risk if approval restricted.
2. China API sourcing concentration — single supplier region, 7-8 week lead time.
3. Only 2 plants, no backup capacity. Vizag coastal flood risk.
4. High FX exposure (66 % export), working capital squeeze.
5. Recent FDA observations pending clearance.
6. EU traceability & environmental compliance costs rising.
7. Logistics: shipping routes through sensitive areas, 20 % freight cost increase."""


def summarise_events(events: list[dict]) -> str:
    """Create a compact summary of all events for the LLM."""
    lines = []
    for i, ev in enumerate(events, 1):
        headline = ev.get("headline", "")[:120]
        summary  = ev.get("summary", "")[:200]
        pillar   = ev.get("predicted_structural_driver", "")
        domain   = ev.get("predicted_structural_domain", "")
        geos     = ", ".join(ev.get("geo_tags", [])[:4])
        lines.append(
            f"[{i}] {headline}\n"
            f"    Pillar: {pillar} | Domain: {domain}\n"
            f"    Geo: {geos}\n"
            f"    Summary: {summary}…"
        )
    return "\n".join(lines)


# ── STEP 1: Per-event relevance triage ──────────────────────────────────

def triage_events(events: list[dict], client_brief: str) -> list[dict]:
    """
    Send events in batches to LLM.
    Ask: which events are DIRECTLY relevant to Meridian and why?
    Returns events with added 'triage' field.
    """
    BATCH = 15  # events per call
    triaged = []

    for start in range(0, len(events), BATCH):
        batch = events[start : start + BATCH]
        batch_nums = list(range(start + 1, start + len(batch) + 1))

        batch_text = "\n\n".join(
            f"[{n}] {ev.get('headline','')[:120]}\n"
            f"    Summary: {ev.get('summary','')[:250]}\n"
            f"    Pillar: {ev.get('predicted_structural_driver','')}\n"
            f"    Geo: {', '.join(ev.get('geo_tags',[])[:4])}"
            for n, ev in zip(batch_nums, batch)
        )

        prompt = f"""{client_brief}

Below are {len(batch)} news events (numbered {batch_nums[0]}-{batch_nums[-1]}).

{batch_text}

TASK: For EACH event, decide if it is DIRECTLY relevant to Meridian Lifesciences.
An event is relevant ONLY if it could materially affect:
- Their FDA approvals or regulatory standing
- Their China API sourcing or India manufacturing
- Their US/Europe revenue or market access
- Their supply chain, logistics, or freight costs
- Their competitive position in generic pharma
- Pharma industry regulations, drug pricing, or trade policy affecting them

Return JSON array. For each event include:
[
  {{"n": <event number>, "relevant": true/false, "reason": "1 sentence why"}}
]

Be STRICT. A pharma news article about a different therapy area with no connection to generics, India, China, FDA, or supply chains is NOT relevant."""

        print(f"  Triaging events {batch_nums[0]}-{batch_nums[-1]}...")
        raw = call_groq(prompt, temperature=0.1, max_tokens=2048)

        # parse JSON from response
        try:
            text = raw
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            # Try to find JSON array in response
            text = text.strip()
            if not text.startswith("["):
                # Find first [ in text
                idx = text.find("[")
                if idx >= 0:
                    text = text[idx:]
                    # Find matching ]
                    end = text.rfind("]")
                    if end >= 0:
                        text = text[:end+1]
            verdicts = json.loads(text)
        except Exception as e:
            print(f"    ⚠ Parse error: {e}")
            print(f"    Raw response (first 300 chars): {raw[:300]}")
            verdicts = [{"n": n, "relevant": False, "reason": "parse error"} for n in batch_nums]

        verdict_map = {v["n"]: v for v in verdicts}

        for n, ev in zip(batch_nums, batch):
            v = verdict_map.get(n, {"relevant": False, "reason": "missing"})
            ev["triage"] = {
                "relevant": v.get("relevant", False),
                "reason": v.get("reason", ""),
            }
            if v.get("relevant"):
                triaged.append(ev)

        time.sleep(RATE_LIMIT)

    return triaged


# ── STEP 2: Generate top-3 risk narratives ──────────────────────────────

def generate_narratives(relevant_events: list[dict], client_brief: str) -> dict:
    """
    Send all relevant events to LLM and ask for top 3 emerging risk narratives.
    """
    event_summaries = summarise_events(relevant_events)

    prompt = f"""{client_brief}

RELEVANT EVENTS ({len(relevant_events)} events that directly affect Meridian):

{event_summaries}

TASK: Based on these events AND the client's vulnerability profile, produce the TOP 3 EMERGING RISKS for Meridian Lifesciences.

For each risk, write a short intelligence narrative (3-5 sentences) that:
1. Names the risk clearly (e.g. "China API Sourcing Disruption")
2. Cites specific events from the list above as evidence
3. Explains the transmission mechanism — HOW it hits Meridian's operations, revenue, or compliance
4. Quantifies impact where possible (revenue at risk, lead-time increase, etc.)
5. Suggests a watch-list action

Return ONLY valid JSON:
{{
  "generated_at": "<current date>",
  "client": "Meridian Lifesciences",
  "top_3_risks": [
    {{
      "rank": 1,
      "risk_title": "...",
      "risk_level": "Critical/High/Medium",
      "narrative": "3-5 sentence intelligence narrative...",
      "evidence_events": [list of event numbers cited],
      "impact_areas": ["Supply Chain", "Revenue", "Regulatory", etc.],
      "estimated_impact": "brief quantification",
      "recommended_action": "1 sentence"
    }},
    ...
  ]
}}"""

    print("\n  Generating top 3 risk narratives...")
    raw = call_groq(prompt, temperature=0.25, max_tokens=4096)

    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        result = json.loads(raw)
    except Exception as e:
        print(f"  ⚠ Could not parse narrative JSON: {e}")
        result = {"error": str(e), "raw_response": raw}

    return result


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("GENERATING RISK NARRATIVES FOR MERIDIAN LIFESCIENCES")
    print("=" * 80)

    # Load data
    profile = load_json(os.path.join(BASE_DIR, "data", "client_data.json"))
    events  = load_jsonl(os.path.join(BASE_DIR, "data", "llm_filtered_relevant_events.jsonl"))
    client_brief = build_client_brief(profile)

    print(f"\nLoaded {len(events)} pre-filtered events")
    print(f"Client: {profile['companyOverview']['primaryIndustry']}\n")

    # Step 1: Triage — which of the 66 events truly matter?
    print("STEP 1: Triaging events for direct client relevance...")
    relevant = triage_events(events, client_brief)
    print(f"\n  → {len(relevant)} events passed triage (from {len(events)})\n")

    if not relevant:
        print("No relevant events found. Check triage logic.")
        return

    # Step 2: Generate narratives from relevant events
    print("STEP 2: Generating top 3 risk narratives...")
    time.sleep(RATE_LIMIT)
    narratives = generate_narratives(relevant, client_brief)

    # Save triaged events
    triaged_path = os.path.join(BASE_DIR, "data", "triaged_client_events.json")
    with open(triaged_path, "w", encoding="utf-8") as f:
        json.dump(relevant, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved {len(relevant)} triaged events → {triaged_path}")

    # Save narratives
    narratives_path = os.path.join(BASE_DIR, "data", "client_risk_narratives.json")
    with open(narratives_path, "w", encoding="utf-8") as f:
        json.dump(narratives, f, indent=2, ensure_ascii=False)
    print(f"  Saved narratives → {narratives_path}")

    # Print results
    print("\n" + "=" * 80)
    print("TOP 3 EMERGING RISKS FOR MERIDIAN")
    print("=" * 80)

    risks = narratives.get("top_3_risks", [])
    for risk in risks:
        print(f"\n{'─' * 60}")
        print(f"#{risk.get('rank','')} {risk.get('risk_title','')} [{risk.get('risk_level','')}]")
        print(f"{'─' * 60}")
        print(f"{risk.get('narrative','')}")
        print(f"\nImpact: {risk.get('estimated_impact','')}")
        print(f"Action: {risk.get('recommended_action','')}")

    print("\n" + "=" * 80)
    print("Done!")


if __name__ == "__main__":
    main()
