import json
import random
from datetime import datetime, timezone

# Load original events
with open('data/event_severity_results.json', 'r') as f:
    all_events = json.load(f)

# Define sector-specific keyword filters (events must match to be included)
sector_relevance_keywords = {
    'Financial Services': {
        'required': ['bank', 'financial', 'finance', 'currency', 'payment', 'sanction', 'treasury',
                    'capital', 'credit', 'liquidity', 'fx', 'dollar', 'euro', 'swift', 'asset',
                    'investment', 'fund', 'loan', 'debt', 'bond', 'stock', 'market crash'],
        'exclude': []
    },
    'Energy & Utilities': {
        'required': ['oil', 'gas', 'energy', 'pipeline', 'lng', 'petroleum', 'refinery', 
                    'electricity', 'power', 'grid', 'utility', 'fuel', 'opec', 'crude',
                    'renewable', 'solar', 'wind', 'nuclear power', 'coal'],
        'exclude': []
    },
    'Technology & Telecommunications': {
        'required': ['semiconductor', 'chip', 'ai', 'cyber', 'technology', 'software', 'hardware',
                    'data', 'cloud', 'telecom', '5g', 'internet', 'digital', 'tech', 'computing',
                    'ransomware', 'hack', 'breach', 'server', 'network', 'platform'],
        'exclude': []
    },
    'Healthcare & Life Sciences': {
        'required': ['health', 'medical', 'hospital', 'pharma', 'drug', 'vaccine', 'patient',
                    'medicine', 'healthcare', 'clinical', 'biotech', 'disease', 'treatment',
                    'fda', 'pharmaceutical', 'therapy', 'diagnostic'],
        'exclude': []
    },
    'Consumer, Retail & E-Commerce': {
        'required': ['retail', 'consumer', 'shopping', 'store', 'ecommerce', 'e-commerce',
                    'brand', 'product', 'supply chain', 'logistics', 'delivery', 'warehouse',
                    'inventory', 'sales', 'customer', 'market', 'goods'],
        'exclude': []
    },
    'Defense, Aerospace & Security': {
        'required': ['military', 'defense', 'weapon', 'missile', 'army', 'navy', 'air force',
                    'war', 'conflict', 'attack', 'strike', 'combat', 'security', 'threat',
                    'nuclear', 'drone', 'fighter', 'tank', 'soldier', 'troop'],
        'exclude': []
    }
}

# Theme distributions per sector
sector_theme_profiles = {
    'Financial Services': {
        'Finance/Treasury/FP&A': 0.40,
        'Governance, Risk & Compliance': 0.25,
        'Cybersecurity': 0.20,
        'Strategy & Business Model': 0.10,
        'Operations': 0.05
    },
    'Energy & Utilities': {
        'Operations': 0.35,
        'Strategy & Business Model': 0.25,
        'Finance/Treasury/FP&A': 0.20,
        'Governance, Risk & Compliance': 0.15,
        'Human Resources': 0.05
    },
    'Technology & Telecommunications': {
        'Cybersecurity': 0.35,
        'Strategy & Business Model': 0.30,
        'Operations': 0.20,
        'Finance/Treasury/FP&A': 0.10,
        'Human Resources': 0.05
    },
    'Healthcare & Life Sciences': {
        'Governance, Risk & Compliance': 0.30,
        'Operations': 0.25,
        'Strategy & Business Model': 0.20,
        'Finance/Treasury/FP&A': 0.15,
        'Human Resources': 0.10
    },
    'Consumer, Retail & E-Commerce': {
        'Operations': 0.30,
        'Strategy & Business Model': 0.25,
        'Finance/Treasury/FP&A': 0.20,
        'Cybersecurity': 0.15,
        'Human Resources': 0.10
    },
    'Defense, Aerospace & Security': {
        'Strategy & Business Model': 0.35,
        'Governance, Risk & Compliance': 0.25,
        'Operations': 0.20,
        'Cybersecurity': 0.15,
        'Human Resources': 0.05
    }
}

def is_relevant_to_sector(event, sector_keywords):
    """Check if event is relevant to sector based on keywords"""
    text = ' '.join([
        str(event.get('headline', '')),
        str(event.get('summary', '')),
        str(event.get('structural_domain', '')),
        str(event.get('actor', '')),
        str(event.get('action', '')),
        str(event.get('target', ''))
    ]).lower()
    
    # Check if any required keyword is present
    for keyword in sector_keywords['required']:
        if keyword.lower() in text:
            return True
    return False

# Filter and assign events to sectors
sector_events = {sector: [] for sector in sector_relevance_keywords.keys()}

for event in all_events:
    for sector, keywords in sector_relevance_keywords.items():
        if is_relevant_to_sector(event, keywords):
            event_copy = event.copy()
            event_copy['sector'] = sector
            sector_events[sector].append(event_copy)

# Redistribute themes and limit to reasonable numbers
random.seed(42)
curated_events = []

for sector, events in sector_events.items():
    if not events:
        continue
    
    # Sort by severity and take top events
    events_sorted = sorted(events, key=lambda x: float(x.get('severity_score', 0)), reverse=True)
    
    # Take top 15-20 events per sector for variety
    selected_events = events_sorted[:min(20, len(events_sorted))]
    
    # Assign themes based on sector profile
    profile = sector_theme_profiles[sector]
    themes = list(profile.keys())
    weights = list(profile.values())
    
    for event in selected_events:
        event['internal_theme'] = random.choices(themes, weights=weights)[0]
        curated_events.append(event)

# Save curated events
with open('data/event_severity_results_demo_curated.json', 'w') as f:
    json.dump(curated_events, f, indent=2)

# Build sector report
sector_groups = {}
for event in curated_events:
    sector = event.get('sector', 'Unknown')
    sector_groups.setdefault(sector, []).append(event)

sectors_out = []
for sector, items in sector_groups.items():
    ranked = sorted(items, key=lambda x: float(x.get('severity_score', 0)), reverse=True)
    top_10 = ranked[:10]
    avg_severity = sum(float(x.get('severity_score', 0)) for x in items) / len(items)
    
    sectors_out.append({
        'sector': sector,
        'event_count': len(items),
        'avg_severity': round(avg_severity, 3),
        'high_risk_count': sum(1 for x in items if float(x.get('severity_score', 0)) >= 0.60),
        'critical_risk_count': sum(1 for x in items if float(x.get('severity_score', 0)) >= 0.80),
        'top_risks': [{
            'event_id': x.get('event_id'),
            'headline': x.get('headline'),
            'severity_score': x.get('severity_score'),
            'internal_theme': x.get('internal_theme'),
            'structural_domain': x.get('structural_domain'),
            'geography': x.get('geography')
        } for x in top_10]
    })

sectors_out.sort(key=lambda s: (s['avg_severity'], s['event_count']), reverse=True)

report = {
    'generated_at_utc': datetime.now(timezone.utc).isoformat(),
    'top_n_per_sector': 10,
    'sector_count': len(sectors_out),
    'sectors': sectors_out
}

with open('data/sector_top_10_risks_demo_curated.json', 'w') as f:
    json.dump(report, f, indent=2)

print(f'\n✅ Created curated demo dataset with {len(curated_events)} sector-relevant events')
print(f'\n📊 Sector breakdown:')
for s in sectors_out:
    print(f"  • {s['sector']}: {s['event_count']} events, avg severity {s['avg_severity']:.2f}")
    print(f"    Top event: {s['top_risks'][0]['headline'][:80]}...")
