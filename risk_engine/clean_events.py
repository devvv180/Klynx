import json

input_file = "data/merged_lexis_event_frames_similarity_v1.jsonl"
output_file = "data/clean_event_dataset.jsonl"

clean_events = []

with open(input_file) as f:
    for line in f:
        event = json.loads(line)

        headline = event.get("headline", "")
        summary = event.get("summary", "")

        actor = ""
        action = ""
        target = ""
        geography = ""

        if event.get("event_frame"):
            frame = event["event_frame"][0]["Canonical"]

            actor = frame.get("Actor", "")
            action = frame.get("Action", "")
            target = frame.get("Target", "")
            geography = frame.get("Geography", "")

        clean_event = {
            "headline": headline,
            "summary": summary,
            "actor": actor,
            "action": action,
            "target": target,
            "geography": geography,
            "domain": event.get("top_signature_domain", ""),
            "predicted_structural_domain": event.get("predicted_structural_domain", "")
        }

        clean_events.append(clean_event)

with open(output_file, "w") as f:
    for event in clean_events:
        f.write(json.dumps(event) + "\n")

print("Clean dataset saved to:", output_file)
print("Total events:", len(clean_events))