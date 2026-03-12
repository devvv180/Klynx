"""
=============================================================
DRA Risk Matching Engine  v2.0
=============================================================
Reads:   merged_lexis_event_frames_similarity_v1.jsonl
Outputs: risk_match_report.json
         risk_match_report.md

Modes:
  1. Rule-based  (no API key needed)  — python risk_matching_engine.py
  2. LLM-enhanced (Groq key needed)  — python risk_matching_engine.py --groq-key YOUR_KEY
  3. Custom transcript               — python risk_matching_engine.py --transcript client.txt
=============================================================
"""

import argparse
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

# ─────────────────────────────────────────
# CONFIG  (override via env or CLI flags)
# ─────────────────────────────────────────
# Get base directory (where this script is located)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

LEXIS_FILE  = os.getenv("LEXIS_FILE",  os.path.join(DATA_DIR, "merged_lexis_event_frames_similarity_v1.jsonl"))
OUTPUT_JSON = os.getenv("OUTPUT_JSON", os.path.join(BASE_DIR, "..", "..", "risk_match_report.json"))
OUTPUT_MD   = os.getenv("OUTPUT_MD",   os.path.join(BASE_DIR, "..", "..", "risk_match_report.md"))

GROQ_URL    = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL  = "llama-3.3-70b-versatile"

TOP_N_DRIVERS   = 5
TOP_N_EVENTS    = 3
MIN_MATCH_SCORE = 0.40  # Lowered from 0.45 to get more results

# ─────────────────────────────────────────
# NOISE FILTER - Remove false positives
# ─────────────────────────────────────────
NOISE_HEADLINE_KEYWORDS = [
    "opening ceremony", "investor opportunity", "fraud investigation",
    "announces", "appoints", "names", "hires", "promotes",
    "press release", "business wire", "pr newswire",
    "quarterly results", "earnings call", "investor relations"
]

NOISE_EFFECT_KEYWORDS = [
    "inauguration", "office opening", "press release",
    "announcement", "appointment", "hiring"
]

# ─────────────────────────────────────────
# SECTOR → EXPECTED RISK DRIVER MAP
# ─────────────────────────────────────────
SECTOR_DRIVER_MAP = {
    "pharma":         ["Geopolitical & Sovereign", "Regulatory & Policy Regime",
                       "Technological & Digital",  "Macroeconomic & Financial System"],
    "pharmaceutical": ["Geopolitical & Sovereign", "Regulatory & Policy Regime",
                       "Technological & Digital",  "Macroeconomic & Financial System"],
    "manufacturing":  ["Geopolitical & Sovereign", "Infrastructure & Critical Systems",
                       "Macroeconomic & Financial System"],
    "technology":     ["Technological & Digital",  "Regulatory & Policy Regime",
                       "Geopolitical & Sovereign"],
    "fintech":        ["Regulatory & Policy Regime","Technological & Digital",
                       "Macroeconomic & Financial System"],
    "banking":        ["Macroeconomic & Financial System","Regulatory & Policy Regime",
                       "Geopolitical & Sovereign"],
    "energy":         ["Geopolitical & Sovereign", "Environmental & Climate",
                       "Regulatory & Policy Regime"],
    "logistics":      ["Geopolitical & Sovereign", "Infrastructure & Critical Systems",
                       "Macroeconomic & Financial System"],
    "shipping":       ["Geopolitical & Sovereign", "Infrastructure & Critical Systems",
                       "Macroeconomic & Financial System"],
    "healthcare":     ["Regulatory & Policy Regime","Societal & Human Capital",
                       "Technological & Digital"],
    "retail":         ["Macroeconomic & Financial System","Societal & Human Capital",
                       "Technological & Digital"],
    "agriculture":    ["Environmental & Climate",  "Geopolitical & Sovereign",
                       "Macroeconomic & Financial System"],
    "telecom":        ["Technological & Digital",  "Regulatory & Policy Regime",
                       "Geopolitical & Sovereign"],
    "aerospace":      ["Geopolitical & Sovereign", "Technological & Digital",
                       "Regulatory & Policy Regime"],
}

