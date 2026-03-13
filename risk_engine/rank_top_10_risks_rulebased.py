"""
Rank top 10 risk events for Meridian using rule-based scoring.
No API calls needed - works offline.
"""

import json
import os

# Scoring weights
WEIGHTS = {
    'pharma_keywords': 30,
    'regulatory_keywords': 25,
    'region_match': 20,
    'supply_chain_keywords': 15,
    'severity_score': 10,
}

# Pharma-specific keywords (higher scores)
PHARMA_KEYWORDS = {
    'critical': ['fda approval', 'drug approval', 'clinical trial', 'phase iii', 'phase 3', 
                 'regulatory approval', 'generic drug', 'biosimilar', 'api', 'active pharmaceutical'],
    'high': ['fda', 'pharmaceutical', 'pharma', 'medicine', 'therapy', 'treatment', 'drug',
             'biopharma', 'biotech', 'gene therapy', 'oncology', 'cancer drug'],
    'medium': ['health', 'medical', 'patient', 'hospital', 'disease', 'clinical'],
}

# Regulatory keywords
REGULATORY_KEYWORDS = {
    'critical': ['fda inspection', 'regulatory action', 'compliance violation', 'warning letter',
                 'import ban', 'manufacturing ban'],
    'high': ['regulatory', 'compliance', 'inspection', 'gmp', 'quality control', 'approval'],
    'medium': ['policy', 'regulation', 'standard', 'guideline'],
}

# Supply chain keywords
SUPPLY_CHAIN_KEYWORDS = {
    'critical': ['supply disruption', 'shortage', 'manufacturing halt', 'plant closure',
                 'api shortage', 'raw material shortage'],
    'high': ['supply chain', 'manufacturing', 'production', 'sourcing', 'supplier'],
    'medium': ['logistics', 'shipping', 'freight', 'customs'],
}

# Client regions (Meridian operates in these)
CLIENT_REGIONS = {
    'critical': ['india', 'hyderabad', 'vizag', 'andhra pradesh'],  # Manufacturing
    'high': ['china', 'guangdong', 'beijing', 'shanghai'],  # Sourcing
    'medium': ['united states', 'usa', 'us', 'europe', 'eu'],  # Sales markets
}

def score_keywords(text: str, keyword_dict: dict) -> float:
    """Score text based on keyword matches."""
    text_lower = text.lower()
    score = 0.0
    
    for level, keywords in keyword_dict.items():
        for keyword in keywords:
            if keyword in text_lower:
                if level == 'critical':
                    score += 3.0
                elif level == 'high':
                    score += 2.0
                else:
                    score += 1.0
    
    return min(score, 10.0)  # Cap at 10

def score_regions(event: dict) -> float:
    """Score based on geographic relevance."""
    geo_tags = [str(g).lower() for g in event.get('geo_tags', [])]
    geo_text = ' '.join(geo_tags)
    
    score = 0.0
    for level, regions in CLIENT_REGIONS.items():
        for region in regions:
            if region in geo_text:
                if level == 'critical':
                    score += 3.0
                elif level == 'high':
                    score += 2.0
                else:
                    score += 1.0
    
    return min(score, 10.0)

