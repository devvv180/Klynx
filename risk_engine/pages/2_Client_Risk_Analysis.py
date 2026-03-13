"""
Client Risk Analysis — Signal AI-style dashboard
Reads: client_data.json, client_theme_exposure.json, merged_lexis_event_frames_similarity_v1.jsonl
"""

import html
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from textwrap import dedent
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from io_paths import get_output_tag, tag_filename

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Client Risk Analysis",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -------------------------------------------------
# SHARED STYLES (matches Sector Risk Explorer)
# -------------------------------------------------

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #0e1117;
    --bg-soft: #141b23;
    --card: #161f2a;
    --card-border: #263242;
    --text: #e6edf3;
    --text-muted: #94a3b8;
    --brand: #2f81f7;
    --high: #ff5d5d;
    --medium: #f9b44d;
    --low: #3ecf8e;
}

html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }

.stApp {
    background: radial-gradient(900px 420px at 90% -10%, rgba(47,129,247,0.15), rgba(14,17,23,0) 60%),
                radial-gradient(900px 520px at -10% 110%, rgba(62,207,142,0.08), rgba(14,17,23,0) 60%),
                var(--bg);
    color: var(--text);
}

h1, h2, h3, h4 { color: var(--text); letter-spacing: 0.1px; }

.panel {
    background: linear-gradient(180deg, rgba(22,31,42,0.94) 0%, rgba(20,27,35,0.94) 100%);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 10px 14px;
    box-shadow: 0 12px 30px rgba(0,0,0,0.28);
}