# ─────────────────────────────────────────
# GEO KEYWORDS  (what the extractor scans for)
# ─────────────────────────────────────────
GEO_KEYWORDS = [
    "india", "china", "united states", "usa", "us", "europe", "eu",
    "middle east", "iran", "russia", "ukraine", "taiwan", "north korea",
    "south korea", "pakistan", "saudi arabia", "uae", "gulf",
    "guangdong", "shandong", "hyderabad", "vizag", "mumbai",
    "strait of hormuz", "south china sea", "mediterranean",
    "japan", "germany", "france", "uk", "brazil", "indonesia",
]

# ─────────────────────────────────────────
# RISK SIGNAL KEYWORDS  (for keyword match)
# ─────────────────────────────────────────
RISK_KEYWORDS = [
    "warning letter", "ransomware", "cyber", "supply chain", "concentration risk",
    "api shortage", "freight cost", "freight", "oil price", "inflation", "forex",
    "data localization", "sanctions", "nuclear", "war", "conflict",
    "talent retention", "regulatory", "compliance", "fda", "data breach",
    "disruption", "shortage", "delay", "cost increase", "interest rate",
    "working capital", "attrition", "inspection", "audit", "flooding", "cyclone",
    "climate", "carbon", "emission", "traceability", "serialization",
]

# ─────────────────────────────────────────
# VELOCITY CLASSIFICATION
# ─────────────────────────────────────────
FAST_SIGNALS   = ["war","attack","invasion","strike","bomb","casualt","oil price",
                  "market crash","sanctions","nuclear","blockade","ransomware",
                  "breach","explosion","flood","earthquake","emergency","urgent"]
MEDIUM_SIGNALS = ["regulation","compliance","policy","tariff","trade restriction",
                  "supply chain","shortage","inflation","interest rate","freight",
                  "legislation","court ruling","fda","warning","inspection"]
SLOW_SIGNALS   = ["five-year plan","long-term","structural","demographic",
                  "climate change","workforce","talent","r&d","research",
                  "infrastructure investment","strategic"]

def classify_velocity(text: str) -> str:
    t = text.lower()
    f = sum(1 for k in FAST_SIGNALS   if k in t)
    m = sum(1 for k in MEDIUM_SIGNALS if k in t)
    s = sum(1 for k in SLOW_SIGNALS   if k in t)
    if f >= m and f >= s:   return "FAST   (hours–days)"
    elif m >= s:             return "MEDIUM (weeks–months)"
    else:                    return "SLOW   (months–quarters)"

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())

def load_jsonl(path: str) -> list:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows

# ─────────────────────────────────────────
# NOISE FILTER — Remove false positives
# ─────────────────────────────────────────
def is_noise_event(event: dict) -> bool:
    """
    Filter out press releases, office openings, corporate announcements.
    Returns True if event should be EXCLUDED.
    """
    headline = (event.get("headline") or "").lower()
    
    # Check headline for noise keywords
    for keyword in NOISE_HEADLINE_KEYWORDS:
        if keyword in headline:
            return True
    
    # Check effects for noise keywords
    for frame in event.get("event_frame", []):
        canonical = frame.get("Canonical", {})
        effect = (canonical.get("Effect") or "").lower()
        for keyword in NOISE_EFFECT_KEYWORDS:
            if keyword in effect:
                return True
    
    return False

# ─────────────────────────────────────────
# STEP 1 — LOAD EVENTS
# ─────────────────────────────────────────
def load_events(path: str) -> list:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Events file not found: {path}")
    events = load_jsonl(path)
    print(f"[LOAD] {len(events)} events loaded from {path}")
    
    # Filter out noise events
    filtered_events = [e for e in events if not is_noise_event(e)]
    filtered_count = len(events) - len(filtered_events)
    print(f"[FILTER] Removed {filtered_count} noise events (press releases, office openings, etc.)")
    print(f"[FILTER] {len(filtered_events)} events remaining for analysis")
    
    return filtered_events