def calculate_relevance_score(event: dict) -> dict:
    """Calculate comprehensive relevance score for event."""
    
    headline = str(event.get('headline', '')).lower()
    summary = str(event.get('summary', '')).lower()
    domain = str(event.get('predicted_structural_domain', '')).lower()
    text = f"{headline} {summary} {domain}"
    
    # Component scores (0-10 each)
    pharma_score = score_keywords(text, PHARMA_KEYWORDS)
    regulatory_score = score_keywords(text, REGULATORY_KEYWORDS)
    supply_chain_score = score_keywords(text, SUPPLY_CHAIN_KEYWORDS)
    region_score = score_regions(event)
    severity = float(event.get('predicted_structural_similarity', 0.5)) * 10
    
    # Weighted total (0-100)
    total_score = (
        pharma_score * WEIGHTS['pharma_keywords'] / 10 +
        regulatory_score * WEIGHTS['regulatory_keywords'] / 10 +
        region_score * WEIGHTS['region_match'] / 10 +
        supply_chain_score * WEIGHTS['supply_chain_keywords'] / 10 +
        severity * WEIGHTS['severity_score'] / 10
    )
    
    # Determine risk level
    if total_score >= 70:
        risk_level = "Critical"
        priority = "Immediate"
    elif total_score >= 50:
        risk_level = "High"
        priority = "High"
    elif total_score >= 30:
        risk_level = "Medium"
        priority = "Medium"
    else:
        risk_level = "Low"
        priority = "Low"
    
    # Determine impact areas
    impact_areas = []
    if regulatory_score > 3:
        impact_areas.append("Regulatory/Compliance")
    if supply_chain_score > 3:
        impact_areas.append("Supply Chain")
    if pharma_score > 5:
        impact_areas.append("Market/Competition")
    if region_score > 5:
        impact_areas.append("Geographic Operations")
    
    # Generate business impact explanation
    impact_parts = []
    if 'fda' in text or 'approval' in text:
        impact_parts.append("FDA regulatory implications")
    if 'china' in text and ('manufacturing' in text or 'supply' in text):
        impact_parts.append("China sourcing risk")
    if 'india' in text and 'manufacturing' in text:
        impact_parts.append("India manufacturing operations")
    if 'generic' in text or 'drug' in text:
        impact_parts.append("competitive pharma landscape")
    
    business_impact = "Affects " + ", ".join(impact_parts) if impact_parts else "General pharma industry relevance"
    
    return {
        "relevance_score": round(total_score, 1),
        "risk_level": risk_level,
        "impact_areas": impact_areas,
        "business_impact": business_impact,
        "action_priority": priority,
        "component_scores": {
            "pharma": round(pharma_score, 1),
            "regulatory": round(regulatory_score, 1),
            "supply_chain": round(supply_chain_score, 1),
            "region": round(region_score, 1),
            "severity": round(severity, 1),
        }
    }

def main():
    base_dir = os.path.dirname(__file__)
    
    # Load filtered events
    filtered_path = os.path.join(base_dir, 'data', 'llm_filtered_relevant_events.jsonl')
    events = []
    with open(filtered_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    print("=" * 80)
    print("RANKING TOP 10 RISK EVENTS FOR MERIDIAN LIFESCIENCES")
    print("Rule-Based Scoring (No API Required)")
    print("=" * 80)
    print(f"\nProcessing {len(events)} pre-filtered events...\n")
    
    # Score all events
    for event in events:
        ranking = calculate_relevance_score(event)
        event['client_ranking'] = ranking
    
    # Sort by relevance score
    events.sort(key=lambda x: x['client_ranking']['relevance_score'], reverse=True)
    
    # Get top 10
    top_10 = events[:10]
    
    print("=" * 80)
    print("TOP 10 RISK EVENTS FOR MERIDIAN")
    print("=" * 80)
    
    for i, event in enumerate(top_10, 1):
        ranking = event['client_ranking']
        components = ranking['component_scores']
        
        print(f"\n{i}. {event.get('headline', 'Unknown')[:75]}")
        print(f"   Score: {ranking['relevance_score']}/100 | Risk: {ranking['risk_level']} | Priority: {ranking['action_priority']}")
        print(f"   Impact: {ranking['business_impact'][:90]}")
        print(f"   Areas: {', '.join(ranking['impact_areas'])}")
        print(f"   Components: Pharma={components['pharma']}, Reg={components['regulatory']}, "
              f"Supply={components['supply_chain']}, Region={components['region']}")
    
    # Save top 10
    output_path = os.path.join(base_dir, 'data', 'top_10_client_risks.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(top_10, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print(f"✅ Saved top 10 events to: {output_path}")
    
    # Also save full ranked list
    full_output_path = os.path.join(base_dir, 'data', 'all_ranked_client_risks.json')
    with open(full_output_path, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved all {len(events)} ranked events to: {full_output_path}")
    print("=" * 80)
    print("\nDone! No API calls required.")

if __name__ == '__main__':
    main()
