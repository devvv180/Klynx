import json
import os

base_dir = os.path.dirname(__file__)

frames_file = os.path.join(base_dir, "risk_engine", "data", "merged_event_frames_similarity_gold_clean_v9.jsonl")
domains_file = os.path.join(base_dir, "risk_engine", "data", "merged_events_333.jsonl")

frames = []
domains = {}

# Load domain dataset
with open(domains_file) as f:
    for line in f:
        obj = json.loads(line)
        domains[obj["event_id"]] = obj

# Merge with frames dataset
with open(frames_file) as f:
    for line in f:
        event = json.loads(line)

        eid = event["event_id"]

        if eid in domains:

            event["top_signature_domain"] = domains[eid].get("top_signature_domain")
            event["top_signature_driver"] = domains[eid].get("top_signature_driver")

        frames.append(event)

# Save merged file
output_file = os.path.join(base_dir, "risk_engine", "data", "final_event_dataset.jsonl")
with open(output_file, "w") as f:
    for e in frames:
        f.write(json.dumps(e) + "\n")

print(f"Merged dataset saved as {output_file}")