# ─────────────────────────────────────────
# STEP 2a — PROFILE EXTRACTION  (rule-based)
# No API key needed. Scans transcript for
# geo mentions, sector keywords, risk phrases.
# ─────────────────────────────────────────
def extract_profile_rules(transcript: str) -> dict:
    t = transcript.lower()
    geos    = [g for g in GEO_KEYWORDS  if g in t]
    sectors = [s for s in SECTOR_DRIVER_MAP.keys() if s in t]
    risks   = [r for r in RISK_KEYWORDS if r in t]

    # Simple heuristic splits
    sourcing_geos = [g for g in geos if g in [
        "china","guangdong","shandong","india","vietnam","bangladesh","indonesia"]]
    sales_geos    = [g for g in geos if g in [
        "united states","usa","us","europe","eu","uk","germany","france","japan"]]
    ops_geos      = [g for g in geos if g not in sourcing_geos and g not in sales_geos]

    return {
        "company_name":              "Client Organisation",
        "sector":                    sectors[0] if sectors else "general",
        "sub_sector":                sectors[1] if len(sectors) > 1 else "",
        "geographies_operations":    ops_geos[:4],
        "geographies_sourcing":      sourcing_geos[:4],
        "geographies_sales":         sales_geos[:4],
        "supply_chain_dependencies": [r for r in risks if any(
            k in r for k in ["supply","freight","shortage","api","oil","delay"])],
        "regulatory_bodies":         [r for r in risks if any(
            k in r for k in ["fda","regulatory","compliance","sanctions","warning"])],
        "technology_stack":          [r for r in risks if any(
            k in r for k in ["cyber","ransomware","data","breach","traceability"])],
        "known_risks":               risks[:8],
        "blind_spots":               [],
        "key_concerns":              risks[:3],
        "_extraction_mode":          "rule-based",
    }

# ─────────────────────────────────────────
# STEP 2b — PROFILE EXTRACTION  (LLM)
# Better quality; needs a Groq API key.
# ─────────────────────────────────────────
PROFILE_PROMPT = """You are a risk intelligence analyst.

Extract a structured client business profile from the transcript below.

Return STRICT JSON only — no markdown, no explanation:
{{
  "company_name": "string",
  "sector": "string (one of: pharma, manufacturing, banking, technology, energy, logistics, healthcare, retail, agriculture, telecom, aerospace, other)",
  "sub_sector": "string",
  "geographies_operations": ["countries or cities where they operate"],
  "geographies_sourcing":   ["countries or regions they source raw materials from"],
  "geographies_sales":      ["countries or regions they sell into"],
  "supply_chain_dependencies": ["specific materials, routes, suppliers, logistics nodes mentioned"],
  "regulatory_bodies":     ["regulators, standards, or compliance bodies mentioned"],
  "technology_stack":      ["systems, cloud providers, software, vendors mentioned"],
  "known_risks":           ["risks explicitly named by the client"],
  "blind_spots":           ["risks the client admits they have not fully assessed"],
  "key_concerns":          ["the top concerns expressed in the client's own words"]
}}

Transcript:
{transcript}
"""

def extract_profile_llm(transcript: str, groq_key: str) -> dict:
    try:
        import requests
    except ImportError:
        print("[WARN] requests not installed. Falling back to rule-based extraction.")
        return {}

    prompt = PROFILE_PROMPT.format(transcript=transcript[:6000])
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":           GROQ_MODEL,
        "messages":        [{"role": "user", "content": prompt}],
        "temperature":     0.0,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            print(f"[LLM ERROR] status={resp.status_code}  {resp.text[:200]}")
            return {}
        content = resp.json()["choices"][0]["message"]["content"]
        profile = json.loads(content)
        profile["_extraction_mode"] = "llm"
        return profile
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return {}

# ─────────────────────────────────────────
# STEP 3 — SCORING
# Three sub-scores combined into one:
#   geo_overlap      weight 0.35
#   sector_relevance weight 0.40
#   signal_strength  weight 0.25
# ─────────────────────────────────────────
def _geo_overlap(profile: dict, event: dict) -> float:
    client_geos = set()
    for field in ("geographies_sourcing", "geographies_operations",
                  "geographies_sales",    "supply_chain_dependencies"):
        for item in profile.get(field, []):
            client_geos.add(normalize(item))

    event_geos = set()
    for tag in event.get("geo_tags", []):
        event_geos.add(normalize(tag))
    for loc in event.get("geo_locations", []):
        if loc.get("name"):    event_geos.add(normalize(loc["name"]))
        if loc.get("country"): event_geos.add(normalize(loc["country"]))

    if not client_geos or not event_geos:
        return 0.0
    return min(1.0, len(client_geos & event_geos) / 3.0)


