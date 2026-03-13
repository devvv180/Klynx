"""
LLM-based relevance filter for client risk matching.
Uses existing LLM setup (Groq/Ollama) to determine if events are truly relevant to client business.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Tuple, List, Dict

# Use same LLM config as llm_severity.py
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
GROQ_URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:70b")

def call_llm(prompt: str, temperature: float = 0.1, max_tokens: int = 300) -> str:
    """Call LLM using OpenAI-compatible API (Groq or Ollama)."""
    
    if LLM_PROVIDER == "groq":
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set")
        url = f"{GROQ_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        model = GROQ_MODEL
    else:  # ollama
        url = f"{OLLAMA_URL}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        model = OLLAMA_MODEL
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"LLM API error: {e.code} {e.reason}\n{error_body}")
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {str(e)}")

def load_client_profile(profile_path: str) -> dict:
    """Load client profile from JSON."""
    with open(profile_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_client_context(profile: dict) -> str:
    """Build a concise client context string for LLM."""
    overview = profile.get('companyOverview', {})
    
    context = f"""Client Profile:
- Industry: {overview.get('primaryIndustry', 'Unknown')} / {overview.get('secondaryIndustry', 'Unknown')}
- Key Regions: {', '.join(overview.get('selectedRegions', []))}
- Business Model: """
    
    # Add regional exposure details
    regional = overview.get('regionalExposure', {})
    for region, details in regional.items():
        channels = details.get('channels', [])
        importance = details.get('importance', '')
        context += f"\n  • {region}: {', '.join(channels)} ({importance})"
    
    # Add top exposures
    context += "\n\nTop Risk Exposures:"
    if 'supplyChainExposure' in profile:
        context += "\n- Supply Chain: High concentration in China sourcing, India manufacturing"
    if 'regulatoryExposure' in profile:
        context += "\n- Regulatory: FDA/EU pharma regulations, licensing dependency"
    if 'financialExposure' in profile:
        context += "\n- Financial: High FX exposure, working capital constraints"
    
    return context

def check_event_relevance_llm(event: dict, client_context: str) -> Tuple[bool, float, str]:
    """
    Use LLM to determine if event is relevant to client.
    Returns: (is_relevant, confidence_score, reasoning)
    """
    
    headline = event.get('headline', '')
    summary = event.get('summary', '')[:500]  # Limit summary length
    domain = event.get('predicted_structural_domain', '')
    pillar = event.get('predicted_structural_driver', '')
    geo_tags = ', '.join(event.get('geo_tags', [])[:5])
    
    prompt = f"""{client_context}

Event to Evaluate:
- Headline: {headline}
- Summary: {summary}
- Risk Pillar: {pillar}
- Domain: {domain}
- Geography: {geo_tags}

Question: Is this event DIRECTLY relevant to the client's business operations, supply chain, regulatory environment, or financial performance?

Consider:
1. Does it affect their industry (pharmaceuticals/life sciences)?
2. Does it impact their key regions (manufacturing, sourcing, sales)?
3. Does it relate to their specific risk exposures (FDA regulations, China sourcing, India manufacturing)?
4. Would this event materially affect their business decisions or risk profile?

Respond in JSON format:
{{
  "is_relevant": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation (max 100 words)"
}}

Be STRICT - only mark as relevant if there's a clear, direct connection to the client's business."""

    try:
        result_text = call_llm(prompt, temperature=0.1, max_tokens=300)
        
        # Extract JSON from response (handle markdown code blocks)
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0].strip()
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0].strip()
        
        result = json.loads(result_text)
        
        return (
            result.get('is_relevant', False),
            float(result.get('confidence', 0.0)),
            result.get('reasoning', '')
        )
    
    except Exception as e:
        print(f"Error checking relevance for event {event.get('event_id', 'unknown')}: {e}")
        return (False, 0.0, f"Error: {str(e)}")

def filter_events_with_llm(events: List[dict], profile: dict, 
                           batch_size: int = 10) -> List[dict]:
    """
    Filter events using LLM relevance checking.
    
    Args:
        events: List of event dictionaries
        profile: Client profile dictionary
        batch_size: Process this many events at a time (for progress tracking)
    
    Returns:
        List of relevant events with added 'llm_relevance' field
    """
    
    client_context = build_client_context(profile)
    
    relevant_events = []
    total = len(events)
    
    print(f"Filtering {total} events using LLM relevance checking...")
    print(f"Client: {profile.get('companyOverview', {}).get('primaryIndustry', 'Unknown')}")
    print("=" * 80)
    
    for i, event in enumerate(events, 1):
        is_relevant, confidence, reasoning = check_event_relevance_llm(
            event, client_context
        )
        
        if is_relevant:
            event['llm_relevance'] = {
                'is_relevant': True,
                'confidence': confidence,
                'reasoning': reasoning
            }
            relevant_events.append(event)
            print(f"✓ [{i}/{total}] RELEVANT ({confidence:.2f}): {event.get('headline', '')[:70]}...")
            print(f"  Reason: {reasoning[:100]}...")
        else:
            if i % 10 == 0:
                print(f"  [{i}/{total}] Filtered {i - len(relevant_events)} events so far...")
    
    print("=" * 80)
    print(f"Results: {len(relevant_events)} relevant events from {total} total ({len(relevant_events)/total*100:.1f}%)")
    
    return relevant_events

def main():
    """Main function to run LLM-based filtering."""
    import sys
    
    # Check for LLM provider
    if LLM_PROVIDER == "groq" and not GROQ_API_KEY:
        print("Error: GROQ_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export GROQ_API_KEY='your-key-here'  # Linux/Mac")
        print("  set GROQ_API_KEY=your-key-here       # Windows CMD")
        print("  $env:GROQ_API_KEY='your-key-here'    # Windows PowerShell")
        sys.exit(1)
    
    # Load data
    base_dir = os.path.dirname(__file__)
    profile_path = os.path.join(base_dir, 'data', 'client_data.json')
    events_path = os.path.join(base_dir, 'data', 'merged_lexis_event_frames_similarity_v1.jsonl')
    output_path = os.path.join(base_dir, 'data', 'llm_filtered_relevant_events.jsonl')
    
    print("Loading client profile...")
    profile = load_client_profile(profile_path)
    
    print("Loading events...")
    events = []
    with open(events_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    # Filter events
    relevant_events = filter_events_with_llm(events, profile)
    
    # Save results
    print(f"\nSaving {len(relevant_events)} relevant events to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        for event in relevant_events:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    
    print("Done!")

if __name__ == '__main__':
    main()
