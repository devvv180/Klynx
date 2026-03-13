import html
import json
import os
from textwrap import dedent
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path to import shared modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from io_paths import get_output_tag, tag_filename

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Sector Risk Explorer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------
# SHARED STYLES
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
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# HELPER FUNCTIONS
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

def build_event_hover_card(row: pd.Series) -> str:
    headline = html.escape(clip_text(row.get("headline", "Unknown event"), 120))
    theme = html.escape(row.get("internal_theme", "Unknown"))
    domain = html.escape(clip_text(row.get("structural_domain", "Unknown"), 65))
    source = html.escape(row.get("event_source", "Unknown source"))
    score = float(row.get("severity_score", 0.0))
    risk = severity_label(score)
    return (
        "<span style='color:#9fb3c8;font-size:11px;letter-spacing:0.4px;'>EVENT SNAPSHOT</span><br>"
        f"<b style='color:#e6edf3;font-size:13px;'>{headline}</b><br>"
        f"<span style='color:#8ca3bd;'>Theme:</span> {theme}<br>"
        f"<span style='color:#8ca3bd;'>Domain:</span> {domain}<br>"
        f"<span style='color:#8ca3bd;'>Severity:</span> <b>{score:.2f}</b> ({risk})<br>"
        f"<span style='color:#8ca3bd;'>Source:</span> {source}"
    )

def add_geo_jitter(events: pd.DataFrame) -> pd.DataFrame:
    import math
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

# -------------------------------------------------
# MAIN PAGE
# -------------------------------------------------

st.title("Sector Risk Explorer")
st.caption("Select a sector to review top 10 risks, geo mapping, and event cards.")

base_dir = os.path.dirname(os.path.dirname(__file__))
output_tag = get_output_tag()

# Check if demo mode is enabled
demo_mode = os.getenv("DEMO_MODE", "true").strip().lower() in {"1", "true", "yes", "y"}

if demo_mode:
    results_path = os.path.join(base_dir, "data", "event_severity_results_demo_curated.json")
    sector_report_path = os.path.join(base_dir, "data", "sector_top_10_risks_demo_curated.json")
    st.caption("🎯 Demo Mode: Showing curated sector-relevant events with realistic theme distributions")
else:
    tagged_results_path = os.path.join(base_dir, "data", tag_filename("event_severity_results.json"))
    default_results_path = os.path.join(base_dir, "data", "event_severity_results.json")
    results_path = tagged_results_path if os.path.exists(tagged_results_path) else default_results_path

    tagged_sector_path = os.path.join(base_dir, "data", tag_filename("sector_top_10_risks.json"))
    default_sector_path = os.path.join(base_dir, "data", "sector_top_10_risks.json")
    sector_report_path = tagged_sector_path if os.path.exists(tagged_sector_path) else default_sector_path

    if output_tag:
        st.caption(f"Dataset tag: {output_tag}")

if not os.path.exists(results_path):
    st.error("Run llm_severity.py first to generate event severity results.")
    st.stop()

with open(results_path, "r") as f:
    data = json.load(f)

if len(data) == 0:
    st.warning("No events found.")
    st.stop()

df = pd.DataFrame(data)
df["severity_score"] = pd.to_numeric(df.get("severity_score"), errors="coerce").fillna(0.0)
if "sector" in df.columns:
    df["sector"] = df["sector"].fillna("Cross-Sector / Multi-Industry")

report_lookup = {}
if os.path.exists(sector_report_path):
    try:
        with open(sector_report_path, "r") as f:
            sector_report = json.load(f)
        for row in sector_report.get("sectors", []):
            report_lookup[row.get("sector")] = row.get("top_risks", [])
    except Exception:
        report_lookup = {}

sectors_from_df = sorted(df["sector"].dropna().unique().tolist()) if "sector" in df.columns else []
sectors_from_report = sorted([s for s in report_lookup.keys() if s])
sector_options = sectors_from_df if sectors_from_df else sectors_from_report

if not sector_options:
    st.error("No sector information found. Re-run llm_severity.py to generate sector outputs.")
    st.stop()

selected_sector = st.selectbox(
    "Select Sector",
    options=sector_options,
    index=0,
    key="sector_page_select",
)

