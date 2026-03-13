import json
from datetime import datetime, timezone

# Load demo events
with open('data/event_severity_results_demo.json', 'r') as f:
    events = json.load(f)

# Build sector report
sector_groups = {}
for event in events:
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

with open('data/sector_top_10_risks_demo.json', 'w') as f:
    json.dump(report, f, indent=2)

print(f'Created demo sector report with {len(sectors_out)} sectors')
for s in sectors_out:
    print(f"  {s['sector']}: {s['event_count']} events, avg severity {s['avg_severity']}")