def _sector_relevance(profile: dict, event: dict) -> float:
    sector = normalize(profile.get("sector", ""))
    relevant_drivers = []
    for key, drivers in SECTOR_DRIVER_MAP.items():
        if key in sector:
            relevant_drivers.extend(drivers)

    driver_match = 1.0 if event.get("predicted_structural_driver") in relevant_drivers else 0.2

    # Build client keyword set from all known-risk / concern fields
    client_kws = set()
    for field in ("known_risks", "supply_chain_dependencies",
                  "key_concerns", "technology_stack", "regulatory_bodies"):
        for item in profile.get(field, []):
            for word in normalize(item).split():
                if len(word) > 3:
                    client_kws.add(word)

    event_text = normalize(
        (event.get("headline") or "")  + " " +
        (event.get("summary")  or "")  + " " +
        " ".join(
            (c.get("Effect") or "") + " " + (c.get("Escalation_Signals") or "")
            for frame in event.get("event_frame", [])
            for c in [frame.get("Canonical", {})]
        )
    )

    hits = sum(1 for kw in client_kws if kw in event_text)
    keyword_score = min(1.0, hits / 5.0)

    return (driver_match * 0.6) + (keyword_score * 0.4)


def score_event(profile: dict, event: dict) -> float:
    geo    = _geo_overlap(profile, event)
    sector = _sector_relevance(profile, event)
    signal = float(event.get("predicted_structural_similarity") or 0.5)
    return round((geo * 0.35) + (sector * 0.40) + (signal * 0.25), 6)

# ─────────────────────────────────────────
# STEP 4 — MATCH & RANK
# ─────────────────────────────────────────
def match_risks(profile: dict, events: list,
                top_n_drivers: int = TOP_N_DRIVERS,
                top_n_events:  int = TOP_N_EVENTS) -> list:

    scored = []
    for ev in events:
        s = score_event(profile, ev)
        if s >= MIN_MATCH_SCORE:
            scored.append({**ev, "_match_score": s})

    # GROUP BY SPECIFIC EVENT TYPE (predicted_structural_domain) instead of vague driver
    by_event_type = defaultdict(list)
    for ev in scored:
        event_type = ev.get("predicted_structural_domain") or "Unknown Risk Event"
        by_event_type[event_type].append(ev)

    summaries = []
    for event_type, evs in by_event_type.items():
        evs_sorted = sorted(evs, key=lambda x: x["_match_score"], reverse=True)
        top_evs    = evs_sorted[:top_n_events]
        agg_score  = sum(e["_match_score"] for e in evs) / len(evs)

        # Collect text for velocity classification
        vel_text = " ".join(
            (c.get("Effect") or "") + " " + (c.get("Escalation_Signals") or "")
            for ev in top_evs
            for frame in ev.get("event_frame", [])
            for c in [frame.get("Canonical", {})]
        ) + " " + " ".join(ev.get("headline", "") for ev in top_evs)

        velocity = classify_velocity(vel_text)

        event_list = []
        for ev in top_evs:
            canonicals = [f.get("Canonical", {}) for f in ev.get("event_frame", [])]
            event_list.append({
                "event_id":      ev.get("event_id"),
                "headline":      ev.get("headline"),
                "domain":        ev.get("predicted_structural_domain"),
                "match_score":   ev["_match_score"],
                "signal_score":  ev.get("predicted_structural_similarity"),
                "published":     ev.get("published_utc"),
                "geo_tags":      ev.get("geo_tags", [])[:5],
                "effects":       [c.get("Effect", "")        for c in canonicals if c.get("Effect")],
                "escalations":   [c.get("Escalation_Signals","") for c in canonicals
                                  if c.get("Escalation_Signals","").lower() not in ("","none")],
                "actors":        [c.get("Actor", "")         for c in canonicals if c.get("Actor")],
                "snippet":       (ev.get("summary") or "")[:200],
            })

        summaries.append({
            "event_type":      event_type,  # Changed from "driver"
            "aggregate_score": round(agg_score, 4),
            "event_count":     len(evs),
            "velocity":        velocity,
            "top_events":      event_list,
        })

    summaries.sort(key=lambda x: x["aggregate_score"], reverse=True)
    return summaries[:top_n_drivers]

# ─────────────────────────────────────────
# STEP 5 — IMPACT PATHWAYS
# ─────────────────────────────────────────
PATHWAY_PROMPT = """You are a senior risk advisor writing a concise brief for a CEO/Board audience.

Given the client profile and a specific risk event type with triggering events, write:

IMPACT PATHWAY:
[What is happening globally] → [How it reaches the client's operations] → [Specific business impact]

WATCH INDICATORS (2–3 bullets):
Early warning signs the client should monitor.

Rules: Under 100 words total. Be specific to this client, not generic.

Client: {sector} company | Operations: {ops} | Sourcing: {sourcing} | Sales: {sales}
Key dependencies: {deps}

Risk Event Type: {event_type}  |  Velocity: {velocity}
Top triggering events:
{events_text}
"""

