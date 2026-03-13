import json

# Load events
events = []
with open('data/merged_lexis_event_frames_similarity_v1.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            events.append(json.loads(line))

print(f'Total events: {len(events)}\n')
print('Sample of first 15 events:')
print('=' * 120)

for i, ev in enumerate(events[:15], 1):
    headline = ev.get('headline', 'Unknown')[:90]
    domain = ev.get('predicted_structural_domain', 'Unknown')
    pillar = ev.get('predicted_structural_driver', 'Unknown')
    geo_tags = ev.get('geo_tags', [])[:3]
    
    print(f'{i}. {headline}')
    print(f'   Pillar: {pillar}')
    print(f'   Domain: {domain}')
    print(f'   Geo: {", ".join(geo_tags)}')
    print()
