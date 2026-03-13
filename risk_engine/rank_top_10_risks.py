"""
Rank top 10 risk events for client using LLM.
Takes the 66 pre-filtered events and ranks them by relevance to Meridian Lifesciences.
Stores results in data/top_10_client_risks.json
"""

import json
import os
import time
import urllib.request
import urllib.error

# Hardcoded API key and config
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"
RATE_LIMIT_SECONDS = 4  # Wait 4 seconds between API calls

def call_llm(prompt: str, temperature: float = 0.1, max_tokens: int = 500) -> str:
    """Call Groq LLM API - matches llm_severity.py implementation."""
    endpoint = GROQ_URL.rstrip("/") + "/chat/completions"
    
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    if not GROQ_API_KEY:
        raise ValueError("Missing GROQ_API_KEY")
    
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
    
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read().decode("utf-8")
        
        data = json.loads(body)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"LLM API error: {e.code} {e.reason}\n{error_body}")
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {str(e)}")

def build_client_context(profile: dict) -> str:
    """Build client context for LLM."""
    overview = profile.get('companyOverview', {})
    
    context = f"""Client: Meridian Lifesciences
Industry: {overview.get('primaryIndustry', 'Unknown')} / {overview.get('secondaryIndustry', 'Unknown')}

Key Business Operations:
- Manufacturing: 2 plants in India (Hyderabad, Vizag) - 100% of production capacity
- Sourcing: Critical APIs from China (high concentration, 12-month qualification for alternates)
- Sales: 40% US revenue, 18% Europe, rest domestic India
- Product: Generic medicines manufacturing

Critical Risk Exposures:
1. Regulatory: FDA approval required for 40% of revenue (400 crore at risk)
2. Supply Chain: Single-source China APIs, difficult to substitute
3. Manufacturing: Only 2 plants, no backup capacity, coastal flood risk
4. Financial: High FX exposure (66% export), working capital squeeze
5. Compliance: Recent FDA observations, pending clearance

Key Regions:
- South Asia (India): Manufacturing base, core operations
- East Asia (China): Critical raw material sourcing
- North America (US): 40% revenue, FDA jurisdiction
- Europe: 18% revenue, regulatory compliance"""
    
    return context

def rank_event_relevance(event: dict, client_context: str) -> dict:
    """Use LLM to rank event relevance and explain impact."""
    
    headline = event.get('headline', '')
    summary = event.get('summary', '')[:600]
    domain = event.get('predicted_structural_domain', '')
    pillar = event.get('predicted_structural_driver', '')
    geo_tags = ', '.join(event.get('geo_tags', [])[:5])
    
    prompt = f"""{client_context}

Event to Rank:
Headline: {headline}
Summary: {summary}
Risk Pillar: {pillar}
Domain: {domain}
Geography: {geo_tags}

Task: Rate this event's relevance and risk impact to Meridian Lifesciences on a scale of 0-100.

Consider:
1. Direct impact on operations (manufacturing, supply chain, sales)
2. Regulatory/compliance implications (FDA, EU, India)
3. Financial impact (revenue, costs, FX)
4. Strategic importance (competitive landscape, market access)
5. Urgency and materiality

Respond in JSON format:
{{
  "relevance_score": 0-100,
  "risk_level": "Critical/High/Medium/Low",
  "impact_areas": ["area1", "area2"],
  "business_impact": "1-2 sentence explanation of specific impact to Meridian",
  "action_priority": "Immediate/High/Medium/Low"
}}

Be specific about HOW this affects Meridian's pharma operations."""

    try:
        result_text = call_llm(prompt, temperature=0.1, max_tokens=500)
        
        # Extract JSON
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0].strip()
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0].strip()
        
        result = json.loads(result_text)
        return result
    
    except Exception as e:
        print(f"  ⚠️  Error ranking event: {e}")
        return {
            "relevance_score": 0,
            "risk_level": "Unknown",
            "impact_areas": [],
            "business_impact": f"Error: {str(e)}",
            "action_priority": "Low"
        }

def main():
    base_dir = os.path.dirname(__file__)
    
    # Load client profile
    profile_path = os.path.join(base_dir, 'data', 'client_data.json')
    with open(profile_path, 'r', encoding='utf-8') as f:
        profile = json.load(f)
    
    client_context = build_client_context(profile)
    
    # Load filtered events
    filtered_path = os.path.join(base_dir, 'data', 'llm_filtered_relevant_events.jsonl')
    events = []
    with open(filtered_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    print("=" * 80)
    print("RANKING TOP 10 RISK EVENTS FOR MERIDIAN LIFESCIENCES")
    print("=" * 80)
    print(f"\nClient: {profile['companyOverview']['primaryIndustry']}")
    print(f"Processing {len(events)} pre-filtered events...")
    print(f"Rate limit: {RATE_LIMIT_SECONDS} seconds between API calls")
    print(f"Estimated time: {len(events) * RATE_LIMIT_SECONDS / 60:.1f} minutes\n")
    print("=" * 80)
    
    ranked_events = []
    
    for i, event in enumerate(events, 1):
        headline = event.get('headline', 'Unknown')[:70]
        print(f"\n[{i}/{len(events)}] Ranking: {headline}...")
        
        try:
            ranking = rank_event_relevance(event, client_context)
            
            # Add ranking to event
            event['client_ranking'] = ranking
            ranked_events.append(event)
            
            score = ranking.get('relevance_score', 0)
            risk = ranking.get('risk_level', 'Unknown')
            impact = ranking.get('business_impact', '')[:80]
            
            print(f"  Score: {score}/100 | Risk: {risk}")
            print(f"  Impact: {impact}...")
            
            # Rate limiting
            if i < len(events):  # Don't wait after last event
                print(f"  ⏳ Waiting {RATE_LIMIT_SECONDS} seconds...")
                time.sleep(RATE_LIMIT_SECONDS)
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user. Saving progress...")
            break
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    # Sort by relevance score
    ranked_events.sort(key=lambda x: x.get('client_ranking', {}).get('relevance_score', 0), reverse=True)
    
    # Get top 10
    top_10 = ranked_events[:10]
    
    print("\n" + "=" * 80)
    print(f"TOP 10 RISK EVENTS FOR MERIDIAN")
    print("=" * 80)
    
    for i, event in enumerate(top_10, 1):
        ranking = event.get('client_ranking', {})
        print(f"\n{i}. {event.get('headline', 'Unknown')[:70]}")
        print(f"   Score: {ranking.get('relevance_score', 0)}/100 | Risk: {ranking.get('risk_level', 'Unknown')}")
        print(f"   Impact: {ranking.get('business_impact', 'N/A')[:100]}")
        print(f"   Priority: {ranking.get('action_priority', 'Unknown')}")
    
    # Save top 10
    output_path = os.path.join(base_dir, 'data', 'top_10_client_risks.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(top_10, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print(f"✅ Saved top 10 events to: {output_path}")
    print("=" * 80)
    
    # Also save full ranked list
    full_output_path = os.path.join(base_dir, 'data', 'all_ranked_client_risks.json')
    with open(full_output_path, 'w', encoding='utf-8') as f:
        json.dump(ranked_events, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved all {len(ranked_events)} ranked events to: {full_output_path}")
    print("\nDone!")

if __name__ == '__main__':
    main()
