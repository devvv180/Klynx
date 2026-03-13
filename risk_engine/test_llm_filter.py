"""
Quick test of LLM relevance filtering on sample events.
Shows how LLM evaluates relevance vs rule-based scoring.
"""

import json
import os
from llm_relevance_filter import build_client_context, check_event_relevance_llm

def main():
    # Check for LLM setup
    groq_key = os.getenv('GROQ_API_KEY')
    ollama_url = os.getenv('OLLAMA_URL')
    
    if not groq_key and not ollama_url:
        print("Error: No LLM provider configured")
        print("\nFor Groq, set:")
        print("  export GROQ_API_KEY='your-key-here'  # Linux/Mac")
        print("  set GROQ_API_KEY=your-key-here       # Windows CMD")
        print("  $env:GROQ_API_KEY='your-key-here'    # Windows PowerShell")
        print("\nFor Ollama, set:")
        print("  export OLLAMA_URL='http://127.0.0.1:11434'")
        return
    
    # Load client profile
    with open('data/client_data.json', 'r', encoding='utf-8') as f:
        profile = json.load(f)
    
    client_context = build_client_context(profile)
    
    # Load first 10 events
    events = []
    with open('data/merged_lexis_event_frames_similarity_v1.jsonl', 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 10:
                break
            if line.strip():
                events.append(json.loads(line))
    
    print("=" * 100)
    print("LLM RELEVANCE FILTERING TEST")
    print("=" * 100)
    print(f"\nClient: {profile['companyOverview']['primaryIndustry']}")
    print(f"Testing first 10 events from dataset\n")
    print("=" * 100)
    
    relevant_count = 0
    
    for i, event in enumerate(events, 1):
        headline = event.get('headline', '')[:80]
        pillar = event.get('predicted_structural_driver', '')
        
        print(f"\n{i}. {headline}")
        print(f"   Pillar: {pillar}")
        
        # Check relevance with LLM
        is_relevant, confidence, reasoning = check_event_relevance_llm(
            event, client_context
        )
        
        if is_relevant:
            relevant_count += 1
            print(f"   ✅ RELEVANT (confidence: {confidence:.2f})")
            print(f"   Reason: {reasoning}")
        else:
            print(f"   ❌ NOT RELEVANT (confidence: {confidence:.2f})")
            print(f"   Reason: {reasoning}")
    
    print("\n" + "=" * 100)
    print(f"RESULTS: {relevant_count} relevant events out of 10 tested ({relevant_count/10*100:.0f}%)")
    print("=" * 100)
    
    if relevant_count < 3:
        print("\n✅ Good! LLM is being strict and filtering out irrelevant events.")
    elif relevant_count > 7:
        print("\n⚠️  Warning: LLM marked most events as relevant. May need to adjust prompt.")
    else:
        print("\n✅ Reasonable filtering rate. LLM is working as expected.")

if __name__ == '__main__':
    main()
