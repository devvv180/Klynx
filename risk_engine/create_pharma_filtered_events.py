"""
Create filtered events file for pharma client using keyword-based filtering.
This is a fallback when LLM API is not available.
"""

import json
import os

# Pharma-relevant keywords
PHARMA_KEYWORDS = {
    # Drug/pharma specific
    "fda", "drug", "pharmaceutical", "pharma", "medicine", "therapy", "treatment",
    "clinical trial", "approval", "enhertu", "genentech", "astrazeneca", "daiichi sankyo",
    "breast cancer", "gene therapy", "biopharma", "biotech", "biologic",
    
    # Regulatory
    "regulatory", "compliance", "quality", "gmp", "inspection",
    
    # Manufacturing/supply chain in pharma regions
    "india manufacturing", "china api", "china sourcing", "guangdong",
    "hyderabad", "vizag", "andhra pradesh",
    
    # Generic medicines
    "generic", "biosimilar",
}

def is_pharma_relevant(event: dict) -> bool:
    """Check if event is relevant to pharma business."""
    
    # Get text fields
    headline = str(event.get('headline', '')).lower()
    summary = str(event.get('summary', '')).lower()
    domain = str(event.get('predicted_structural_domain', '')).lower()
    
    # Check for pharma keywords
    text = f"{headline} {summary} {domain}"
    
    for keyword in PHARMA_KEYWORDS:
        if keyword in text:
            return True
    
    # Check if it's regulatory + US/EU/India (pharma markets)
    if 'regulatory' in domain or 'policy' in domain:
        geo_tags = [str(g).lower() for g in event.get('geo_tags', [])]
        if any(g in ['united states', 'us', 'usa', 'europe', 'india', 'china'] for g in geo_tags):
            # Only if also mentions health/medical
            if any(word in text for word in ['health', 'medical', 'patient', 'hospital', 'disease']):
                return True
    
    return False

def main():
    base_dir = os.path.dirname(__file__)
    input_path = os.path.join(base_dir, 'data', 'merged_lexis_event_frames_similarity_v1.jsonl')
    output_path = os.path.join(base_dir, 'data', 'llm_filtered_relevant_events.jsonl')
    
    print("Loading events...")
    events = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    print(f"Filtering {len(events)} events for pharma relevance...")
    
    relevant_events = []
    for event in events:
        if is_pharma_relevant(event):
            # Add marker that this was filtered
            event['llm_relevance'] = {
                'is_relevant': True,
                'confidence': 0.85,
                'reasoning': 'Keyword-based pharma relevance filter'
            }
            relevant_events.append(event)
            print(f"✓ {event.get('headline', '')[:80]}")
    
    print(f"\nFiltered to {len(relevant_events)} relevant events from {len(events)} total")
    
    # Save
    with open(output_path, 'w', encoding='utf-8') as f:
        for event in relevant_events:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    
    print(f"Saved to {output_path}")

if __name__ == '__main__':
    main()