def generate_pathway_llm(result: dict, profile: dict, groq_key: str) -> str:
    try:
        import requests
    except ImportError:
        return generate_pathway_rules(result, profile)

    events_text = "\n".join(
        f"- {ev['headline']} | Effect: {ev['effects'][0] if ev['effects'] else 'n/a'}"
        f" | Escalation: {ev['escalations'][0] if ev['escalations'] else 'n/a'}"
        for ev in result["top_events"]
    )
    prompt = PATHWAY_PROMPT.format(
        sector   = profile.get("sector", "n/a"),
        ops      = ", ".join(profile.get("geographies_operations", [])[:3]) or "n/a",
        sourcing = ", ".join(profile.get("geographies_sourcing",   [])[:3]) or "n/a",
        sales    = ", ".join(profile.get("geographies_sales",      [])[:3]) or "n/a",
        deps     = ", ".join(profile.get("supply_chain_dependencies", [])[:3]) or "n/a",
        event_type = result["event_type"],  # Changed from "driver"
        velocity = result["velocity"],
        events_text = events_text,
    )
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload = {"model": GROQ_MODEL, "messages": [{"role":"user","content":prompt}], "temperature": 0.2}
    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[PATHWAY LLM ERROR] {e}")
    return generate_pathway_rules(result, profile)


def generate_pathway_rules(result: dict, profile: dict) -> str:
    top       = result["top_events"]
    headline  = top[0]["headline"]      if top              else "External risk event"
    effect    = top[0]["effects"][0]    if top and top[0]["effects"]    else "operational disruption"
    escalation= top[0]["escalations"][0]if top and top[0]["escalations"]else "escalating signals"
    geos      = ", ".join(top[0]["geo_tags"][:2]) if top else "affected region"
    sector    = profile.get("sector", "your sector")
    sales     = ", ".join(profile.get("geographies_sales", [])[:2]) or "key markets"
    sourcing  = ", ".join(profile.get("geographies_sourcing", [])[:2]) or "supply regions"
    return (
        f"IMPACT PATHWAY:\n"
        f"{headline} [{geos}] → "
        f"Disruption to {sector} operations via {sourcing} sourcing exposure → "
        f"{effect}, impacting revenue in {sales}.\n\n"
        f"WATCH INDICATORS:\n"
        f"• Escalation signals: {escalation}\n"
        f"• Freight / logistics index changes for {geos}\n"
        f"• Supplier communication from {sourcing} re: allocation or pricing"
    )

# ─────────────────────────────────────────
# STEP 6 — BUILD REPORTS
# ─────────────────────────────────────────
def build_json_report(profile: dict, results: list, pathways: dict) -> dict:
    return {
        "report_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "client":       profile.get("company_name", "Client"),
            "sector":       profile.get("sector"),
            "extraction":   profile.get("_extraction_mode", "unknown"),
            "data_source":  LEXIS_FILE,
        },
        "client_profile": profile,
        "top_risks": [
            {
                "rank":            i + 1,
                "event_type":      r["event_type"],  # Changed from "driver"
                "aggregate_score": r["aggregate_score"],
                "event_count":     r["event_count"],
                "velocity":        r["velocity"],
                "impact_pathway":  pathways.get(r["event_type"], ""),  # Changed from "driver"
                "top_events":      r["top_events"],
            }
            for i, r in enumerate(results)
        ],
    }


