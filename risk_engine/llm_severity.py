import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone

from io_paths import tag_filename


# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
GROQ_URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.05"))
GROQ_TIMEOUT_SEC = int(os.getenv("GROQ_TIMEOUT_SEC", "180"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:70b")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.05"))
OLLAMA_TIMEOUT_SEC = int(os.getenv("OLLAMA_TIMEOUT_SEC", "180"))
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()

CHECKPOINT_EVERY = int(os.getenv("SAVE_CHECKPOINT_EVERY", "5"))
RESUME_RUN = os.getenv("RESUME_RUN", "true").strip().lower() in {"1", "true", "yes", "y"}
SECTOR_TOP_N = int(os.getenv("SECTOR_TOP_N", "10"))


THEME_GUIDANCE = {
    "Strategy & Business Model": "market share, strategic positioning, pricing power, partner ecosystem, long-term viability, major demand/supply shifts",
    "Finance/Treasury/FP&A": "liquidity, cash flow volatility, financing access, sanctions exposure, FX/commodity shocks, credit and solvency pressure",
    "Operations": "production continuity, logistics reliability, facility uptime, critical supplier disruption, operational safety and delivery performance",
    "Human Resources": "workforce safety, labor availability, retention risk, talent mobility constraints, legal and morale impact on staff",
    "Cybersecurity": "cyber attack surface, data loss/exfiltration, ransomware downtime risk, third-party cyber contagion, control environment stress",
    "Governance, Risk & Compliance": "regulatory/legal action, compliance burden, policy enforcement, reporting/governance failures, sanctions and audit risk",
    "Governance, Risk & Complaiance": "regulatory/legal action, compliance burden, policy enforcement, reporting/governance failures, sanctions and audit risk",
}


SECTOR_KEYWORDS = {
    "Financial Services": {
        "bank", "banking", "finance", "financial", "treasury", "insurance", "capital",
        "credit", "liquidity", "loan", "bond", "equity", "stock exchange", "payment",
        "fintech", "asset manager", "wealth management", "currency", "fx", "interest rate",
    },
    "Energy & Utilities": {
        "oil", "gas", "lng", "refinery", "petrochemical", "electricity", "power grid",
        "utility", "pipeline", "renewable", "solar", "wind", "nuclear plant", "hydrogen",
        "energy ministry", "water utility",
    },
    "Healthcare & Life Sciences": {
        "hospital", "healthcare", "pharma", "biotech", "drug", "fda", "clinical trial",
        "vaccine", "medical device", "gene therapy", "oncology", "patient", "diagnostic",
    },
    "Technology & Telecommunications": {
        "semiconductor", "chip", "ai", "cloud", "software", "cyber", "ransomware",
        "data center", "telecom", "5g", "platform", "api", "saas", "it services",
    },
    "Industrial & Manufacturing": {
        "manufacturing", "factory", "plant", "industrial", "machinery", "automation",
        "production", "assembly", "supplier", "component", "heavy industry",
    },
    "Transportation & Logistics": {
        "shipping", "port", "freight", "cargo", "logistics", "airline", "aviation",
        "rail", "truck", "trucking", "maritime", "corridor", "customs", "suez", "hormuz",
    },
    "Consumer, Retail & E-Commerce": {
        "retail", "consumer", "e-commerce", "shopping", "fmcg", "brand", "supermarket",
        "store", "fashion", "cosmetics", "beverage", "food service",
    },
    "Defense, Aerospace & Security": {
        "defense", "military", "missile", "airstrike", "army", "navy", "air force",
        "aerospace", "weapon", "munitions", "nuclear", "security force",
    },
    "Government, Public Policy & Regulatory": {
        "government", "ministry", "regulator", "policy", "law", "sanction", "export control",
        "embargo", "parliament", "congress", "public sector", "sovereign",
    },
    "Real Estate & Construction": {
        "real estate", "property", "construction", "infrastructure project", "housing",
        "contractor", "cement", "building permit",
    },
    "Agriculture & Food Supply": {
        "agriculture", "farming", "crop", "fertilizer", "grain", "wheat", "food supply",
        "livestock", "dairy", "aquaculture",
    },
    "Mining, Metals & Materials": {
        "mining", "metal", "copper", "lithium", "nickel", "steel", "aluminum", "ore",
        "rare earth", "smelter",
    },
    "Education & Research": {
        "university", "school", "education", "research institute", "academic", "campus",
    },
    "Media, Sports & Entertainment": {
        "media", "sports", "football", "cricket", "basketball", "entertainment",
        "celebrity", "festival", "awards", "fashion week",
    },
}


