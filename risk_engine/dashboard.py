import html
import json
import math
import os
from textwrap import dedent
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from io_paths import get_output_tag, tag_filename

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Global Risk Monitor",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------
# STYLE
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

html, body, [class*="css"] {
    font-family: 'Manrope', sans-serif;
}

.stApp {
    background: radial-gradient(900px 420px at 90% -10%, rgba(47,129,247,0.15), rgba(14,17,23,0) 60%),
                radial-gradient(900px 520px at -10% 110%, rgba(62,207,142,0.08), rgba(14,17,23,0) 60%),
                var(--bg);
    color: var(--text);
}

h1, h2, h3, h4 {
    color: var(--text);
    letter-spacing: 0.1px;
}

.block-container {
    padding-top: 1.15rem;
}

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

.event-title:hover {
    color: #93c5fd;
}

.event-grid {
    margin-top: 10px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
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

.severity-fill {
    height: 100%;
    border-radius: 99px;
}

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

[data-testid="stSidebar"] {
    background-color: #0f1520;
    border-right: 1px solid #1f2a39;
}

.filter-panel {
    background: linear-gradient(180deg, rgba(22,31,42,0.96) 0%, rgba(15,21,32,0.96) 100%);
    border: 1px solid #263246;
    border-radius: 12px;
    padding: 10px 12px;
    margin-bottom: 10px;
}

.filter-title {
    color: #dbeafe;
    font-size: 0.90rem;
    font-weight: 700;
    margin-bottom: 2px;
}

.filter-sub {
    color: #9fb3c8;
    font-size: 0.75rem;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}

[data-testid="stSidebar"] label {
    color: #c9d8eb !important;
    font-weight: 600 !important;
}

[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background-color: #101824 !important;
    border: 1px solid #2a3a4f !important;
}

.kpi-card {
    background: linear-gradient(165deg, #1a2431 0%, #121a24 100%);
    border: 1px solid #2a3648;
    border-radius: 12px;
    padding: 14px 14px 12px 14px;
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.24);
    margin-bottom: 8px;
}

.kpi-label {
    color: #9fb3c8;
    font-size: 0.73rem;
    text-transform: uppercase;
    letter-spacing: 0.45px;
    margin-bottom: 6px;
}

.kpi-value {
    color: #e6edf3;
    font-size: 1.55rem;
    line-height: 1.1;
    font-weight: 800;
}

.kpi-sub {
    color: #9fb3c8;
    font-size: 0.78rem;
    margin-top: 6px;
}

.kpi-accent-high { border-left: 4px solid #ff5d5d; }
.kpi-accent-med { border-left: 4px solid #f9b44d; }
.kpi-accent-low { border-left: 4px solid #3ecf8e; }
.kpi-accent-main { border-left: 4px solid #2f81f7; }

.feed-board {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.feed-row {
    display: grid;
    grid-template-columns: 46px 1fr auto;
    gap: 12px;
    align-items: start;
    background: linear-gradient(165deg, #1a2431 0%, #131b27 100%);
    border: 1px solid #2a3648;
    border-radius: 12px;
    padding: 12px 12px 10px 12px;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.22);
}

.feed-rank {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #0f1724;
    border: 1px solid #2a3648;
    color: #9fb3c8;
    font-size: 0.78rem;
    font-weight: 800;
}

.feed-main {
    min-width: 0;
}

.feed-title {
    color: #e6edf3;
    text-decoration: none;
    font-size: 1.00rem;
    font-weight: 700;
    line-height: 1.35;
}

.feed-title:hover {
    color: #93c5fd;
}

.feed-meta {
    margin-top: 6px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.feed-chip {
    background: #0f1724;
    border: 1px solid #27354a;
    color: #cfe0f5;
    border-radius: 999px;
    padding: 3px 9px;
    font-size: 0.72rem;
    letter-spacing: 0.2px;
}

.feed-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 6px;
    min-width: 70px;
}

.feed-score {
    color: #dbeafe;
    font-weight: 800;
    font-size: 0.92rem;
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
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def build_latest_event_feed_row(row: pd.Series, rank: int) -> str:
    score = max(0.0, min(1.0, float(row.get("severity_score", 0.0))))
    risk = severity_label(score)
    risk_class = risk_css(score)

    raw_event_id = clean_text(row.get("event_id"), "")
    event_url = html.escape(raw_event_id) if raw_event_id else "#"

    title = html.escape(clean_text(row.get("headline"), "Unknown Event"))
    theme = html.escape(clean_text(row.get("internal_theme"), "Unknown"))
    domain = html.escape(clean_text(row.get("structural_domain"), "Unknown"))
    location = html.escape(clean_text(row.get("geography"), "Unknown"))
    source = html.escape(urlparse(raw_event_id).netloc or "Unknown source")

    return dedent(
        f"""
<div class="feed-row">
  <div class="feed-rank">{rank:02d}</div>
  <div class="feed-main">
    <a href="{event_url}" target="_blank" class="feed-title">{title}</a>
    <div class="feed-meta">
      <span class="feed-chip">Theme: {theme}</span>
      <span class="feed-chip">Domain: {domain}</span>
      <span class="feed-chip">Location: {location}</span>
      <span class="feed-chip">Source: {source}</span>
    </div>
  </div>
  <div class="feed-right">
    <div class="risk-pill {risk_class}">{risk}</div>
    <div class="feed-score">{score:.2f}</div>
  </div>
</div>
        """
    ).strip()


def build_event_hover_card(row: pd.Series) -> str:
    headline = html.escape(clip_text(row.get("headline", "Unknown event"), 120))
    theme = html.escape(clean_text(row.get("internal_theme"), "Unknown"))
    geography = html.escape(clean_text(row.get("geography"), "Unknown"))
    score = float(row.get("severity_score", 0.0))
    risk = severity_label(score)
    return (
        "<span style='color:#9fb3c8;font-size:11px;letter-spacing:0.45px;'>EVENT RISK CARD</span><br>"
        f"<b style='color:#e6edf3;font-size:13px;line-height:1.35;'>{headline}</b><br>"
        f"<span style='color:#8ca3bd;'>Location:</span> {geography}<br>"
        f"<span style='color:#8ca3bd;'>Internal Theme:</span> <b style='color:#d8e7fb;'>{theme}</b><br>"
        f"<span style='color:#8ca3bd;'>Severity:</span> <b style='color:#ffd7d7;'>{score:.2f}</b> ({risk})<br>"
    )


def build_cluster_hover_card(row: pd.Series) -> str:
    headline = html.escape(clip_text(row.get("top_headline", "Unknown event"), 120))
    theme = html.escape(row.get("top_theme", "Unknown"))
    domain = html.escape(clip_text(row.get("top_domain", "Unknown"), 65))
    source = html.escape(row.get("top_source", "Unknown source"))
    return (
        "<span style='color:#9fb3c8;font-size:11px;letter-spacing:0.4px;'>CLUSTER SNAPSHOT</span><br>"
        f"<b style='color:#e6edf3;'>Events in cluster:</b> {int(row.get('event_count', 0))}<br>"
        f"<b style='color:#e6edf3;'>Avg severity:</b> {float(row.get('avg_severity', 0.0)):.2f}<br>"
        "<span style='color:#9fb3c8;'>Top event:</span><br>"
        f"<b style='color:#e6edf3;font-size:13px;'>{headline}</b><br>"
        f"<span style='color:#8ca3bd;'>Theme:</span> {theme}<br>"
        f"<span style='color:#8ca3bd;'>Domain:</span> {domain}<br>"
        f"<span style='color:#8ca3bd;'>Severity:</span> {float(row.get('top_severity', 0.0)):.2f}<br>"
        f"<span style='color:#8ca3bd;'>Source:</span> {source}"
    )


def add_geo_jitter(events: pd.DataFrame) -> pd.DataFrame:
    jittered = events.copy()
    jittered["coord_rank"] = jittered.groupby(["lat", "lon"]).cumcount()
    jittered["coord_total"] = jittered.groupby(["lat", "lon"])["event_id"].transform("count")

    plot_lat = []
    plot_lon = []
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


def clean_text(value, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return fallback
    return text


COUNTRY_ALIASES = {
    "united states": "United States",
    "usa": "United States",
    "u.s.": "United States",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "russia": "Russia",
    "iran": "Iran",
    "china": "China",
    "india": "India",
    "germany": "Germany",
    "france": "France",
    "japan": "Japan",
    "south korea": "South Korea",
    "north korea": "North Korea",
    "israel": "Israel",
    "turkey": "Turkey",
    "saudi arabia": "Saudi Arabia",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "australia": "Australia",
    "canada": "Canada",
    "denmark": "Denmark",
    "switzerland": "Switzerland",
    "italy": "Italy",
    "spain": "Spain",
    "malaysia": "Malaysia",
    "nigeria": "Nigeria",
    "chile": "Chile",
    "jordan": "Jordan",
    "iraq": "Iraq",
    "yemen": "Yemen",
    "kuwait": "Kuwait",
    "bahrain": "Bahrain",
    "cyprus": "Cyprus",
    "lebanon": "Lebanon",
    "togo": "Togo",
}


def infer_country(geography_value: str) -> str:
    text = clean_text(geography_value, "").lower()
    if not text:
        return "Unknown"

    if text in {"global", "world", "international", "middle east", "oecd"}:
        return "Global / Multi-country"

    for alias, canonical in COUNTRY_ALIASES.items():
        if alias in text:
            return canonical

    parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    if parts:
        last = parts[-1]
        if len(last) > 2 and last not in {"unknown", "virtual", "n/a", "na"}:
            return last.title()

    return "Unknown"


# -------------------------------------------------
# MAIN PAGE - GLOBAL RISK MONITOR
# -------------------------------------------------

st.title("Global Risk Monitor")
st.caption("Real-time global event risk intelligence")

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------

base_dir = os.path.dirname(__file__)
output_tag = get_output_tag()

tagged_results_path = os.path.join(base_dir, "data", tag_filename("event_severity_results.json"))
default_results_path = os.path.join(base_dir, "data", "event_severity_results.json")
results_path = tagged_results_path if os.path.exists(tagged_results_path) else default_results_path

tagged_geo_path = os.path.join(base_dir, "data", tag_filename("event_severity_with_geo.json"))
default_geo_path = os.path.join(base_dir, "data", "event_severity_with_geo.json")
geo_candidates = []
for candidate in [results_path, tagged_geo_path, default_geo_path]:
    if candidate not in geo_candidates:
        geo_candidates.append(candidate)

if output_tag:
    st.caption(f"Dataset tag: {output_tag}")

if not os.path.exists(results_path):
    st.error("Run llm_severity.py first to generate results.")
    st.stop()

with open(results_path, "r") as f:
    data = json.load(f)

if len(data) == 0:
    st.warning("No events found.")
    st.stop()

df = pd.DataFrame(data)

# -------------------------------------------------
# SIDEBAR FILTERS
# -------------------------------------------------

st.sidebar.markdown(
    """
    <div class="filter-panel">
      <div class="filter-title">Risk Filters</div>
      <div class="filter-sub">Business Area</div>
    </div>
    """,
    unsafe_allow_html=True,
)

theme_options = sorted(df["internal_theme"].dropna().unique().tolist())

selected_theme = st.sidebar.multiselect(
    "Business Area (Internal Theme)",
    theme_options,
    default=theme_options,
)

filtered_df = df[df["internal_theme"].isin(selected_theme)].copy()

st.sidebar.caption(
    f"Selected: {len(selected_theme)}/{len(theme_options)} themes"
)

if filtered_df.empty:
    st.warning("No events match selected filters.")
    st.stop()

# -------------------------------------------------
# EXECUTIVE KPI OVERVIEW
# -------------------------------------------------

total_events = int(len(filtered_df))
high_risk = int((filtered_df["severity_score"] >= 0.8).sum())
medium_risk = int(((filtered_df["severity_score"] >= 0.5) & (filtered_df["severity_score"] < 0.8)).sum())
low_risk = int((filtered_df["severity_score"] < 0.5).sum())
avg_severity = float(filtered_df["severity_score"].mean())
high_share = (high_risk / total_events * 100.0) if total_events else 0.0

st.markdown("### Executive Risk Snapshot")
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(
        f"""
        <div class="kpi-card kpi-accent-main">
          <div class="kpi-label">Total Events</div>
          <div class="kpi-value">{total_events}</div>
          <div class="kpi-sub">Active in current filter scope</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        f"""
        <div class="kpi-card kpi-accent-high">
          <div class="kpi-label">High Risk Events</div>
          <div class="kpi-value">{high_risk}</div>
          <div class="kpi-sub">{high_share:.1f}% of filtered portfolio</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        f"""
        <div class="kpi-card kpi-accent-med">
          <div class="kpi-label">Medium Risk Events</div>
          <div class="kpi-value">{medium_risk}</div>
          <div class="kpi-sub">Watchlist exposure</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        f"""
        <div class="kpi-card kpi-accent-low">
          <div class="kpi-label">Low Risk Events</div>
          <div class="kpi-value">{low_risk}</div>
          <div class="kpi-sub">Background baseline activity</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------------------------
# RISK OVERVIEW
# -------------------------------------------------

st.markdown("---")
st.subheader("Risk Intelligence Overview")

fig_gauge = go.Figure(
    go.Indicator(
        mode="gauge+number",
        value=avg_severity,
        title={"text": "Average Global Risk Severity"},
        gauge={
            "axis": {"range": [0, 1]},
            "bar": {"color": "#2f81f7"},
            "steps": [
                {"range": [0, 0.4], "color": "#134e4a"},
                {"range": [0.4, 0.7], "color": "#8a5a13"},
                {"range": [0.7, 1], "color": "#7f1d1d"},
            ],
        },
    )
)
fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#e6edf3")
st.markdown("### Average Global Severity")
g1, g2, g3 = st.columns([0.22, 0.56, 0.22])
with g2:
    st.plotly_chart(fig_gauge, use_container_width=True)

# -------------------------------------------------
# TOP RISK EVENTS
# -------------------------------------------------

ranked_risk = filtered_df.sort_values("severity_score", ascending=False).copy()
top_risk = ranked_risk.head(10).copy()
top_title = "Top 10 Highest Risk Events"

if top_risk["severity_score"].nunique() == 1 and ranked_risk["severity_score"].nunique() > 1:
    # Many datasets have tied top severities. Expand selection to include the next score levels
    # so the bar chart communicates severity spread instead of flat identical bars.
    spread = ranked_risk.drop_duplicates(subset=["severity_score"]).head(10).copy()
    if len(spread) < 10:
        remainder = ranked_risk.loc[~ranked_risk.index.isin(spread.index)].head(10 - len(spread))
        spread = pd.concat([spread, remainder], axis=0)
    top_risk = spread.head(10).copy()
    top_title = "Top Risk Events (Severity Spread View)"
    st.caption("Top severities are tied; chart includes next severity tiers for better comparative insight.")

fig_top = px.bar(
    top_risk,
    x="severity_score",
    y="headline",
    orientation="h",
    color="severity_score",
    color_continuous_scale=[
        [0, "#f9b44d"],
        [1, "#ff5d5d"],
    ],
    range_color=[0.0, 1.0],
    title=top_title,
)
fig_top.update_layout(
    yaxis={"categoryorder": "total ascending"},
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#e6edf3",
)
fig_top.update_coloraxes(showscale=False)
st.markdown("### Top 10 Risk Events")
st.plotly_chart(fig_top, use_container_width=True)

# -------------------------------------------------
# COUNTRY NEWS PULSE
# -------------------------------------------------

st.subheader("Country News Pulse")

country_df = filtered_df.copy()
geo_series = country_df["geography"] if "geography" in country_df.columns else pd.Series([""] * len(country_df), index=country_df.index)
country_df["country"] = geo_series.apply(infer_country)
country_df["severity_score"] = pd.to_numeric(country_df["severity_score"], errors="coerce").fillna(0.0)
country_df = country_df[country_df["country"] != "Unknown"].copy()

if country_df.empty:
    st.info("No country-level geography data available for charting.")
else:
    top_news_by_country = (
        country_df.groupby("country", as_index=False)
        .agg(news_count=("severity_score", "size"))
        .sort_values("news_count", ascending=False)
        .head(15)
    )

    high_severity_by_country = (
        country_df[country_df["severity_score"] >= 0.8]
        .groupby("country", as_index=False)
        .agg(high_severity_count=("severity_score", "size"))
        .sort_values("high_severity_count", ascending=False)
        .head(15)
    )

    fig_country_volume = px.bar(
        top_news_by_country,
        x="country",
        y="news_count",
        color="news_count",
        color_continuous_scale=[
            [0, "#1f6feb"],
            [1, "#58a6ff"],
        ],
        title="Most News by Country (Descending)",
        text="news_count",
    )
    fig_country_volume.update_layout(
        xaxis_title="Country",
        yaxis_title="Number of News Events",
        xaxis={"categoryorder": "total descending"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e6edf3",
    )
    fig_country_volume.update_coloraxes(showscale=False)
    st.plotly_chart(fig_country_volume, use_container_width=True)

    st.markdown("### High-Severity Concentration by Country")
    if high_severity_by_country.empty:
        st.info("No high-severity events (>= 0.80) in the current filter selection.")
    else:
        fig_country_high = px.bar(
            high_severity_by_country,
            x="country",
            y="high_severity_count",
            color="high_severity_count",
            color_continuous_scale=[
                [0, "#f9b44d"],
                [1, "#ff5d5d"],
            ],
            title="High-Severity News by Country (Descending)",
            text="high_severity_count",
        )
        fig_country_high.update_layout(
            xaxis_title="Country",
            yaxis_title="High-Severity Event Count",
            xaxis={"categoryorder": "total descending"},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e6edf3",
        )
        fig_country_high.update_coloraxes(showscale=False)
        st.plotly_chart(fig_country_high, use_container_width=True)


# -------------------------------------------------
# GLOBAL 3D RISK GLOBE
# -------------------------------------------------

st.subheader("Global Risk Globe")

geo_df = None
geo_source_path = None
for candidate in geo_candidates:
    if not os.path.exists(candidate):
        continue
    try:
        candidate_df = pd.read_json(candidate).copy()
    except Exception:
        continue
    if {"lat", "lon"}.issubset(candidate_df.columns):
        geo_df = candidate_df
        geo_source_path = candidate
        break

if geo_df is not None:
    if output_tag:
        st.caption(f"Geo source: {os.path.basename(geo_source_path)}")

    required_cols = ["headline", "internal_theme", "structural_domain", "severity_score"]
    if not set(required_cols).issubset(geo_df.columns):
        geo_df = geo_df.merge(
            df[["event_id", "severity_score", "headline", "structural_domain", "internal_theme"]],
            on="event_id",
            how="left",
        )

    geo_df["severity_score"] = pd.to_numeric(geo_df["severity_score"], errors="coerce")
    geo_df["lat"] = pd.to_numeric(geo_df["lat"], errors="coerce")
    geo_df["lon"] = pd.to_numeric(geo_df["lon"], errors="coerce")

    # Keep map visuals in sync with the active dashboard filters.
    geo_df = geo_df[geo_df["event_id"].isin(filtered_df["event_id"])].copy()

    geo_df = geo_df.dropna(subset=["lat", "lon"]).copy()

    if geo_df.empty:
        st.info("No geo events available for the current filter selection.")
    else:
        geo_df["headline"] = geo_df["headline"].fillna("Unknown event")
        geo_df["internal_theme"] = geo_df["internal_theme"].fillna("Unknown")
        geo_df["structural_domain"] = geo_df["structural_domain"].fillna("Unknown")
        geo_df["event_source"] = geo_df["event_id"].astype(str).apply(
            lambda x: urlparse(x).netloc or "Unknown source"
        )

        geo_df = geo_df.sort_values("severity_score", ascending=False).reset_index(drop=True)
        geo_df["hover_card"] = geo_df.apply(build_event_hover_card, axis=1)

        geo_plot_df = add_geo_jitter(geo_df)
        geo_plot_df["marker_size"] = 10 + geo_plot_df["severity_score"].clip(0, 1) * 22

        fig_globe = px.scatter_geo(
            geo_plot_df,
            lat="plot_lat",
            lon="plot_lon",
            size="marker_size",
            color="severity_score",
            custom_data=["hover_card"],
            projection="orthographic",
            color_continuous_scale=[
                [0, "#3ecf8e"],
                [0.5, "#f9b44d"],
                [1, "#ff5d5d"],
            ],
        )

        fig_globe.update_traces(
            marker=dict(opacity=0.82),
            hovertemplate="%{customdata[0]}<extra></extra>",
        )

        fig_globe.update_layout(
            height=860,
            margin=dict(l=0, r=0, t=20, b=0),
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            font_color="#e6edf3",
            coloraxis_colorbar=dict(title="Severity"),
            hoverlabel=dict(bgcolor="#0f1520", bordercolor="#2a3648", font=dict(color="#e6edf3")),
            geo=dict(
                bgcolor="#0e1117",
                showframe=False,
                showland=True,
                landcolor="#1c1f26",
                showcountries=True,
                countrycolor="#3a4658",
                showocean=True,
                oceancolor="#0b1f33",
                projection_rotation=dict(lon=30, lat=10, roll=0),
            ),
            title="Global Event Risk Distribution (hover reveals one event at a time)",
        )

        st.plotly_chart(fig_globe, use_container_width=True, key="risk_globe")

        # -------------------------------------------------
        # GLOBAL RISK HEATMAP + EVENT MARKERS
        # -------------------------------------------------

        st.subheader("Global Risk Heatmap")

        fig_heatmap = go.Figure()
        fig_heatmap.add_trace(
            go.Densitymapbox(
                lat=geo_df["lat"],
                lon=geo_df["lon"],
                z=geo_df["severity_score"],
                radius=42,
                colorscale=[
                    [0, "#3ecf8e"],
                    [0.5, "#f9b44d"],
                    [1, "#ff5d5d"],
                ],
                hoverinfo="skip",
                name="Risk Density",
                showscale=True,
                colorbar=dict(title="Severity"),
            )
        )
        fig_heatmap.add_trace(
            go.Scattermapbox(
                lat=geo_plot_df["plot_lat"],
                lon=geo_plot_df["plot_lon"],
                mode="markers",
                marker=dict(
                    size=geo_plot_df["marker_size"] * 0.6,
                    color=geo_plot_df["severity_score"],
                    colorscale=[
                        [0, "#3ecf8e"],
                        [0.5, "#f9b44d"],
                        [1, "#ff5d5d"],
                    ],
                    cmin=0,
                    cmax=1,
                    opacity=0.9,
                    showscale=False,
                ),
                customdata=geo_plot_df[["hover_card"]].values,
                hovertemplate="%{customdata[0]}<extra></extra>",
                name="Event Markers",
            )
        )

        fig_heatmap.update_layout(
            mapbox=dict(style="carto-darkmatter", center=dict(lat=20, lon=0), zoom=1),
            height=680,
            margin=dict(l=0, r=0, t=35, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e6edf3",
            hoverlabel=dict(bgcolor="#0f1520", bordercolor="#2a3648", font=dict(color="#e6edf3")),
            title="Global Geopolitical Risk Intensity (hover reveals one event at a time)",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0.0),
        )

        st.plotly_chart(fig_heatmap, use_container_width=True)

        # -------------------------------------------------
        # EVENT CLUSTERS (TOP EVENT PER CLUSTER)
        # -------------------------------------------------

        st.subheader("Event Concentration Clusters")

        cluster_summary = (
            geo_df.groupby(["lat", "lon"], as_index=False)
            .agg(
                event_count=("event_id", "count"),
                avg_severity=("severity_score", "mean"),
            )
        )

        cluster_top = (
            geo_df.sort_values("severity_score", ascending=False)
            .drop_duplicates(subset=["lat", "lon"])
            .rename(
                columns={
                    "headline": "top_headline",
                    "internal_theme": "top_theme",
                    "structural_domain": "top_domain",
                    "severity_score": "top_severity",
                    "event_source": "top_source",
                }
            )[["lat", "lon", "top_headline", "top_theme", "top_domain", "top_severity", "top_source"]]
        )

        cluster_df = cluster_summary.merge(cluster_top, on=["lat", "lon"], how="left")
        cluster_df["cluster_hover"] = cluster_df.apply(build_cluster_hover_card, axis=1)

        fig_cluster = px.scatter_mapbox(
            cluster_df,
            lat="lat",
            lon="lon",
            size="event_count",
            color="avg_severity",
            custom_data=["cluster_hover"],
            zoom=1,
            center=dict(lat=20, lon=0),
            mapbox_style="carto-darkmatter",
            color_continuous_scale="RdYlGn_r",
            title="Geopolitical Event Clusters (hover shows top event in each cluster)",
        )

        fig_cluster.update_traces(hovertemplate="%{customdata[0]}<extra></extra>")
        fig_cluster.update_layout(
            height=650,
            margin=dict(l=0, r=0, t=40, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e6edf3",
            hoverlabel=dict(bgcolor="#0f1520", bordercolor="#2a3648", font=dict(color="#e6edf3")),
        )

        st.plotly_chart(fig_cluster, use_container_width=True)

else:
    st.info("No geo-enabled dataset found with lat/lon columns. Run llm_severity.py to regenerate results.")

# -------------------------------------------------
# EVENT INTELLIGENCE TABLE
# -------------------------------------------------

st.subheader("Latest Risk Events")
st.caption("Dynamic risk feed for rapid analyst review and triage.")

f1, f2, f3 = st.columns([1.9, 1.1, 1.0])
search_query = f1.text_input("Search events", value="", placeholder="Search headline, theme, domain, or location")
risk_levels_selected = f2.multiselect(
    "Risk Level",
    options=["High", "Medium", "Low"],
    default=["High", "Medium", "Low"],
    key="latest_risk_levels",
)
sort_choice = f3.selectbox(
    "Sort By",
    options=["Highest Severity", "Lowest Severity", "Headline A-Z"],
    index=0,
    key="latest_sort_choice",
)

feed_df = filtered_df.copy()
feed_df["risk_level"] = feed_df["severity_score"].apply(severity_label)

if search_query.strip():
    q = search_query.strip().lower()
    search_text = (
        feed_df["headline"].fillna("").astype(str).str.lower() + " "
        + feed_df["internal_theme"].fillna("").astype(str).str.lower() + " "
        + feed_df["structural_domain"].fillna("").astype(str).str.lower() + " "
        + feed_df["geography"].fillna("").astype(str).str.lower()
    )
    feed_df = feed_df[search_text.str.contains(q, na=False)].copy()

if risk_levels_selected:
    feed_df = feed_df[feed_df["risk_level"].isin(risk_levels_selected)].copy()

if sort_choice == "Lowest Severity":
    feed_df = feed_df.sort_values("severity_score", ascending=True)
elif sort_choice == "Headline A-Z":
    feed_df = feed_df.sort_values("headline", ascending=True)
else:
    feed_df = feed_df.sort_values("severity_score", ascending=False)

if feed_df.empty:
    st.info("No events match current feed filters.")
else:
    max_rows = min(25, len(feed_df))
    rows_to_show = st.slider(
        "Rows to display",
        min_value=5,
        max_value=max(5, max_rows),
        value=min(12, max_rows),
        step=1,
        key="latest_rows_to_show",
    )
    view_df = feed_df.head(rows_to_show).copy()
    st.caption(f"Showing {len(view_df)} of {len(feed_df)} matching events")

    st.markdown('<div class="feed-board">', unsafe_allow_html=True)
    for idx, (_, row) in enumerate(view_df.iterrows(), start=1):
        st.markdown(build_latest_event_feed_row(row, idx), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# EVENT CARDS
# -------------------------------------------------

st.subheader("Event Risk Cards")

card_df = filtered_df.sort_values("severity_score", ascending=False).copy()
cards_per_page = st.selectbox(
    "Cards per page",
    options=[8, 12, 16, 24],
    index=1,
    key="cards_per_page",
)

total_cards = len(card_df)
total_pages = max(1, math.ceil(total_cards / cards_per_page))
page = st.number_input(
    "Page",
    min_value=1,
    max_value=total_pages,
    value=1,
    step=1,
    key="cards_page",
)

start_idx = (int(page) - 1) * cards_per_page
end_idx = min(start_idx + cards_per_page, total_cards)
page_df = card_df.iloc[start_idx:end_idx].copy()

st.caption(f"Showing events {start_idx + 1}-{end_idx} of {total_cards}")

for offset, (_, row) in enumerate(page_df.iterrows(), start=1):
    score = float(row["severity_score"])
    score = max(0.0, min(1.0, score))
    risk = severity_label(score)

    raw_event_id = clean_text(row.get("event_id"), "")
    source = urlparse(raw_event_id).netloc or "Unknown source"

    title = html.escape(clean_text(row.get("headline"), "Unknown Event"))
    event_url = html.escape(raw_event_id) if raw_event_id else "#"
    theme = html.escape(clean_text(row.get("internal_theme"), "Unknown"))
    domain = html.escape(clean_text(row.get("structural_domain"), "Unknown"))
    source_html = html.escape(source)
    rank = start_idx + offset

    card_html = dedent(
        f"""
<div class="event-card">
  <div class="event-header">
    <div class="event-rank">Priority #{rank}</div>
    <div class="risk-pill {risk_css(score)}">{risk} Risk</div>
  </div>
  <a href="{event_url}" target="_blank" class="event-title">{title}</a>
  <div class="event-grid">
    <div class="meta-chip">
      <div class="meta-label">Business Area</div>
      <div class="meta-value">{theme}</div>
    </div>
    <div class="meta-chip">
      <div class="meta-label">Structural Domain</div>
      <div class="meta-value">{domain}</div>
    </div>
    <div class="meta-chip">
      <div class="meta-label">Source</div>
      <div class="meta-value">{source_html}</div>
    </div>
    <div class="meta-chip">
      <div class="meta-label">Severity</div>
      <div class="meta-value">{score:.2f}</div>
    </div>
  </div>
  <div class="severity-track">
    <div class="severity-fill" style="width:{score * 100:.1f}%;background:{severity_color(score)};"></div>
  </div>
</div>
        """
    ).strip()

    st.markdown(card_html, unsafe_allow_html=True)