def build_md_report(profile: dict, results: list, pathways: dict) -> str:
    lines = []
    lines += [
        "# Dynamic Risk Assessment Report",
        f"**Client:**    {profile.get('company_name','Client')}",
        f"**Sector:**    {profile.get('sector','N/A')}",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Source:**    {LEXIS_FILE}",
        "",
        "---",
        "",
        "## Client Risk Exposure Profile",
        "",
        "| Dimension | Detail |",
        "|---|---|",
        f"| Sector | {profile.get('sector','')} — {profile.get('sub_sector','')} |",
        f"| Operations | {', '.join(profile.get('geographies_operations',[]))} |",
        f"| Sourcing | {', '.join(profile.get('geographies_sourcing',[]))} |",
        f"| Sales Markets | {', '.join(profile.get('geographies_sales',[]))} |",
        f"| Key Dependencies | {', '.join(profile.get('supply_chain_dependencies',[])[:4])} |",
        f"| Regulatory Bodies | {', '.join(profile.get('regulatory_bodies',[])[:4])} |",
        f"| Known Risks | {', '.join(profile.get('known_risks',[])[:5])} |",
        f"| Blind Spots | {', '.join(profile.get('blind_spots',[])[:3])} |",
        "",
        "---",
        "",
        "## Top Risks Identified",
        "",
    ]

    for i, r in enumerate(results):
        lines += [
            f"### Risk {i+1} — {r['event_type']}",  # Changed from "driver"
            f"**Score:** `{r['aggregate_score']}`  |  "
            f"**Velocity:** `{r['velocity']}`  |  "
            f"**Matching Events in Dataset:** {r['event_count']}",
            "",
        ]
        pathway = pathways.get(r["event_type"], "")  # Changed from "driver"
        if pathway:
            lines += [pathway, ""]

        lines.append("**Top Triggering Events from LexisNexis Dataset:**")
        lines.append("")
        for ev in r["top_events"]:
            lines.append(f"- **{ev['headline']}**")
            lines.append(f"  - Domain: `{ev['domain']}`  |  Match Score: `{ev['match_score']:.3f}`")
            if ev["effects"]:
                lines.append(f"  - Effect: {ev['effects'][0]}")
            if ev["escalations"]:
                lines.append(f"  - Escalation Signal: {ev['escalations'][0]}")
            if ev["geo_tags"]:
                lines.append(f"  - Geographies: {', '.join(ev['geo_tags'][:4])}")
        lines += ["", "---", ""]

    return "\n".join(lines)

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="DRA Risk Matching Engine v2.0")
    parser.add_argument("--transcript",  default=None,  help="Path to .txt transcript file")
    parser.add_argument("--groq-key",    default=None,  help="Groq API key (optional — enables LLM mode)")
    parser.add_argument("--lexis-file",  default=LEXIS_FILE)
    parser.add_argument("--top-drivers", default=TOP_N_DRIVERS, type=int)
    parser.add_argument("--top-events",  default=TOP_N_EVENTS,  type=int)
    args = parser.parse_args()

    groq_key = args.groq_key or os.getenv("GROQ_API_KEY")

    # 1. Load events
    events = load_events(args.lexis_file)

    # 2. Load transcript
    if args.transcript and os.path.exists(args.transcript):
        with open(args.transcript, "r", encoding="utf-8") as f:
            transcript = f.read()
        print(f"[TRANSCRIPT] Loaded: {args.transcript} ({len(transcript)} chars)")
    else:
        print("[TRANSCRIPT] Using built-in sample transcript")
        transcript = SAMPLE_TRANSCRIPT

    # 3. Extract profile
    profile = {}
    if groq_key:
        print("[PROFILE] Extracting via LLM (Groq)...")
        profile = extract_profile_llm(transcript, groq_key)
    if not profile:
        print("[PROFILE] Using rule-based extraction...")
        profile = extract_profile_rules(transcript)
    print(f"[PROFILE] Sector={profile.get('sector')}  "
          f"Ops={profile.get('geographies_operations')}  "
          f"Mode={profile.get('_extraction_mode')}")

    # 4. Match
    print("[MATCH] Scoring events...")
    results = match_risks(profile, events, args.top_drivers, args.top_events)

    # 5. Pathways
    print("[PATHWAY] Generating impact pathways...")
    pathways = {}
    for r in results:
        if groq_key:
            pathways[r["event_type"]] = generate_pathway_llm(r, profile, groq_key)  # Changed from "driver"
        else:
            pathways[r["event_type"]] = generate_pathway_rules(r, profile)  # Changed from "driver"

    # 6. Save reports
    json_report = build_json_report(profile, results, pathways)
    md_report   = build_md_report(profile, results, pathways)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md_report)

    print(f"\n[DONE]  {OUTPUT_JSON}")
    print(f"[DONE]  {OUTPUT_MD}")
    print("\n" + "="*60)
    print("RISK SUMMARY")
    print("="*60)
    for r in results:
        print(f"  #{results.index(r)+1}  {r['event_type']:<42} "  # Changed from "driver"
              f"score={r['aggregate_score']:.4f}  {r['velocity']}")
    print("="*60)


