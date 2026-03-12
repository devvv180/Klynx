import json
import os
import subprocess

import streamlit as st

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Client Risk Analysis",
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
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------

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
# MAIN PAGE
# -------------------------------------------------

st.title("Client Risk Analysis")
st.caption("Upload a client transcript to analyze their risk exposure")

base_dir = os.path.dirname(os.path.dirname(__file__))
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