THEME_DEFAULT_SECTOR = {
    "Finance/Treasury/FP&A": "Financial Services",
    "Operations": "Industrial & Manufacturing",
    "Human Resources": "Government, Public Policy & Regulatory",
    "Cybersecurity": "Technology & Telecommunications",
    "Governance, Risk & Compliance": "Government, Public Policy & Regulatory",
    "Governance, Risk & Complaiance": "Government, Public Policy & Regulatory",
    "Strategy & Business Model": "Cross-Sector / Multi-Industry",
}


COUNTRY_COORDS = {
    "united states": (39.8283, -98.5795),
    "usa": (39.8283, -98.5795),
    "iran": (32.4279, 53.6880),
    "saudi arabia": (23.8859, 45.0792),
    "united arab emirates": (23.4241, 53.8478),
    "uae": (23.4241, 53.8478),
    "north korea": (40.3399, 127.5101),
    "south korea": (35.9078, 127.7669),
    "china": (35.8617, 104.1954),
    "japan": (36.2048, 138.2529),
    "germany": (51.1657, 10.4515),
    "france": (46.2276, 2.2137),
    "italy": (41.8719, 12.5674),
    "spain": (40.4637, -3.7492),
    "switzerland": (46.8182, 8.2275),
    "denmark": (56.2639, 9.5018),
    "turkey": (38.9637, 35.2433),
    "lebanon": (33.8547, 35.8623),
    "yemen": (15.5527, 48.5164),
    "kuwait": (29.3117, 47.4818),
    "bahrain": (25.9304, 50.6378),
    "iraq": (33.2232, 43.6793),
    "russia": (61.5240, 105.3188),
    "cyprus": (35.1264, 33.4299),
    "india": (20.5937, 78.9629),
    "united kingdom": (55.3781, -3.4360),
    "malaysia": (4.2105, 101.9758),
    "australia": (-25.2744, 133.7751),
    "israel": (31.0461, 34.8516),
    "canada": (56.1304, -106.3468),
    "nigeria": (9.0820, 8.6753),
    "chile": (-35.6751, -71.5430),
    "jordan": (30.5852, 36.2384),
    "togo": (8.6195, 0.8248),
}


CITY_COORDS = {
    "riyadh": (24.7136, 46.6753),
    "tehran": (35.6892, 51.3890),
    "makkah": (21.3891, 39.8579),
    "jeddah": (21.4858, 39.1925),
    "madinah": (24.5247, 39.5692),
    "nuremberg": (49.4521, 11.0767),
    "guangdong": (23.1291, 113.2644),
    "denizli": (37.7765, 29.0864),
    "south san francisco": (37.6547, -122.4077),
    "paris": (48.8566, 2.3522),
    "zug": (47.1662, 8.5155),
    "silivri": (41.0735, 28.2460),
    "hyderabad": (17.3850, 78.4867),
    "glasgow": (55.8642, -4.2518),
    "kuala lumpur": (3.1390, 101.6869),
    "los angeles": (34.0522, -118.2437),
    "tampa": (27.9506, -82.4572),
    "dammam": (26.4207, 50.0888),
    "gaza": (31.5017, 34.4668),
    "farasan": (16.7027, 42.1187),
    "chesapeake bay": (37.8000, -76.2500),
    "strait of hormuz": (26.5667, 56.2500),
    "mediterranean sea": (34.5, 18.0),
    "dubai": (25.2048, 55.2708),
    "abu dhabi": (24.4539, 54.3773),
    "fujairah": (25.1288, 56.3265),
    "bratislava": (48.1486, 17.1077),
    "kansas city": (39.0997, -94.5786),
    "atlanta": (33.7490, -84.3880),
    "florence": (43.7696, 11.2558),
    "pescara": (42.4618, 14.2161),
}


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------


def clip_text(text: str, limit: int = 1200) -> str:
    if text is None:
        return ""
    s = str(text).strip()
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "..."



def _theme_lens(theme: str) -> str:
    return THEME_GUIDANCE.get(theme, "theme-specific enterprise exposure pathways")



def normalize_text(value: str) -> str:
    if value is None:
        return ""
    return " ".join(str(value).lower().split())


