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


def render_sector_explorer_page():
    st.title("Sector Risk Explorer")
    st.caption("Select a sector to review top 10 risks, geo mapping, and event cards.")

    base_dir = os.path.dirname(__file__)
    output_tag = get_output_tag()

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
        return

    with open(results_path, "r") as f:
        data = json.load(f)

    if len(data) == 0:
        st.warning("No events found.")
        return

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
        return

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
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Sector Events", int(len(sector_all_df)))
    m2.metric("Avg Severity", f"{float(sector_all_df['severity_score'].mean()):.2f}")
    m3.metric("High Risk Events", int((sector_all_df["severity_score"] >= 0.8).sum()))

    st.subheader(f"Top 10 Risks: {selected_sector}")
    st.dataframe(
        sector_top_df[["headline", "internal_theme", "structural_domain", "severity_score"]].sort_values(
            "severity_score", ascending=False
        ),
        use_container_width=True,
    )

    st.subheader("Sector Risk Map")
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
            height=660,
            margin=dict(l=0, r=0, t=35, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e6edf3",
            hoverlabel=dict(bgcolor="#0f1520", bordercolor="#2a3648", font=dict(color="#e6edf3")),
            title=f"Top 10 Risk Events Mapped: {selected_sector}",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0.0),
        )
        st.plotly_chart(fig_sector, use_container_width=True, key="sector_map")

    st.subheader("Sector Event Cards")
    ranked_df = sector_top_df.sort_values("severity_score", ascending=False).copy()
    for rank, (_, row) in enumerate(ranked_df.iterrows(), start=1):
        score = max(0.0, min(1.0, float(row.get("severity_score", 0.0))))
        risk = severity_label(score)
        raw_event_id = clean_text(row.get("event_id"), "")
        source = urlparse(raw_event_id).netloc or "Unknown source"

        title = html.escape(clean_text(row.get("headline"), "Unknown Event"))
        event_url = html.escape(raw_event_id) if raw_event_id else "#"
        theme = html.escape(clean_text(row.get("internal_theme"), "Unknown"))
        domain = html.escape(clean_text(row.get("structural_domain"), "Unknown"))
        sector = html.escape(clean_text(row.get("sector"), selected_sector))
        source_html = html.escape(source)

        card_html = dedent(
            f"""
<div class="event-card">
  <div class="event-header">
    <div class="event-rank">Sector Priority #{rank}</div>
    <div class="risk-pill {risk_css(score)}">{risk} Risk</div>
  </div>
  <a href="{event_url}" target="_blank" class="event-title">{title}</a>
  <div class="event-grid">
    <div class="meta-chip">
      <div class="meta-label">Sector</div>
      <div class="meta-value">{sector}</div>
    </div>
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


# -------------------------------------------------
# CLIENT RISK ANALYSIS PAGE
# -------------------------------------------------

def render_client_risk_analysis():
    st.title("Client Risk Analysis")
    st.caption("Upload a client transcript to analyze their risk exposure")
    
    base_dir = os.path.dirname(__file__)
    report_path = os.path.join(base_dir, "..", "..", "risk_match_report.json")
    
    # Check if sample report exists
    sample_report_exists = os.path.exists(report_path)
    
    # Show sample results by default
    if sample_report_exists and "uploaded_file" not in st.session_state:
        st.info("📊 Showing sample analysis for Meridian Lifesciences. Upload your own transcript to analyze a different client.")
        
        with open(report_path, "r") as f:
            report = json.load(f)
        
        display_risk_report(report, base_dir)
        
        st.markdown("---")
        st.markdown("### Analyze Your Own Client")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload Client Transcript (.txt)", type=["txt"], key="transcript_uploader")
    
    # Use Groq API key if available
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        st.success("✓ Groq API key detected - will use LLM for profile extraction")
    else:
        st.info("ℹ No Groq API key found - will use rule-based profile extraction")
    
    if uploaded_file is not None:
        st.session_state.uploaded_file = True
        
        # Save uploaded file temporarily
        transcript_text = uploaded_file.read().decode("utf-8")
        temp_transcript_path = os.path.join(base_dir, "data", "transcripts", "temp_upload.txt")
        
        with open(temp_transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        
        st.success(f"✓ Transcript uploaded ({len(transcript_text)} characters)")
        
        # Analyze button
        if st.button("Analyze Risk Exposure", type="primary"):
            with st.spinner("Analyzing client risk exposure..."):
                # Run client_risk_matcher.py
                import subprocess
                
                cmd = ["uv", "run", "python", "client_risk_matcher.py", 
                       "--transcript", temp_transcript_path]
                
                if groq_key:
                    cmd.extend(["--groq-key", groq_key])
                
                result = subprocess.run(
                    cmd,
                    cwd=base_dir,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0 or result.returncode == -1:  # -1 is ok on Windows
                    st.success("✓ Analysis complete!")
                    
                    # Load and display results
                    if os.path.exists(report_path):
                        with open(report_path, "r") as f:
                            report = json.load(f)
                        
                        display_risk_report(report, base_dir)
                    else:
                        st.error("Report file not found. Please try again.")
                else:
                    st.error(f"Analysis failed. Error: {result.stderr}")


def clean_encoding(text: str) -> str:
    """Fix UTF-8 encoding issues in text"""
    if not text:
        return text
    # Fix common encoding issues
    text = text.replace('\xe2\x86\x92', '>')  # arrow
    text = text.replace('\xe2\x80\x94', '-')  # em dash
    text = text.replace('\xe2\x80\x93', '-')  # en dash
    text = text.replace('\xe2\x80\xa2', '-')  # bullet
    text = text.replace('\xe2\x80\x99', "'")  # right single quote
    text = text.replace('\xe2\x80\x9c', '"')  # left double quote
    text = text.replace('\xe2\x80\x9d', '"')  # right double quote
    return text

def display_risk_report(report: dict, base_dir: str):
    """Display the risk analysis report in a clean, executive-friendly format"""
    profile = report.get("client_profile", {})
    top_risks = report.get("top_risks", [])
    
    # Display client profile in metrics
    st.markdown("### Client Overview")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Company", profile.get("company_name", "N/A"))
    with col2:
        st.metric("Sector", profile.get("sector", "N/A").title())
    with col3:
        st.metric("Key Markets", ", ".join(profile.get("geographies_sales", [])[:2]) or "N/A")
    with col4:
        st.metric("Top Risks", len(top_risks))
    
    st.markdown("---")
    
    # Display top risks - EXECUTIVE SUMMARY ONLY
    st.subheader(f"Top {len(top_risks)} Risk Events")
    
    for risk in top_risks:
        # Clean velocity text
        velocity_raw = clean_encoding(risk.get('velocity', ''))
        if 'hours' in velocity_raw.lower() or 'days' in velocity_raw.lower():
            velocity_icon = "🔴"
            velocity_text = "FAST"
        elif 'weeks' in velocity_raw.lower() or 'months' in velocity_raw.lower():
            velocity_icon = "🟡"
            velocity_text = "MEDIUM"
        else:
            velocity_icon = "🟢"
            velocity_text = "SLOW"
        
        # Get event type (changed from driver)
        event_type = clean_encoding(risk.get('event_type', risk.get('driver', 'Unknown Risk')))
        
        # Risk summary card (EXECUTIVE VIEW - NO SCROLLING)
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); 
                    border-left: 4px solid {'#ff5d5d' if risk['aggregate_score'] > 0.5 else '#f9b44d'}; 
                    border-radius: 8px; padding: 20px; margin-bottom: 16px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div style='flex: 1;'>
                    <h3 style='color: #93c5fd; margin: 0 0 8px 0;'>#{risk['rank']} {event_type}</h3>
                    <p style='color: #94a3b8; margin: 0; font-size: 0.9rem;'>{risk['event_count']} related events</p>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 2rem;'>{velocity_icon}</div>
                    <div style='color: #f9b44d; font-size: 0.85rem; font-weight: 600;'>{velocity_text}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Impact pathway - CLEAN, MINIMAL
        if risk.get("impact_pathway"):
            pathway_full = clean_encoding(risk["impact_pathway"])
            if "IMPACT PATHWAY:" in pathway_full:
                pathway_line = pathway_full.split("IMPACT PATHWAY:")[1].split("WATCH INDICATORS:")[0].strip()
                # Simplify: just show the effect, not the full chain
                if '→' in pathway_line or '>' in pathway_line:
                    parts = [p.strip() for p in pathway_line.replace('>', '→').split('→')]
                    # Show: trigger → effect
                    if len(parts) >= 3:
                        trigger = parts[0].split('[')[0].strip()  # Remove geo tags
                        effect = parts[-1].strip()
                        pathway_simple = f"{trigger} → {effect}"
                    else:
                        pathway_simple = pathway_line
                else:
                    pathway_simple = pathway_line
                
                st.markdown(f"""
                <div style='background: rgba(47,129,247,0.1); border-left: 3px solid #2f81f7; 
                            padding: 12px 16px; margin: 0 0 12px 0; border-radius: 4px;'>
                    <strong style='color: #93c5fd; font-size: 0.85rem;'>BUSINESS IMPACT:</strong><br/>
                    <span style='color: #e6edf3; font-size: 0.95rem;'>{pathway_simple}</span>
                </div>
                """, unsafe_allow_html=True)
                
                # Watch indicators - COLLAPSED by default
                if "WATCH INDICATORS:" in pathway_full:
                    indicators_text = pathway_full.split("WATCH INDICATORS:")[1].strip()
                    indicators = [line.strip().lstrip('-').strip() 
                                 for line in indicators_text.split("\n") if line.strip()]
                    
                    with st.expander("📋 What to Monitor", expanded=False):
                        for indicator in indicators[:3]:  # Max 3 indicators
                            if indicator:
                                st.markdown(f"• {indicator}")
    
    st.markdown("---")
    
    # Download buttons
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        json_str = json.dumps(report, indent=2)
        st.download_button(
            label="📥 JSON Report",
            data=json_str,
            file_name="risk_report.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col2:
        md_path = os.path.join(base_dir, "..", "..", "risk_match_report.md")
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            st.download_button(
                label="📥 MD Report",
                data=md_content,
                file_name="risk_report.md",
                mime="text/markdown",
                use_container_width=True
            )


# -------------------------------------------------
# PAGE ROUTER
# -------------------------------------------------

view_mode = st.radio(
    "View",
    options=["Global Risk Monitor", "Sector Risk Explorer", "Client Risk Analysis"],
    horizontal=True,
    key="dashboard_view_mode",
)

if view_mode == "Sector Risk Explorer":
    render_sector_explorer_page()
    st.stop()

if view_mode == "Client Risk Analysis":
    render_client_risk_analysis()
    st.stop()

# -------------------------------------------------
# TITLE
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
# METRICS
# -------------------------------------------------

col1, col2, col3 = st.columns(3)

high_risk = int((df["severity_score"] >= 0.8).sum())
medium_risk = int(((df["severity_score"] >= 0.5) & (df["severity_score"] < 0.8)).sum())
low_risk = int((df["severity_score"] < 0.5).sum())

col1.metric("High Risk Events", high_risk)
col2.metric("Medium Risk Events", medium_risk)
col3.metric("Low Risk Events", low_risk)

# -------------------------------------------------
# SIDEBAR FILTERS
# -------------------------------------------------

st.sidebar.header("Filters")

selected_theme = st.sidebar.multiselect(
    "Business Area",
    sorted(df["internal_theme"].dropna().unique().tolist()),
    default=sorted(df["internal_theme"].dropna().unique().tolist()),
)

filtered_df = df[df["internal_theme"].isin(selected_theme)].copy()

if filtered_df.empty:
    st.warning("No events match selected filters.")
    st.stop()

# -------------------------------------------------
# RISK OVERVIEW
# -------------------------------------------------

st.markdown("---")
st.subheader("Risk Intelligence Overview")

colA, colB = st.columns(2)

avg_severity = float(filtered_df["severity_score"].mean())

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
colA.plotly_chart(fig_gauge, use_container_width=True)

# -------------------------------------------------
# TOP RISK EVENTS
# -------------------------------------------------

top_risk = filtered_df.sort_values("severity_score", ascending=False).head(10)

fig_top = px.bar(
    top_risk,
    x="severity_score",
    y="headline",
    orientation="h",
    color="severity_score",
    color_continuous_scale=[
        [0, "#3ecf8e"],
        [0.5, "#f9b44d"],
        [1, "#ff5d5d"],
    ],
    title="Top 10 Highest Risk Events",
)
fig_top.update_layout(
    yaxis={"categoryorder": "total ascending"},
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#e6edf3",
)
fig_top.update_coloraxes(showscale=False)
colB.plotly_chart(fig_top, use_container_width=True)


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
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e6edf3",
            coloraxis_colorbar=dict(title="Severity"),
            hoverlabel=dict(bgcolor="#0f1520", bordercolor="#2a3648", font=dict(color="#e6edf3")),
            geo=dict(
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
st.dataframe(
    filtered_df[["headline", "internal_theme", "severity_score"]].sort_values(
        "severity_score", ascending=False
    ),
    use_container_width=True,
)

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