.event-card {
    background: linear-gradient(165deg, #1a2431 0%, #151c27 100%);
    border: 1px solid #2a3648;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.26);
}

.event-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.event-rank {
    color: #9db5d8;
    font-size: 0.82rem;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    font-weight: 700;
}

.event-title {
    font-size: 1.04rem;
    line-height: 1.4;
    font-weight: 700;
    text-decoration: none;
    color: #dbeafe;
}
.event-title:hover { color: #93c5fd; }

.event-grid {
    margin-top: 10px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 8px;
}

.meta-chip {
    background-color: #111722;
    border: 1px solid #233246;
    border-radius: 8px;
    padding: 8px 10px;
}

.meta-label {
    color: var(--text-muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.meta-value {
    margin-top: 2px;
    color: #d9e6f7;
    font-size: 0.88rem;
    font-weight: 600;
    word-break: break-word;
    overflow-wrap: anywhere;
}

.severity-track {
    width: 100%;
    height: 7px;
    border-radius: 99px;
    background: #0f1520;
    border: 1px solid #253449;
    margin-top: 10px;
}
.severity-fill { height: 100%; border-radius: 99px; }

.risk-pill {
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.5px;
}
.risk-high {
    color: #ffd9d9;
    background: rgba(255, 93, 93, 0.2);
    border: 1px solid rgba(255, 93, 93, 0.4);
}
.risk-medium {
    color: #ffe6bd;
    background: rgba(249, 180, 77, 0.2);
    border: 1px solid rgba(249, 180, 77, 0.4);
}
.risk-low {
    color: #cdfbe6;
    background: rgba(62, 207, 142, 0.18);
    border: 1px solid rgba(62, 207, 142, 0.36);
}

.client-connection {
    margin-top: 10px;
    padding: 10px 14px;
    background: rgba(47,129,247,0.08);
    border-left: 3px solid #2f81f7;
    border-radius: 4px;
    font-size: 0.88rem;
    color: #c8d9f0;
}

.narrative-card {
    background: linear-gradient(165deg, #1a2431 0%, #151c27 100%);
    border: 1px solid #2a3648;
    border-radius: 14px;
    padding: 22px 24px;
    margin-bottom: 16px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.30);
}
.narrative-card.critical { border-left: 4px solid #ff5d5d; }
.narrative-card.high { border-left: 4px solid #f9b44d; }
.narrative-card.medium { border-left: 4px solid #38bdf8; }

.narrative-rank {
    color: #9db5d8;
    font-size: 0.78rem;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 6px;
}

.narrative-title {
    font-size: 1.12rem;
    line-height: 1.45;
    font-weight: 700;
    color: #dbeafe;
    margin-bottom: 12px;
}

.narrative-text {
    font-size: 0.92rem;
    line-height: 1.65;
    color: #b8c9de;
    margin-bottom: 14px;
}

.narrative-evidence {
    margin-top: 10px;
    padding: 10px 14px;
    background: rgba(47,129,247,0.06);
    border-left: 3px solid #2f81f7;
    border-radius: 4px;
    font-size: 0.84rem;
    color: #94a3b8;
}

.narrative-impact {
    margin-top: 10px;
    padding: 10px 14px;
    background: rgba(255,93,93,0.06);
    border-left: 3px solid #ff5d5d;
    border-radius: 4px;
    font-size: 0.88rem;
    color: #c8d9f0;
}

.narrative-action {
    margin-top: 10px;
    padding: 10px 14px;
    background: rgba(62,207,142,0.08);
    border-left: 3px solid #3ecf8e;
    border-radius: 4px;
    font-size: 0.88rem;
    color: #c8d9f0;
}
</style>
""",
    unsafe_allow_html=True,
)


# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def severity_label(score: float) -> str:
    if score >= 0.8:
        return "High"
    if score >= 0.5:
        return "Medium"
    return "Low"

def risk_css(score: float) -> str:
    if score >= 0.8:
        return "risk-high"
    if score >= 0.5:
        return "risk-medium"
    return "risk-low"

def severity_color(score: float) -> str:
    if score >= 0.8:
        return "#ff5d5d"
    if score >= 0.5:
        return "#f9b44d"
    return "#3ecf8e"

def clip_text(value: str, limit: int = 100) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."

def clean_text(value, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    text = str(value).strip()
    return fallback if (not text or text.lower() == "nan") else text

def add_geo_jitter(events: pd.DataFrame) -> pd.DataFrame:
    jittered = events.copy()
    jittered["coord_rank"] = jittered.groupby(["lat", "lon"]).cumcount()
    jittered["coord_total"] = jittered.groupby(["lat", "lon"])["event_id"].transform("count")
    plot_lat, plot_lon = [], []
    for lat, lon, rank, total in jittered[["lat", "lon", "coord_rank", "coord_total"]].itertuples(index=False):
        if int(total) <= 1:
            plot_lat.append(lat)
            plot_lon.append(lon)
            continue
        ring = 1 + (int(rank) // 8)
        slot = int(rank) % 8
        angle = (slot / 8.0) * 2 * math.pi + (ring * 0.35)
        offset = 0.11 * ring
        plot_lat.append(lat + offset * math.sin(angle))
        plot_lon.append(lon + offset * math.cos(angle))
    jittered["plot_lat"] = plot_lat
    jittered["plot_lon"] = plot_lon
    return jittered

# -------------------------------------------------
# SIGNAL AI PILLAR MAPPING
# Maps predicted_structural_driver → Signal AI pillar
# -------------------------------------------------

DRIVER_TO_PILLAR = {
    "Geopolitical & Sovereign": "Geopolitical",
    "Technological & Digital": "Technology",
    "Regulatory & Policy Regime": "Regulatory",
    "Societal & Human Capital": "Workforce",
    "Environmental & Climate": "ESG/Climate",
    "Infrastructure & Critical Systems": "Operational",
    "Market & Industry Structure": "Competitive",
    "Macroeconomic & Financial System": "Macro/Financial",
}

PILLAR_COLORS = {
    "Geopolitical": "#ff5d5d",
    "Technology": "#5b8def",
    "Regulatory": "#3ecf8e",
    "Workforce": "#a78bfa",
    "ESG/Climate": "#6ee7b7",
    "Operational": "#f9b44d",
    "Competitive": "#38bdf8",
    "Macro/Financial": "#fbbf24",
}

# -------------------------------------------------
# EXPOSURE DIMENSION DEFINITIONS
# -------------------------------------------------

DIMENSION_KEYS = {
    "Workforce": {"prefix": "2.", "fields": [
        ("2.1", "Global Workforce Size"),
        ("2.2", "Geographic Concentration"),
        ("2.3", "Specialized Talent Dependence"),
        ("2.4", "Organized Labor Exposure"),
        ("2.5", "Operational Flexibility"),
        ("2.6", "Cost Flexibility"),
        ("2.7", "Reputational Sensitivity"),
    ]},
    "Financial": {"prefix": "3.", "fields": [
        ("3.1", "Capital Structure"),
        ("3.2", "Liquidity Resilience"),
        ("3.3", "Revenue Predictability"),
        ("3.4", "Cost Structure Flexibility"),
        ("3.5", "FX Exposure"),
        ("3.6", "Pricing Power"),
        ("3.7", "Capital Markets Access"),
    ]},
    "Supply Chain": {"prefix": "4.", "fields": [
        ("4.1", "Critical Input Concentration"),
        ("4.2", "Geographic Sourcing Spread"),
        ("4.3", "Logistics Dependency"),
        ("4.4", "Supplier Replacement"),
        ("4.5", "Energy Sensitivity"),
        ("4.6", "Service Provider Reliance"),
        ("4.7", "Inventory Buffer"),
    ]},
    "Technology": {"prefix": "5.", "fields": [
        ("5.1", "Digital Dependency"),
        ("5.2", "Cloud Concentration"),
        ("5.3", "Cyber Threat Exposure"),
        ("5.4", "Data Regulation Complexity"),
        ("5.5", "Digital Redundancy"),
        ("5.6", "AI Dependence"),
    ]},
    "Regulatory": {"prefix": "6.", "fields": [
        ("6.1", "Core Regulatory Intensity"),
        ("6.2", "Jurisdiction Complexity"),
        ("6.3", "Licensing Dependency"),
        ("6.4", "Enforcement Risk"),
        ("6.5", "Policy Shift Exposure"),
        ("6.6", "Government Revenue Dependence"),
    ]},
}

# Map pillars to exposure dimensions for relevance scoring
PILLAR_TO_DIMENSION = {
    "Geopolitical": ["Supply Chain", "Financial"],
    "Technology": ["Technology"],
    "Regulatory": ["Regulatory"],
    "Workforce": ["Workforce"],
    "ESG/Climate": ["Supply Chain"],
    "Operational": ["Supply Chain", "Technology"],
    "Competitive": ["Financial"],
    "Macro/Financial": ["Financial"],
}

# -------------------------------------------------
# REGION MATCHING KEYWORDS
# -------------------------------------------------

REGION_GEO_KEYWORDS = {
    "Middle East": ["iran", "iraq", "saudi arabia", "uae", "united arab emirates",
                    "qatar", "bahrain", "kuwait", "oman", "yemen", "jordan",
                    "lebanon", "syria", "israel", "strait of hormuz", "persian gulf"],
    "South Asia": ["india", "pakistan", "bangladesh", "sri lanka", "nepal",
                   "hyderabad", "vizag", "mumbai", "delhi", "chennai", "kolkata"],
    "Southeast Asia": ["vietnam", "thailand", "indonesia", "malaysia", "philippines",
                       "singapore", "myanmar", "cambodia", "laos"],
    "East Asia": ["china", "japan", "south korea", "north korea", "taiwan",
                  "hong kong", "guangdong", "beijing", "shanghai", "shenzhen"],
    "Europe": ["germany", "france", "uk", "united kingdom", "italy", "spain",
               "netherlands", "poland", "sweden", "norway", "switzerland"],
    "North America": ["united states", "usa", "us", "canada", "mexico"],
    "Africa": ["nigeria", "south africa", "kenya", "egypt", "ethiopia", "ghana"],
    "South America": ["brazil", "argentina", "chile", "colombia", "peru"],
}


# -------------------------------------------------
# DATA LOADING
# -------------------------------------------------

base_dir = os.path.dirname(os.path.dirname(__file__))

def load_client_profile():
    path = os.path.join(base_dir, "data", "client_data.json")
    if not os.path.exists(path):
        st.error(f"Missing file: data/client_data.json — run the client questionnaire first.")
        st.stop()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_theme_exposure():
    path = os.path.join(base_dir, "data", "client_theme_exposure.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_events_jsonl():
    """Load full event dataset for analytical panels."""
    path = os.path.join(base_dir, "data", "merged_lexis_event_frames_similarity_v1.jsonl")
    if not os.path.exists(path):
        st.error("Missing: merged_lexis_event_frames_similarity_v1.jsonl")
        st.stop()
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events

def load_risk_report():
    path = os.path.join(base_dir, "..", "..", "risk_match_report.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def load_risk_narratives():
    """Load LLM-generated client risk narratives."""
    path = os.path.join(base_dir, "data", "client_risk_narratives.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# -------------------------------------------------
# COMPUTE DIMENSION SCORES
# -------------------------------------------------

def compute_dimension_scores(profile: dict) -> dict:
    """Average the mappedScores for each exposure dimension."""
    scores = profile.get("mappedScores", {})
    result = {}
    for dim_name, dim_info in DIMENSION_KEYS.items():
        vals = []
        for key, _label in dim_info["fields"]:
            v = scores.get(key)
            if v is not None and isinstance(v, (int, float)):
                vals.append(v)
        result[dim_name] = round(sum(vals) / len(vals), 3) if vals else 0.0
    return result

# -------------------------------------------------
# COMPUTE CLIENT RELEVANCE SCORE
# -------------------------------------------------

def compute_relevance(event: dict, profile: dict, dim_scores: dict,
                      theme_lookup: dict, region_keywords: dict) -> float:
    """
    Relevance = geo_overlap(0.35) + theme_alignment(0.40) + dimension_match(0.25)
    Tightened scoring to reduce false positives.
    """
    # --- Geo overlap ---
    client_regions = set(r.lower() for r in profile.get("companyOverview", {}).get("selectedRegions", []))
    event_geos = set()
    for loc in event.get("geo_locations", []):
        if loc.get("country"):
            event_geos.add(loc["country"].lower())
        if loc.get("name"):
            event_geos.add(loc["name"].lower())
    for tag in event.get("geo_tags", []):
        event_geos.add(tag.lower())

    geo_hits = 0
    for region in client_regions:
        keywords = region_keywords.get(region, [region.lower()])
        for kw in keywords:
            if any(kw in eg for eg in event_geos):
                geo_hits += 1
                break
    geo_score = min(1.0, geo_hits / max(1, len(client_regions)))

    # --- Theme alignment ---
    pillar = DRIVER_TO_PILLAR.get(event.get("predicted_structural_driver", ""), "")
    theme_score = 0.0
    if pillar:
        # Use the event's structural similarity as base (weighted 70%)
        sim = float(event.get("predicted_structural_similarity", 0.5))
        # Boost if client has high exposure in related themes (weighted 30%)
        related_themes = []
        if pillar in ("Geopolitical", "Macro/Financial"):
            related_themes = ["Finance / Treasury / FP&A", "Procurement & Vendor Management"]
        elif pillar == "Technology":
            related_themes = ["Cybersecurity", "Data Governance"]
        elif pillar == "Regulatory":
            related_themes = ["Governance, Risk & Compliance", "Quality & Assurance"]
        elif pillar == "Workforce":
            related_themes = ["Human Resources", "Operations"]
        elif pillar == "ESG/Climate":
            related_themes = ["Business Continuity", "Operations"]
        elif pillar in ("Operational", "Competitive"):
            related_themes = ["Operations", "Procurement & Vendor Management"]

        max_exposure = 0.0
        for t in related_themes:
            exp = theme_lookup.get(t, 0.0)
            if exp > max_exposure:
                max_exposure = exp
        # Changed from 50/50 to 70/30 to prioritize event quality over client exposure
        theme_score = sim * 0.7 + max_exposure * 0.3

    # --- Dimension match ---
    dim_match = 0.0
    related_dims = PILLAR_TO_DIMENSION.get(pillar, [])
    if related_dims:
        dim_match = max(dim_scores.get(d, 0.0) for d in related_dims)

    # Changed weights: geo 0.35 (up from 0.30), theme 0.40 (same), dim 0.25 (down from 0.30)
    return round(geo_score * 0.35 + theme_score * 0.40 + dim_match * 0.25, 4)

# -------------------------------------------------
# LOAD ALL DATA
# -------------------------------------------------

profile = load_client_profile()
theme_exposure = load_theme_exposure()
raw_events = load_events_jsonl()
risk_report = load_risk_report()
risk_narratives = load_risk_narratives()

overview = profile.get("companyOverview", {})
dim_scores = compute_dimension_scores(profile)
theme_lookup = {t["internal_theme"]: t["exposure_score"] for t in theme_exposure}

# Build region keyword map from profile regions
profile_region_kw = {}
for region in overview.get("selectedRegions", []):
    profile_region_kw[region] = REGION_GEO_KEYWORDS.get(region, [region.lower()])

# Assign pillar + relevance to each event
for ev in raw_events:
    ev["pillar"] = DRIVER_TO_PILLAR.get(ev.get("predicted_structural_driver", ""), "Unknown")
    ev["relevance_score"] = compute_relevance(ev, profile, dim_scores, theme_lookup, profile_region_kw)

events_df = pd.DataFrame(raw_events)
events_df["relevance_score"] = pd.to_numeric(events_df["relevance_score"], errors="coerce").fillna(0)
events_df["predicted_structural_similarity"] = pd.to_numeric(
    events_df["predicted_structural_similarity"], errors="coerce"
).fillna(0.5)

# =================================================
# PAGE HEADER
# =================================================

st.title("Client Risk Analysis")
st.caption(f"Signal AI-style client-specific risk intelligence — {len(raw_events)} events")

# Add refresh button
if st.button("🔄 Force Refresh Data", help="Click if the dashboard is showing cached/old data"):
    st.cache_data.clear()
    st.rerun()

# -------------------------------------------------
# REQ 1: CLIENT PROFILE SUMMARY HEADER
# -------------------------------------------------

st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Industry", overview.get("primaryIndustry", "N/A"))
col2.metric("Secondary", overview.get("secondaryIndustry", "N/A"))
col3.metric("Regions", ", ".join(overview.get("selectedRegions", [])))
col4.metric("Events", len(raw_events))

# Enterprise multipliers
multipliers = overview.get("enterpriseMultipliers", {})
if multipliers:
    mcols = st.columns(len(multipliers))
    for i, (key, val) in enumerate(multipliers.items()):
        label = key.split(":")[1].strip() if ":" in key else key
        mcols[i].markdown(
            f"""<div class="meta-chip">
                <div class="meta-label">{html.escape(label)}</div>
                <div class="meta-value">{html.escape(str(val))}</div>
            </div>""",
            unsafe_allow_html=True,
        )

# =================================================
# PANEL 1: RISK SIGNAL VOLUME BY PILLAR
# =================================================

st.markdown("---")
st.subheader("Panel 1 — Risk Signal Volume by Pillar (Client-Relevant Only)")
st.caption(f"Showing {len(raw_events)} client-relevant events")

pillar_counts = events_df["pillar"].value_counts().reset_index()
pillar_counts.columns = ["Pillar", "Signal Count"]
pillar_counts = pillar_counts.sort_values("Signal Count", ascending=True)

fig_volume = go.Figure()
fig_volume.add_trace(go.Bar(
    y=pillar_counts["Pillar"],
    x=pillar_counts["Signal Count"],
    orientation="h",
    marker_color=[PILLAR_COLORS.get(p, "#5b8def") for p in pillar_counts["Pillar"]],
    text=pillar_counts["Signal Count"],
    textposition="outside",
    textfont=dict(color="#e6edf3"),
))
fig_volume.update_layout(
    title="Risk Signal Volume by Pillar (Mar 2026)",
    xaxis_title="Signal Count",
    yaxis_title="Risk Pillar",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#e6edf3",
    height=420,
    margin=dict(l=10, r=40, t=50, b=40),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
)
st.plotly_chart(fig_volume, use_container_width=True)

# =================================================
# PANEL 2: RISK HEATMAP — PILLAR × SIGNAL DOMAIN
# =================================================

st.markdown("---")
st.subheader("Panel 2 — Risk Heatmap: Pillar × Signal Domain (Client-Relevant Only)")
st.caption(f"Score = Signal Freq × Avg Embedding Confidence × 10 — using {len(raw_events)} relevant events")

# Build pillar × domain matrix from RELEVANT events only
heatmap_data = defaultdict(lambda: defaultdict(list))
for ev in raw_events:
    pillar = ev.get("pillar", "Unknown")
    domain = ev.get("predicted_structural_domain", "Unknown")
    sim = float(ev.get("predicted_structural_similarity", 0.5))
    heatmap_data[pillar][domain].append(sim)

# Compute scores
heatmap_rows = []
for pillar, domains in heatmap_data.items():
    for domain, sims in domains.items():
        score = round(len(sims) * (sum(sims) / len(sims)) * 10, 2)
        heatmap_rows.append({"Pillar": pillar, "Domain": domain, "Score": score})

hm_df = pd.DataFrame(heatmap_rows)
if not hm_df.empty:
    # Get top 12 domains by total score
    top_domains = hm_df.groupby("Domain")["Score"].sum().nlargest(12).index.tolist()
    hm_df = hm_df[hm_df["Domain"].isin(top_domains)]

    hm_pivot = hm_df.pivot_table(index="Pillar", columns="Domain", values="Score", fill_value=0)

    fig_heatmap = go.Figure(data=go.Heatmap(
        z=hm_pivot.values,
        x=[d[:30] + "..." if len(d) > 30 else d for d in hm_pivot.columns],
        y=hm_pivot.index.tolist(),
        colorscale=[[0, "#1a1a2e"], [0.3, "#f9b44d"], [0.6, "#ff7043"], [1, "#ff5d5d"]],
        text=np.round(hm_pivot.values, 1),
        texttemplate="%{text}",
        textfont=dict(size=11, color="#e6edf3"),
        hovertemplate="Pillar: %{y}<br>Domain: %{x}<br>Score: %{z:.1f}<extra></extra>",
        colorbar=dict(title="Risk Score"),
    ))
    fig_heatmap.update_layout(
        title="Risk Heatmap: Pillar × Signal Domain (Mar 2026)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e6edf3",
        height=480,
        margin=dict(l=10, r=10, t=50, b=100),
        xaxis=dict(tickangle=-35),
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)


# =================================================
# PANEL 3: GEOGRAPHIC RISK CONCENTRATION
# =================================================

st.markdown("---")
st.subheader("Panel 3 — Geographic Risk Concentration (Client-Relevant Only)")
st.caption(f"Score = Σ(signal confidence × geo relevance) — from {len(raw_events)} relevant events")

# Aggregate geo scores from RELEVANT events only
geo_agg = defaultdict(lambda: {"score": 0.0, "count": 0})
for ev in raw_events:
    sim = float(ev.get("predicted_structural_similarity", 0.5))
    for loc in ev.get("geo_locations", []):
        country = loc.get("country")
        if not country:
            continue
        rel = float(loc.get("relevance_score", 1))
        geo_agg[country]["score"] += sim * rel
        geo_agg[country]["count"] += 1

geo_rows = [{"Country": k, "Risk Exposure Score": round(v["score"], 1), "Signals": v["count"]}
            for k, v in geo_agg.items()]
geo_df = pd.DataFrame(geo_rows).sort_values("Risk Exposure Score", ascending=False).head(20)

if not geo_df.empty:
    # Color gradient: top 3 red-ish, rest light blue
    colors = []
    for i in range(len(geo_df)):
        if i < 3:
            colors.append(f"rgba(255, {93 + i * 40}, {93 + i * 40}, 0.9)")
        else:
            colors.append(f"rgba(150, {200 + min(i * 3, 55)}, {230 + min(i * 2, 25)}, 0.7)")

    fig_geo = go.Figure()
    fig_geo.add_trace(go.Bar(
        x=geo_df["Country"],
        y=geo_df["Risk Exposure Score"],
        marker_color=colors,
        text=[f"{s} signals" for s in geo_df["Signals"]],
        textposition="outside",
        textfont=dict(size=10, color="#94a3b8"),
    ))
    fig_geo.update_layout(
        title="Geographic Risk Concentration (Mar 2026)",
        yaxis_title="Risk Exposure Score",
        xaxis_title="Country",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e6edf3",
        height=460,
        margin=dict(l=10, r=10, t=50, b=80),
        xaxis=dict(tickangle=-35, gridcolor="rgba(255,255,255,0.03)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig_geo, use_container_width=True)

# =================================================
# PANEL 4: CLIENT RISK RADAR
# =================================================

st.markdown("---")
st.subheader("Panel 4 — Client Risk Radar")
st.caption("Client-personalised exposure — your company's risk profile across Signal AI pillars")

colR1, colR2 = st.columns([1, 1])

with colR1:
    # REQ 2: Exposure Dimension Radar
    dim_names = list(dim_scores.keys())
    dim_vals = [dim_scores[d] for d in dim_names]
    dim_vals_closed = dim_vals + [dim_vals[0]]
    dim_names_closed = dim_names + [dim_names[0]]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=dim_vals_closed,
        theta=dim_names_closed,
        fill="toself",
        fillcolor="rgba(255, 93, 93, 0.15)",
        line=dict(color="#ff5d5d", width=2),
        name="Client Exposure",
        hovertemplate="<b>%{theta}</b><br>Score: %{r:.2f}<extra></extra>",
    ))
    fig_radar.update_layout(
        title=dict(text="Exposure Dimension Radar", font=dict(size=16)),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True, range=[0, 1],
                gridcolor="rgba(255,255,255,0.1)",
                tickfont=dict(color="#94a3b8", size=10),
            ),
            angularaxis=dict(
                gridcolor="rgba(255,255,255,0.08)",
                tickfont=dict(color="#e6edf3", size=12),
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e6edf3",
        height=420,
        margin=dict(l=60, r=60, t=60, b=40),
        showlegend=False,
    )
    st.plotly_chart(fig_radar, use_container_width=True)

with colR2:
    # Pillar-level client relevance radar (from matching engine)
    pillar_relevance = events_df.groupby("pillar")["relevance_score"].mean()
    p_names = pillar_relevance.index.tolist()
    p_vals = pillar_relevance.values.tolist()
    p_vals_closed = p_vals + [p_vals[0]]
    p_names_closed = p_names + [p_names[0]]

    fig_pillar_radar = go.Figure()
    fig_pillar_radar.add_trace(go.Scatterpolar(
        r=p_vals_closed,
        theta=p_names_closed,
        fill="toself",
        fillcolor="rgba(255, 93, 93, 0.15)",
        line=dict(color="#ff5d5d", width=2),
        name="Pillar Relevance",
        hovertemplate="<b>%{theta}</b><br>Avg Relevance: %{r:.3f}<extra></extra>",
    ))
    fig_pillar_radar.update_layout(
        title=dict(text="Client Risk Radar — Pillar Relevance", font=dict(size=16)),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True, range=[0, max(p_vals) * 1.2 if p_vals else 0.6],
                gridcolor="rgba(255,255,255,0.1)",
                tickfont=dict(color="#94a3b8", size=10),
            ),
            angularaxis=dict(
                gridcolor="rgba(255,255,255,0.08)",
                tickfont=dict(color="#e6edf3", size=12),
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e6edf3",
        height=420,
        margin=dict(l=60, r=60, t=60, b=40),
        showlegend=False,
    )
    st.plotly_chart(fig_pillar_radar, use_container_width=True)


# =================================================
# REQ 3: THEME EXPOSURE HEATMAP
# =================================================

st.markdown("---")
st.subheader("Enterprise Risk Matrix — Theme Exposure × External Severity")
st.caption(f"Each event mapped to ONE primary theme — using {len(raw_events)} client-relevant events")

if theme_exposure:
    # Map events to internal themes using domain keywords (1 event → 1 primary theme)
    DOMAIN_TO_THEME = {
        # Geopolitical domains
        "diplomatic": "Procurement & Vendor Management",
        "sovereign": "Business Continuity",
        "border": "Procurement & Vendor Management",
        "trade war": "Finance / Treasury / FP&A",
        "tariff": "Finance / Treasury / FP&A",
        "sanctions": "Procurement & Vendor Management",
        "military": "Business Continuity",
        
        # Technology domains
        "cyber": "Cybersecurity",
        "ransomware": "Cybersecurity",
        "data breach": "Data Governance",
        "digital": "Data Governance",
        "ai": "Operations",
        "cloud": "Operations",
        
        # Regulatory domains
        "regulatory": "Governance, Risk & Compliance",
        "compliance": "Governance, Risk & Compliance",
        "policy": "Governance, Risk & Compliance",
        "enforcement": "Legal / Contracts",
        "legislation": "Legal / Contracts",
        "fda": "Quality & Assurance",
        "quality": "Quality & Assurance",
        
        # Workforce domains
        "labor": "Human Resources",
        "workforce": "Human Resources",
        "talent": "Human Resources",
        "strike": "Operations",
        
        # ESG/Climate domains
        "climate": "Business Continuity",
        "environmental": "Ethics & Conduct",
        "wildfire": "Business Continuity",
        "flood": "Business Continuity",
        "emission": "Ethics & Conduct",
        
        # Operational domains
        "supply chain": "Procurement & Vendor Management",
        "logistics": "Procurement & Vendor Management",
        "manufacturing": "Operations",
        "production": "Operations",
        
        # Competitive domains
        "market": "Strategy & Business Model",
        "competitive": "Strategy & Business Model",
        
        # Macro/Financial domains
        "commodity": "Finance / Treasury / FP&A",
        "currency": "Finance / Treasury / FP&A",
        "inflation": "Finance / Treasury / FP&A",
        "interest rate": "Finance / Treasury / FP&A",
    }

    # Assign each event to ONE primary theme from RELEVANT events only
    theme_severity = defaultdict(list)
    for ev in raw_events:
        domain = str(ev.get("predicted_structural_domain", "")).lower()
        sim = float(ev.get("predicted_structural_similarity", 0.5))
        
        # Find best matching theme
        matched_theme = None
        for keyword, theme in DOMAIN_TO_THEME.items():
            if keyword in domain:
                matched_theme = theme
                break
        
        # Fallback: use pillar for unmapped events
        if not matched_theme:
            pillar = ev.get("pillar", "")
            pillar_fallback = {
                "Geopolitical": "Procurement & Vendor Management",
                "Technology": "Cybersecurity",
                "Regulatory": "Governance, Risk & Compliance",
                "Workforce": "Human Resources",
                "ESG/Climate": "Business Continuity",
                "Operational": "Operations",
                "Competitive": "Strategy & Business Model",
                "Macro/Financial": "Finance / Treasury / FP&A",
            }
            matched_theme = pillar_fallback.get(pillar, "Operations")
        
        theme_severity[matched_theme].append(sim)

    enterprise_rows = []
    for te in theme_exposure:
        theme_name = te["internal_theme"]
        client_exp = te["exposure_score"]
        sev_list = theme_severity.get(theme_name, [])
        avg_sev = sum(sev_list) / len(sev_list) if sev_list else 0.0
        ent_risk = round(client_exp * avg_sev, 3)
        enterprise_rows.append({
            "Theme": theme_name,
            "Client Exposure": round(client_exp, 3),
            "External Severity": round(avg_sev, 3),
            "Enterprise Risk": ent_risk,
            "Signal Count": len(sev_list),
        })

    ent_df = pd.DataFrame(enterprise_rows).sort_values("Enterprise Risk", ascending=False)

    # Show data table first
    st.dataframe(
        ent_df,
        use_container_width=True,
        hide_index=True,
    )

    # Then visualization
    fig_ent = go.Figure()
    fig_ent.add_trace(go.Bar(
        y=ent_df["Theme"],
        x=ent_df["Client Exposure"],
        name="Client Exposure",
        orientation="h",
        marker_color="rgba(47,129,247,0.7)",
        text=ent_df["Client Exposure"].apply(lambda x: f"{x:.2f}"),
        textposition="inside",
        textfont=dict(size=10),
    ))
    fig_ent.add_trace(go.Bar(
        y=ent_df["Theme"],
        x=ent_df["External Severity"],
        name="External Severity",
        orientation="h",
        marker_color="rgba(255,93,93,0.7)",
        text=ent_df["External Severity"].apply(lambda x: f"{x:.2f}"),
        textposition="inside",
        textfont=dict(size=10),
    ))
    fig_ent.add_trace(go.Scatter(
        y=ent_df["Theme"],
        x=ent_df["Enterprise Risk"],
        name="Enterprise Risk",
        mode="markers+text",
        marker=dict(size=14, color="#fbbf24", symbol="diamond"),
        text=ent_df["Enterprise Risk"].apply(lambda x: f"{x:.3f}"),
        textposition="middle right",
        textfont=dict(color="#fbbf24", size=10, family="Manrope"),
    ))
    fig_ent.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e6edf3", family="Manrope"),
        height=520,
        margin=dict(l=10, r=80, t=20, b=40),
        xaxis=dict(range=[0, 1], gridcolor="rgba(255,255,255,0.05)", title="Score"),
        yaxis=dict(categoryorder="total ascending", gridcolor="rgba(255,255,255,0.03)"),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(0,0,0,0)",
        ),
        showlegend=True,
    )
    st.plotly_chart(fig_ent, use_container_width=True)

# =================================================
# REQ 6: TOP EMERGING RISKS — LLM NARRATIVE INTELLIGENCE
# =================================================

st.markdown("---")
st.subheader("🔍 Top Emerging Risks for Your Company")
st.caption("AI-generated intelligence narratives — how global events impact your business")

if risk_narratives and risk_narratives.get("top_3_risks"):
    for risk in risk_narratives["top_3_risks"]:
        rank = risk.get("rank", 0)
        title = html.escape(risk.get("risk_title", "Unknown Risk"))
        level = risk.get("risk_level", "Medium")
        narrative = html.escape(risk.get("narrative", ""))
        impact_areas = risk.get("impact_areas", [])

        level_lower = level.lower()
        pill_class = "risk-high" if level_lower == "critical" else ("risk-medium" if level_lower == "high" else "risk-low")
        card_class = level_lower if level_lower in ("critical", "high", "medium") else "medium"

        impact_chips = ""
        if impact_areas:
            chips = " &nbsp;".join(
                f'<span style="background:rgba(255,93,93,0.12);border:1px solid rgba(255,93,93,0.3);'
                f'border-radius:999px;padding:3px 10px;font-size:0.76rem;color:#ffd9d9;">{html.escape(a)}</span>'
                for a in impact_areas
            )
            impact_chips = f'<div style="margin-top:10px;">{chips}</div>'

        card_html = f"""
<div class="narrative-card {card_class}">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div class="narrative-rank">Emerging Risk #{rank}</div>
    <div class="risk-pill {pill_class}">{html.escape(level)}</div>
  </div>
  <div class="narrative-title">{title}</div>
  <div class="narrative-text">{narrative}</div>
  {impact_chips}
</div>"""
        st.markdown(card_html, unsafe_allow_html=True)
else:
    st.info("Run `python generate_risk_narratives.py` to generate AI risk narratives for your client.")


# Exposure Dimension Drill-Down section removed per user request


# =================================================
# REQ 8: REGIONAL EXPOSURE DETAIL PANEL
# =================================================

st.markdown("---")
st.subheader("Regional Exposure Detail")

regions = list(overview.get("regionalExposure", {}).keys())
if regions:
    selected_region = st.selectbox("Select Region", options=regions, index=0)
    region_data = overview["regionalExposure"].get(selected_region, {})

    # Display region details
    r_cols = st.columns(3)
    r_cols[0].markdown(
        f"""<div class="meta-chip">
            <div class="meta-label">Channels</div>
            <div class="meta-value">{html.escape(', '.join(region_data.get('channels', [])))}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    r_cols[1].markdown(
        f"""<div class="meta-chip">
            <div class="meta-label">Importance</div>
            <div class="meta-value">{html.escape(str(region_data.get('importance', 'N/A')))}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Show sub-categories
    sub_cats = {k: v for k, v in region_data.items() if isinstance(v, dict)}
    if sub_cats:
        for cat_name, cat_data in sub_cats.items():
            with st.expander(f"📋 {cat_name.title()} Details", expanded=False):
                for k, v in cat_data.items():
                    st.markdown(f"- **{k.replace('_', ' ').title()}**: {v}")

    # Show events matching this region (from relevant events only)
    region_kws = REGION_GEO_KEYWORDS.get(selected_region, [selected_region.lower()])
    matching_events = []
    for _, ev in events_df.iterrows():
        ev_geos = set()
        locs = ev.get("geo_locations")
        if isinstance(locs, list):
            for loc in locs:
                if loc.get("country"):
                    ev_geos.add(loc["country"].lower())
                if loc.get("name"):
                    ev_geos.add(loc["name"].lower())
        tags = ev.get("geo_tags")
        if isinstance(tags, list):
            for t in tags:
                ev_geos.add(t.lower())
        if any(kw in eg for kw in region_kws for eg in ev_geos):
            matching_events.append(ev)

    if matching_events:
        reg_df = pd.DataFrame(matching_events).sort_values("relevance_score", ascending=False).head(10)
        st.markdown(f"**Events in {selected_region}** ({len(matching_events)} total, showing top 10):")
        st.dataframe(
            reg_df[["headline", "pillar", "predicted_structural_domain", "relevance_score"]].rename(
                columns={
                    "headline": "Headline",
                    "pillar": "Pillar",
                    "predicted_structural_domain": "Domain",
                    "relevance_score": "Relevance",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(f"No events found matching {selected_region}.")
else:
    st.info("No regional exposure data in client profile.")


# =================================================
# REQ 10: TRANSCRIPT UPLOAD FOR CUSTOM ANALYSIS
# =================================================

st.markdown("---")

with st.expander("🔬 Analyze a Different Client (Upload Transcript)", expanded=False):
    uploaded_file = st.file_uploader("Upload Client Transcript (.txt)", type=["txt"], key="transcript_uploader")

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        st.success("✓ Groq API key detected — will use LLM for profile extraction")
    else:
        st.info("ℹ No Groq API key — will use rule-based profile extraction")

    if uploaded_file is not None:
        transcript_text = uploaded_file.read().decode("utf-8")
        temp_path = os.path.join(base_dir, "data", "transcripts", "temp_upload.txt")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        st.success(f"✓ Transcript uploaded ({len(transcript_text)} characters)")

        if st.button("Analyze Risk Exposure", type="primary"):
            with st.spinner("Running risk matching engine..."):
                cmd = ["python", "client_risk_matcher.py", "--transcript", temp_path]
                if groq_key:
                    cmd.extend(["--groq-key", groq_key])
                result = subprocess.run(cmd, cwd=base_dir, capture_output=True, text=True)
                if result.returncode == 0:
                    st.success("✓ Analysis complete — refresh the page to see updated results.")
                    st.rerun()
                else:
                    st.error(f"Analysis failed: {result.stderr[:500]}")

# -------------------------------------------------
# FOOTER
# -------------------------------------------------

st.markdown("---")
st.caption(
    "DRA Risk Intelligence Platform — Signal AI-style taxonomy: "
    "15 Risk Pillars → 70+ Signal Topics → 30+ Event Types. "
    f"Data: {len(raw_events)} LexisNexis events | "
    f"Client: {overview.get('primaryIndustry', 'N/A')} | "
    f"Regions: {', '.join(overview.get('selectedRegions', []))}"
)