def classify_sector(event: dict):
    text = " ".join(
        [
            normalize_text(event.get("headline")),
            normalize_text(event.get("summary")),
            normalize_text(event.get("actor")),
            normalize_text(event.get("verb") or event.get("action")),
            normalize_text(event.get("object") or event.get("target")),
            normalize_text(event.get("structural_domain")),
            normalize_text(event.get("geography")),
            normalize_text(event.get("internal_theme") or event.get("primary_internal_theme")),
        ]
    )

    best_sector = "Cross-Sector / Multi-Industry"
    best_score = 0
    best_hits = []

    for sector, terms in SECTOR_KEYWORDS.items():
        hits = [t for t in terms if t in text]
        score = len(hits)
        if score > best_score:
            best_sector = sector
            best_score = score
            best_hits = hits

    if best_score == 0:
        fallback = THEME_DEFAULT_SECTOR.get(
            event.get("internal_theme") or event.get("primary_internal_theme"),
            "Cross-Sector / Multi-Industry",
        )
        return fallback, []

    return best_sector, best_hits[:8]


def build_sector_top_risk_report(rows: list, top_n: int):
    sector_groups = {}
    for row in rows:
        sector = row.get("sector") or classify_sector(row)[0]
        row["sector"] = sector
        sector_groups.setdefault(sector, []).append(row)

    sectors_out = []
    for sector, items in sector_groups.items():
        ranked = sorted(
            items,
            key=lambda x: float(x.get("severity_score") or 0.0),
            reverse=True,
        )
        top_rows = ranked[:top_n]
        avg_severity = (
            sum(float(x.get("severity_score") or 0.0) for x in items) / len(items)
            if items
            else 0.0
        )
        sectors_out.append(
            {
                "sector": sector,
                "event_count": len(items),
                "avg_severity": round(avg_severity, 3),
                "high_risk_count": sum(
                    1 for x in items if float(x.get("severity_score") or 0.0) >= 0.60
                ),
                "critical_risk_count": sum(
                    1 for x in items if float(x.get("severity_score") or 0.0) >= 0.80
                ),
                "top_risks": [
                    {
                        "event_id": x.get("event_id"),
                        "headline": x.get("headline"),
                        "severity_score": x.get("severity_score"),
                        "internal_theme": x.get("internal_theme"),
                        "structural_domain": x.get("structural_domain"),
                        "geography": x.get("geography"),
                    }
                    for x in top_rows
                ],
            }
        )

    sectors_out.sort(
        key=lambda s: (s["avg_severity"], s["event_count"]),
        reverse=True,
    )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "top_n_per_sector": top_n,
        "sector_count": len(sectors_out),
        "sectors": sectors_out,
    }


# ---------------------------------------------------
# LLM SCORING
# ---------------------------------------------------


def build_prompt(event: dict, theme: str) -> str:
    domain = event.get("structural_domain") or "Unknown Domain"

    actor = event.get("actor") or ""
    action = event.get("verb") or event.get("action") or ""
    target = event.get("object") or event.get("target") or ""
    headline = clip_text(event.get("headline") or "", 500)
    summary = clip_text(event.get("summary") or "", 1800)
    geography = event.get("geography") or ""

    theme_lens = _theme_lens(theme)

    return f"""
You are a senior enterprise risk analyst evaluating geopolitical and macro events for enterprise impact.

Your task is to score the severity of ONE event strictly against ONE internal enterprise theme.

Internal Theme (primary scoring lens): {theme}
Theme lens definition: {theme_lens}
Structural Domain: {domain}

Event data:
Headline: {headline}
Summary: {summary}
Actor: {actor}
Action: {action}
Target: {target}
Geography: {geography}

IMPORTANT PRINCIPLE:
Score ONLY the potential enterprise impact on the specified internal theme.
Ignore general geopolitical drama unless it creates a direct business risk signal.
Use only the provided event fields and the theme lens; do not rely on external assumptions.
Do not output any rationale. Return only the final numeric severity.

-------------------------------------
STEP 1 - EVENT VALIDITY CHECK
-------------------------------------

If the event is any of the following, assign severity between 0.00 and 0.15:
- opinion pieces
- commentary or analysis articles
- sports news
- celebrity or entertainment news
- political rhetoric without policy change
- general news reporting without enterprise impact
- historical comparisons
- social media reactions
- symbolic diplomatic gestures
- minor local incidents with no economic or operational implication
- academic discussions or think-tank commentary

-------------------------------------
STEP 2 - MATERIALITY FILTER
-------------------------------------

An event should only receive a score above 0.40 if it contains a material enterprise signal, such as:
- sanctions
- export controls
- regulatory or policy changes
- trade restrictions
- military escalation affecting supply chains
- financial system instability
- currency or banking disruption
- commodity supply shocks
- cyber attacks on infrastructure
- shutdown of logistics corridors
- infrastructure destruction
- forced migration affecting labor supply
- sovereign defaults
- asset seizures or nationalization
- major geopolitical conflict escalation
- government directives impacting industries
- supply chain disruption

If none of these are present, the score should remain below 0.40.

-------------------------------------
STEP 3 - THEME RELEVANCE FILTER
-------------------------------------

Even if the event is globally important, score it LOW unless it directly affects the given internal theme.

Examples:
- Finance/Treasury themes: sanctions, banking instability, currency collapse, sovereign debt, capital controls.
- Operations themes: logistics disruption, supply shutdown, infrastructure damage, labor disruption.
- Strategy themes: market access restrictions, geopolitical realignment, structural industry shifts.

If connection to the theme is weak or indirect, keep severity below 0.35.

-------------------------------------
STEP 4 - SEVERITY ASSESSMENT
-------------------------------------

Assess severity using:
1. Immediacy
2. Magnitude
3. Likelihood
4. Persistence

SEVERITY SCALE:
0.00-0.19 negligible/noise
0.20-0.39 low relevance
0.40-0.59 moderate exposure
0.60-0.79 high enterprise risk
0.80-1.00 critical impact

Only assign 0.80+ for clear, material, near-term enterprise risk signals.

OUTPUT REQUIREMENTS:
Return ONLY a single numeric value between 0 and 1.
No explanation.
No text.
No JSON.
Example output:
0.67
""".strip()



