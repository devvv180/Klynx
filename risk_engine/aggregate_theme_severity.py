import json
from collections import defaultdict
import os
from io_paths import tag_filename

base_dir = os.path.dirname(__file__)

input_path = os.path.join(
    base_dir,
    "data",
    tag_filename("event_severity_results.json")
)

output_path = os.path.join(
    base_dir,
    "data",
    tag_filename("theme_severity.json")
)

print("\nLoading event severity data...\n")

with open(input_path, "r") as f:
    events = json.load(f)

theme_scores = defaultdict(list)

# -----------------------------
# GROUP SEVERITY BY THEME
# -----------------------------
for event in events:

    theme = event.get("internal_theme")
    severity = event.get("severity_score")

    if theme is None or severity is None:
        continue

    theme_scores[theme].append(severity)


# -----------------------------
# CALCULATE AVERAGE SEVERITY
# -----------------------------
theme_severity = {}

for theme, scores in theme_scores.items():

    avg = sum(scores) / len(scores)

    theme_severity[theme] = round(avg, 3)

    print(f"{theme} → avg severity: {round(avg,3)}")


# -----------------------------
# SAVE RESULT
# -----------------------------
with open(output_path, "w") as f:
    json.dump(theme_severity, f, indent=4)

print("\nTheme severity saved to:")
print(output_path)