if "sector" in df.columns:
    sector_all_df = df[df["sector"] == selected_sector].copy()
    sector_top_df = sector_all_df.sort_values("severity_score", ascending=False).head(10).copy()
else:
    top_ids = [r.get("event_id") for r in report_lookup.get(selected_sector, []) if r.get("event_id")]
    sector_top_df = df[df["event_id"].isin(top_ids)].copy()
    if top_ids:
        id_order = {event_id: idx for idx, event_id in enumerate(top_ids)}
        sector_top_df["order_rank"] = sector_top_df["event_id"].map(id_order).fillna(10_000)
        sector_top_df = sector_top_df.sort_values("order_rank", ascending=True).drop(columns=["order_rank"])
    sector_all_df = sector_top_df.copy()
    sector_top_df = sector_top_df.head(10)

if sector_top_df.empty:
    st.warning("No events available for selected sector.")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Sector Events", int(len(sector_all_df)))
m2.metric("Avg Severity", f"{float(sector_all_df['severity_score'].mean()):.2f}")
m3.metric("High Risk Events", int((sector_all_df["severity_score"] >= 0.8).sum()))
m4.metric("Medium Risk Events", int((sector_all_df["severity_score"] >= 0.5).sum() - (sector_all_df["severity_score"] >= 0.8).sum()))

# Create tabs for better organization
tab1, tab2, tab3 = st.tabs(["📊 Risk Overview", "🗺️ Geographic Distribution", "📋 Event Details"])

