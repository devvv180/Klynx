import json
import os
from io_paths import tag_filename

base_dir = os.path.dirname(__file__)

severity_path = os.path.join(base_dir, "data", tag_filename("theme_severity.json"))
exposure_file = os.getenv("EXPOSURE_FILE", "client_theme_exposure.json")
if os.path.isabs(exposure_file):
    exposure_path = exposure_file
else:
    exposure_path = os.path.join(base_dir, "data", exposure_file)

# ---------------------------------------------------
# Load Data
# ---------------------------------------------------

with open(severity_path) as f:
    events = json.load(f)

with open(exposure_path) as f:
    exposures = json.load(f)

# convert exposure list to dictionary
exposure_map = {}

def normalize_theme(name):
    if name is None:
        return ""

    name = name.lower()

    # normalize common variations
    name = name.replace("and", "&")

    # remove spaces and separators
    for ch in [" ", "/", "_", "-"]:
        name = name.replace(ch, "")

    return name

for item in exposures:
    key = normalize_theme(item.get("internal_theme"))
    exposure_map[key] = item.get("exposure_score", 0)

# ---------------------------------------------------
# Calculate Enterprise Risk (Theme Severity × Exposure)
# ---------------------------------------------------

final_results = []

for theme, severity in events.items():

    normalized_theme = normalize_theme(theme)

    exposure = exposure_map.get(normalized_theme, 0)

    enterprise_risk = round(severity * exposure, 3)

    final_results.append({
        "internal_theme": theme,
        "external_theme_severity": severity,
        "client_exposure": exposure,
        "enterprise_risk": enterprise_risk
    })

    print(f"{theme:35}  Severity: {severity}  Exposure: {exposure}  Enterprise Risk: {enterprise_risk}")

# ---------------------------------------------------
# Save Results
# ---------------------------------------------------

output_path = os.path.join(base_dir, "data", tag_filename("enterprise_risk_results.json"))

with open(output_path, "w") as f:
    json.dump(final_results, f, indent=4)

print("\nEnterprise impact results saved to:", output_path)