def parse_numeric_score(raw_text: str, default: float = 0.2) -> float:
    text = (raw_text or "").strip().replace("\n", " ")
    try:
        value = float(text)
        return max(0.0, min(1.0, value))
    except Exception:
        pass

    match = re.search(r"([01](?:\.\d+)?)", text)
    if match:
        try:
            value = float(match.group(1))
            return max(0.0, min(1.0, value))
        except Exception:
            pass

    return default


def call_ollama_chat(prompt: str) -> str:
    endpoint = OLLAMA_URL.rstrip("/") + "/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": OLLAMA_TEMPERATURE},
    }
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY.strip():
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY.strip()}"

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SEC) as resp:
        body = resp.read().decode("utf-8")

    data = json.loads(body)
    return data.get("message", {}).get("content", "")


def call_groq_chat(prompt: str) -> str:
    endpoint = GROQ_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": GROQ_TEMPERATURE,
    }
    if not GROQ_API_KEY:
        raise ValueError("Missing GROQ_API_KEY. Export GROQ_API_KEY in your environment.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=GROQ_TIMEOUT_SEC) as resp:
        body = resp.read().decode("utf-8")

    data = json.loads(body)
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def evaluate_event_severity(event: dict, theme: str) -> dict:
    prompt = build_prompt(event, theme)

    if LLM_PROVIDER == "groq":
        raw = call_groq_chat(prompt)
    elif LLM_PROVIDER == "ollama":
        raw = call_ollama_chat(prompt)
    else:
        raise ValueError("Unsupported provider. Set LLM_PROVIDER=groq or LLM_PROVIDER=ollama.")

    final = round(parse_numeric_score(raw, default=0.2), 3)

    return {
        "severity_score": final,
        "raw_model_output": clip_text(raw, 1200),
    }


# ---------------------------------------------------
# GEO RESOLUTION
# ---------------------------------------------------


def normalize_geo_text(value: str) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.replace("(", " ").replace(")", " ")
    text = text.replace(";", ",")
    text = " ".join(text.split())
    return text



def resolve_geo(geography: str):
    geo = normalize_geo_text(geography)

    if not geo or geo in {"unknown", "unspecified", "not specified", "n/a", "na", "virtual", "mj"}:
        return None, None, "none"

    if geo in {
        "global",
        "world",
        "international",
        "middle east",
        "asia-pacific region",
        "north america, western europe",
        "oecd",
        "national",
    }:
        return 20.0, 0.0, "global-default"

    for city, (lat, lon) in CITY_COORDS.items():
        if geo == city or city in geo:
            return lat, lon, f"city:{city}"

    tokens = [t.strip() for t in geo.split(",") if t.strip()]
    for token in tokens + [geo]:
        for country, (lat, lon) in COUNTRY_COORDS.items():
            if token == country or country in token or token in country:
                return lat, lon, f"country:{country}"

    for country, (lat, lon) in COUNTRY_COORDS.items():
        if country in geo:
            return lat, lon, f"country:{country}"

    return None, None, "unresolved"



def save_results_snapshot(output_path: str, rows: list) -> None:
    with open(output_path, "w") as f:
        json.dump(rows, f, indent=4)


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------

if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)

    tagged_input = os.path.join(base_dir, "data", tag_filename("external_mapped_events.json"))
    default_input = os.path.join(base_dir, "data", "external_mapped_events.json")
    input_path = tagged_input if os.path.exists(tagged_input) else default_input

    output_results = os.path.join(base_dir, "data", tag_filename("event_severity_results.json"))
    output_sector = os.path.join(
        base_dir,
        "data",
        tag_filename(f"sector_top_{SECTOR_TOP_N}_risks.json"),
    )

    print("\n================ EVENT SEVERITY ENGINE ================\n")
    print("Provider:", LLM_PROVIDER)
    if LLM_PROVIDER == "groq":
        print("Groq URL:", GROQ_URL)
        print("Model:", GROQ_MODEL)
    else:
        print("Ollama URL:", OLLAMA_URL)
        print("Model:", OLLAMA_MODEL)
    print("Loading dataset from:", input_path)

    with open(input_path, "r") as f:
        events = json.load(f)

    print("Total events found:", len(events))

    results = []
    processed_event_ids = set()

    if RESUME_RUN and os.path.exists(output_results):
        try:
            with open(output_results, "r") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                results = existing
                for row in results:
                    if not row.get("sector"):
                        sector, hits = classify_sector(row)
                        row["sector"] = sector
                        row["sector_keyword_hits"] = hits
                processed_event_ids = {str(r.get("event_id")) for r in results if r.get("event_id")}
                print(f"Resume mode: loaded {len(results)} already-processed events from {output_results}")
        except Exception as exc:
            print(f"Resume load skipped due to parse error: {exc}")

    print("\nCalculating severity for each event...\n")

    try:
        for idx, event in enumerate(events):
            event_id = str(event.get("event_id", ""))
            if RESUME_RUN and event_id and event_id in processed_event_ids:
                continue

            domain = event.get("structural_domain", "Unknown Domain")
            theme = event.get("primary_internal_theme") or event.get("internal_theme") or "Operations"

            try:
                score_detail = evaluate_event_severity(event, theme)
            except urllib.error.URLError as exc:
                print(f"Provider connection error at event {idx}: {exc}. Saving progress and stopping.")
                break
            except Exception as exc:
                print(f"Error processing event {idx}: {exc}")
                score_detail = {
                    "severity_score": 0.25,
                    "raw_model_output": "",
                }

            lat, lon, geo_source = resolve_geo(event.get("geography", ""))
            sector, sector_hits = classify_sector(event)

            row = {
                "event_index": idx,
                "event_id": event.get("event_id"),
                "headline": event.get("headline"),
                "summary": event.get("summary"),
                "actor": event.get("actor"),
                "action": event.get("verb") or event.get("action"),
                "target": event.get("object") or event.get("target"),
                "structural_domain": domain,
                "internal_theme": theme,
                "severity_score": score_detail["severity_score"],
                "geography": event.get("geography"),
                "lat": lat,
                "lon": lon,
                "geo_resolution_source": geo_source,
                "sector": sector,
                "sector_keyword_hits": sector_hits,
                "raw_model_output": score_detail["raw_model_output"],
            }

            results.append(row)
            if event_id:
                processed_event_ids.add(event_id)

            print(
                f"Event {idx:03d} | Theme: {theme} | Severity: {row['severity_score']:.2f} | Geo: {geo_source}"
            )

            if CHECKPOINT_EVERY > 0 and len(results) % CHECKPOINT_EVERY == 0:
                save_results_snapshot(output_results, results)
                print(f"Checkpoint saved ({len(results)} rows) -> {output_results}")

    except KeyboardInterrupt:
        print("\nRun interrupted. Saving processed events.")
    finally:
        save_results_snapshot(output_results, results)
        print(f"Final snapshot saved ({len(results)} rows) -> {output_results}")
        sector_report = build_sector_top_risk_report(results, SECTOR_TOP_N)
        with open(output_sector, "w") as f:
            json.dump(sector_report, f, indent=4)
        print(f"Sector top risk report saved -> {output_sector}")

    print("\n================ SUMMARY ================\n")

    summary = Counter(r["internal_theme"] for r in results)
    print("Theme counts:", dict(summary))
    if results:
        avg = sum(r["severity_score"] for r in results) / len(results)
        print("Average severity:", round(avg, 3))

    geo_stats = Counter(r["geo_resolution_source"] for r in results)
    print("Geo resolution stats:", dict(geo_stats))
    sector_stats = Counter(r.get("sector", "Unknown") for r in results)
    print("Sector counts:", dict(sector_stats))
    print("\nFinished processing.\n")