with tab1:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### Top 10 Risks by Severity")
        # Create a horizontal bar chart for top risks
        import plotly.express as px
        top_10_chart_df = sector_top_df.sort_values("severity_score", ascending=True).tail(10).copy()
        top_10_chart_df["headline_short"] = top_10_chart_df["headline"].apply(lambda x: clip_text(x, 60))
        
        fig_bar = px.bar(
            top_10_chart_df,
            y="headline_short",
            x="severity_score",
            orientation="h",
            color="severity_score",
            color_continuous_scale=["#3ecf8e", "#f9b44d", "#ff5d5d"],
            range_color=[0, 1],
            labels={"headline_short": "Event", "severity_score": "Severity Score"},
            height=450
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e6edf3",
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(tickfont=dict(size=10)),
            xaxis=dict(range=[0, 1])
        )
        st.plotly_chart(fig_bar, use_container_width=True, key="top_risks_bar")
    
    with col2:
        st.markdown("#### Sector Risk Exposure Profile")
        
        # Define all standard internal themes (12 total)
        all_standard_themes = [
            "Strategy & Business Model",
            "Governance, Risk & Compliance",
            "Legal/Contracts",
            "Cybersecurity",
            "Procurement & Vendor Management",
            "Operations",
            "Finance/Treasury/FP&A",
            "Business Continuity",
            "Human Resources",
            "Quality & Assurance",
            "Data Governance",
            "Ethics & Conduct"
        ]
        
        # Map existing themes to standard themes
        theme_mapping = {
            "Strategy & Business Model": "Strategy & Business Model",
            "Governance, Risk & Compliance": "Governance, Risk & Compliance",
            "Governance, Risk & Complaiance": "Governance, Risk & Compliance",  # typo fix
            "Cybersecurity": "Cybersecurity",
            "Operations": "Operations",
            "Finance/Treasury/FP&A": "Finance/Treasury/FP&A",
            "Human Resources": "Human Resources"
        }
        
        # Intelligent distribution rules for missing themes based on sector
        theme_distribution_rules = {
            "Legal/Contracts": ["Governance, Risk & Compliance"],  # Derive from GRC
            "Procurement & Vendor Management": ["Operations"],  # Derive from Operations
            "Business Continuity": ["Operations"],  # Derive from Operations
            "Quality & Assurance": ["Operations"],  # Derive from Operations
            "Data Governance": ["Cybersecurity", "Governance, Risk & Compliance"],  # Derive from Cyber + GRC
            "Ethics & Conduct": ["Governance, Risk & Compliance", "Human Resources"]  # Derive from GRC + HR
        }
        
        # Calculate exposure for each standard theme
        theme_scores = {}
        
        for standard_theme in all_standard_themes:
            # Direct match from data
            direct_events = sector_all_df[
                sector_all_df["internal_theme"].map(lambda x: theme_mapping.get(x) == standard_theme)
            ]
            
            if len(direct_events) > 0:
                # Has direct data
                avg_severity = direct_events["severity_score"].mean()
                count = len(direct_events)
            else:
                # Derive from related themes
                if standard_theme in theme_distribution_rules:
                    related_themes = theme_distribution_rules[standard_theme]
                    related_events = sector_all_df[
                        sector_all_df["internal_theme"].isin(related_themes)
                    ]
                    if len(related_events) > 0:
                        # Use 60% of related theme's severity (derived/indirect)
                        avg_severity = related_events["severity_score"].mean() * 0.6
                        count = len(related_events) * 0.3  # Lower weight for derived
                    else:
                        avg_severity = 0.3  # Baseline
                        count = 1
                else:
                    avg_severity = 0.3  # Baseline
                    count = 1
            
            # Calculate exposure score
            max_count = len(sector_all_df)
            exposure_score = (
                (avg_severity * 0.7) +  # 70% weight on severity
                ((count / max_count) * 0.3)  # 30% weight on frequency
            ) * 100
            
            theme_scores[standard_theme] = exposure_score
        
        # Create radar chart with all 12 themes
        fig_radar = go.Figure()
        
        fig_radar.add_trace(go.Scatterpolar(
            r=[theme_scores[theme] for theme in all_standard_themes],
            theta=all_standard_themes,
            fill='toself',
            fillcolor='rgba(47, 129, 247, 0.3)',
            line=dict(color='#2f81f7', width=2),
            marker=dict(size=8, color='#2f81f7'),
            name=selected_sector,
            hovertemplate='<b>%{theta}</b><br>Exposure: %{r:.1f}<br><extra></extra>'
        ))
        
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    gridcolor="#2a3648",
                    tickfont=dict(size=9, color="#94a3b8")
                ),
                angularaxis=dict(
                    gridcolor="#2a3648",
                    tickfont=dict(size=9, color="#e6edf3")
                ),
                bgcolor="rgba(0,0,0,0)"
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e6edf3",
            margin=dict(l=80, r=80, t=30, b=30),
            height=450,
            showlegend=False
        )
        
        st.plotly_chart(fig_radar, use_container_width=True, key="theme_radar")
        st.caption("Exposure score: severity (70%) + event frequency (30%). Derived themes estimated from related categories.")
    
    # Severity distribution histogram
    st.markdown("#### Severity Score Distribution")
    fig_hist = px.histogram(
        sector_all_df,
        x="severity_score",
        nbins=20,
        color_discrete_sequence=["#2f81f7"],
        labels={"severity_score": "Severity Score", "count": "Number of Events"},
        height=300
    )
    fig_hist.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e6edf3",
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(range=[0, 1]),
        showlegend=False
    )
    st.plotly_chart(fig_hist, use_container_width=True, key="severity_hist")

