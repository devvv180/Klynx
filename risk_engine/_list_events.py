import json
events = [json.loads(l) for l in open('data/llm_filtered_relevant_events.jsonl','r',encoding='utf-8') if l.strip()]
for i, e in enumerate(events, 1):
    h = e.get('headline','')[:90]
    p = e.get('predicted_structural_driver','')
    g = ', '.join(e.get('geo_tags',[])[:3])
    print(f"{i}. {h} | {p} | {g}")