# ─────────────────────────────────────────
# SAMPLE TRANSCRIPT  (natural, no geo jargon)
# ─────────────────────────────────────────
SAMPLE_TRANSCRIPT = """
Client: Rajiv Nair, CFO — Meridian Lifesciences Pvt. Ltd.
Date: March 12, 2026

Interviewer: Walk me through the business.

Rajiv: We make generic medicines — tablets, capsules, injectables — and two-thirds of 
revenue comes from exports. The US is 40% of total revenue. Europe is another 18%. 
Two manufacturing plants in Andhra Pradesh — Hyderabad and Vizag, both US regulator approved.

Interviewer: How is the business performing?

Rajiv: Margins are getting squeezed. Raw material costs are up — we import most of our 
key ingredients from China, suppliers we have worked with for years. The relationship is 
fine but lead times have gotten unpredictable. Something has shifted in how they prioritise 
their order books. We suspect domestic pressure on their end but cannot confirm it.

Freight has been the other big hit — logistics costs up over 20%. Our freight forwarder 
is giving us longer transit times and higher quotes. We used to plan 4 to 5 weeks from 
China to our warehouse. Now we quote 7 to 8 weeks internally just to be safe.

Interviewer: Do you know what is driving the freight disruption?

Rajiv: Not precisely. Certain shipping routes have become more expensive or are being 
avoided by some carriers. We have just been absorbing the cost and adjusting safety stock 
upward. That created a working capital problem — we are holding more inventory than before. 
US buyers are also taking longer to pay. We are getting squeezed on both sides.

Interviewer: How is the regulatory situation?

Rajiv: Our single biggest operational anxiety. We had an inspection at Vizag about 
14 months ago — documentation and data management observations. We have addressed the 
findings but until we get formal clearance there is always a risk of action that could 
restrict US shipments. That is roughly 400 crore of revenue at risk. Compliance team 
is on high alert.

Europe has introduced new rules around medicine traceability and environmental standards. 
Our contract manufacturing clients are passing those requirements down to us. In India, 
pricing controls on a few domestic categories hit our margins in the last revision.

Interviewer: Technology infrastructure?

Rajiv: We are mid-transformation, which is a vulnerable position. SAP on cloud for the 
ERP. But the manufacturing floor systems at Vizag are old — software the vendor no longer 
supports. We have had a couple of security incidents in the last two years, nothing serious 
but a wake-up call.

The bigger worry is the US traceability requirement. Every product shipped to America must 
be tracked end-to-end through the supply chain. That requires our systems to connect with 
our distributors systems. Every integration point is a potential vulnerability — a problem 
there is not just a technology issue, it becomes a regulatory one simultaneously.

We are piloting an AI-based quality detection tool using hardware from an Asian vendor. 
Chosen on cost and performance grounds but there are internal conversations about whether 
to revisit that given the broader technology environment.

Interviewer: People and talent?

Rajiv: R&D attrition has been painful — three senior scientists left this year, two to 
multinationals. The compensation gap is widening. We recently lost a regulatory affairs 
specialist right as we are entering an important inspection cycle. At Vizag we had a 
near-miss with a contractor workforce dispute six months ago — a reminder of how exposed 
we are if that export plant goes down even briefly.

Interviewer: Top risks in the next 12 months?

Rajiv: One — the regulatory situation with the US authority. Binary and immediate. 
Two — raw material supply from China. No easy fallback. Qualifying alternates takes 
12 months and costs money. Three — a technology failure touching our compliance systems. 
A security incident that also triggers a regulatory response simultaneously would be 
very damaging.

Interviewer: What are you not paying enough attention to?

Rajiv: Our Vizag plant sits on the coast in Andhra Pradesh. We have had serious weather 
events in recent years — heavier rainfall, a flooding event near the port. Our business 
continuity plan has not been reviewed since 2023. It keeps getting deprioritised.

The other one — and I say this as someone who does not track geopolitics closely — is 
that our business is quite exposed to how relationships between large countries evolve. 
We source from China, we sell to America, our shipping goes through sensitive parts of 
the world. If any of those relationships deteriorate we feel it through our suppliers, 
our freight costs, our regulatory treatment. But we do not have a structured way to 
monitor or anticipate that. We react rather than get ahead of it.

Interviewer: That is exactly what this assessment is designed to address. Thank you, Rajiv.
"""

if __name__ == "__main__":
    main()