with tab2:
    st.markdown("#### Geographic Risk Heatmap")
    map_df = sector_top_df.copy()
    map_df["lat"] = pd.to_numeric(map_df.get("lat"), errors="coerce")
    map_df["lon"] = pd.to_numeric(map_df.get("lon"), errors="coerce")
    map_df = map_df.dropna(subset=["lat", "lon"]).copy()

    if map_df.empty:
        st.info("No geo coordinates available for the selected sector's top risks.")
    else:
        map_df["headline"] = map_df["headline"].fillna("Unknown event")
        map_df["internal_theme"] = map_df["internal_theme"].fillna("Unknown")
        map_df["structural_domain"] = map_df["structural_domain"].fillna("Unknown")
        map_df["event_source"] = map_df["event_id"].astype(str).apply(lambda x: urlparse(x).netloc or "Unknown source")
        map_df["hover_card"] = map_df.apply(build_event_hover_card, axis=1)
        map_plot_df = add_geo_jitter(map_df)
        map_plot_df["marker_size"] = 12 + map_plot_df["severity_score"].clip(0, 1) * 24

        fig_sector = go.Figure()
        fig_sector.add_trace(
            go.Densitymapbox(
                lat=map_df["lat"],
                lon=map_df["lon"],
                z=map_df["severity_score"],
                radius=36,
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
        fig_sector.add_trace(
            go.Scattermapbox(
                lat=map_plot_df["plot_lat"],
                lon=map_plot_df["plot_lon"],
                mode="markers",
                marker=dict(
                    size=map_plot_df["marker_size"],
                    color=map_plot_df["severity_score"],
                    colorscale=[
                        [0, "#3ecf8e"],
                        [0.5, "#f9b44d"],
                        [1, "#ff5d5d"],
                    ],
                    cmin=0,
                    cmax=1,
                    opacity=0.92,
                    showscale=False,
                ),
                customdata=map_plot_df[["hover_card"]].values,
                hovertemplate="%{customdata[0]}<extra></extra>",
                name="Top Risk Events",
            )
        )
        fig_sector.update_layout(
            mapbox=dict(style="carto-darkmatter", center=dict(lat=20, lon=0), zoom=1),
            height=600,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e6edf3",
            hoverlabel=dict(bgcolor="#0f1520", bordercolor="#2a3648", font=dict(color="#e6edf3")),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0.0),
        )
        st.plotly_chart(fig_sector, use_container_width=True, key="sector_map")

with tab3:
    st.markdown("#### Top 10 Risk Events")
    
    # Add search/filter options
    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input("🔍 Search events", placeholder="Search by headline, theme, or domain...", key="event_search")
    with col2:
        severity_filter = st.selectbox("Filter by Risk Level", ["All", "High (≥0.8)", "Medium (0.5-0.8)", "Low (<0.5)"], key="severity_filter")
    
    # Filter events based on search and severity
    filtered_df = sector_top_df.copy()
    if search_term:
        mask = (
            filtered_df["headline"].str.contains(search_term, case=False, na=False) |
            filtered_df["internal_theme"].str.contains(search_term, case=False, na=False) |
            filtered_df["structural_domain"].str.contains(search_term, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    if severity_filter == "High (≥0.8)":
        filtered_df = filtered_df[filtered_df["severity_score"] >= 0.8]
    elif severity_filter == "Medium (0.5-0.8)":
        filtered_df = filtered_df[(filtered_df["severity_score"] >= 0.5) & (filtered_df["severity_score"] < 0.8)]
    elif severity_filter == "Low (<0.5)":
        filtered_df = filtered_df[filtered_df["severity_score"] < 0.5]
    
    ranked_df = filtered_df.sort_values("severity_score", ascending=False).copy()
    
    if ranked_df.empty:
        st.info("No events match your search criteria.")
    else:
        # Use expander for each event to reduce scrolling
        for rank, (_, row) in enumerate(ranked_df.iterrows(), start=1):
            score = max(0.0, min(1.0, float(row.get("severity_score", 0.0))))
            risk = severity_label(score)
            raw_event_id = clean_text(row.get("event_id"), "")
            source = urlparse(raw_event_id).netloc or "Unknown source"

            title = clean_text(row.get("headline"), "Unknown Event")
            theme = clean_text(row.get("internal_theme"), "Unknown")
            domain = clean_text(row.get("structural_domain"), "Unknown")
            
            # Create compact expander title
            risk_emoji = "🔴" if score >= 0.8 else "🟡" if score >= 0.5 else "🟢"
            expander_title = f"{risk_emoji} #{rank} | {clip_text(title, 80)} | Severity: {score:.2f}"
            
            with st.expander(expander_title, expanded=(rank <= 3)):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**Full Headline:** {title}")
                    if raw_event_id and raw_event_id.startswith("http"):
                        st.markdown(f"[🔗 View Source]({raw_event_id})")
                with col2:
                    st.markdown(f"**Theme:** {theme}")
                    st.markdown(f"**Domain:** {domain}")
                with col3:
                    st.markdown(f"**Sector:** {selected_sector}")
                    st.markdown(f"**Source:** {source}")
                
                # Severity progress bar
                st.progress(score, text=f"{risk} Risk - {score:.2f}")

