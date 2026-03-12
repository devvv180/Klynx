import hashlib
import json
import os
from collections import Counter

import pandas as pd

from io_paths import get_output_tag, tag_filename


# ---------------------------------------------------
# TEXT NORMALIZATION
# ---------------------------------------------------

def normalize_exact(value):
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text or text == "nan":
        return ""
    text = text.replace(" and ", " & ")
    text = " ".join(text.split())
    return text


def normalize_relaxed(value):
    text = normalize_exact(value)
    if not text:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


# ---------------------------------------------------
# STEP 1 — LOAD STRUCTURAL DOMAIN -> PRIMARY THEME MAPPING
# ---------------------------------------------------

def load_domain_theme_mapping():
    base_dir = os.path.dirname(__file__)
    mapping_path = os.path.join(base_dir, "config", "fixed_mapping.xlsx")

    print("\nLoading structural domain mapping from:")
    print(mapping_path)

    sheets = pd.read_excel(mapping_path, sheet_name=None)
    sheet_names = list(sheets.keys())

    print("\nSheets detected:")
    print(sheet_names)

    selected_env = os.getenv("MAPPING_SHEETS", "").strip()

    # Default: use first sheet only (as requested).
    if not selected_env:
        selected_sheet_names = [sheet_names[0]]
    elif selected_env.lower() in {"all", "*"}:
        selected_sheet_names = sheet_names
    else:
        selected_sheet_names = [s.strip() for s in selected_env.split(",") if s.strip()]

    valid_sheet_names = [s for s in selected_sheet_names if s in sheets]

    if not valid_sheet_names:
        raise ValueError(
            "No valid mapping sheet selected. "
            "Set MAPPING_SHEETS to a valid sheet name or use MAPPING_SHEETS=all."
        )

    print("\nUsing mapping sheets:")
    print(valid_sheet_names)

    domain_to_theme_exact = {}
    domain_to_theme_relaxed = {}
    conflicts = []

    for sheet_name in valid_sheet_names:
        df = sheets[sheet_name]
        df.columns = [str(c).strip() for c in df.columns]

        if "Structural Domain" not in df.columns or "Primary Internal Theme" not in df.columns:
            print(f"Skipping sheet '{sheet_name}' (required columns not found)")
            continue

        for _, row in df.iterrows():
            domain_raw = row["Structural Domain"]
            theme_raw = row["Primary Internal Theme"]

            domain_exact = normalize_exact(domain_raw)
            domain_relaxed = normalize_relaxed(domain_raw)
            theme = str(theme_raw).strip()

            if not domain_exact or not domain_relaxed:
                continue
            if not theme or theme.lower() == "nan":
                continue

            if domain_exact in domain_to_theme_exact and domain_to_theme_exact[domain_exact] != theme:
                conflicts.append((domain_exact, domain_to_theme_exact[domain_exact], theme, sheet_name))

            domain_to_theme_exact[domain_exact] = theme
            domain_to_theme_relaxed[domain_relaxed] = theme

    if conflicts:
        print("\nWARNING: conflicting primary theme mappings found (last one kept):")
        for c in conflicts[:10]:
            print(c)

    print("\nTotal structural domains mapped (exact):", len(domain_to_theme_exact))

    return domain_to_theme_exact, domain_to_theme_relaxed


# ---------------------------------------------------
# STEP 2 — LOAD EXTERNAL EVENTS
# ---------------------------------------------------

def load_external_events():
    base_dir = os.path.dirname(__file__)

    events_file = os.getenv("EXTERNAL_EVENTS_FILE", "merged_events.jsonl")
    min_similarity = float(os.getenv("MIN_SIMILARITY_SCORE", "0.70"))

    if os.path.isabs(events_file):
        events_path = events_file
    else:
        events_path = os.path.join(base_dir, "data", events_file)

    print("\nLoading external events from:")
    print(events_path)
    print("Similarity threshold:", min_similarity)

    events = []

    # Supports JSON array and JSONL.
    if events_path.lower().endswith(".json"):
        with open(events_path, "r") as f:
            loaded = json.load(f)
            if isinstance(loaded, list):
                events = loaded
            else:
                raise ValueError("JSON input must be a list of event objects")
    else:
        with open(events_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                events.append(json.loads(line))

    filtered = []
    for obj in events:
        similarity = obj.get("similarity_score")

        if similarity is not None:
            try:
                if float(similarity) < min_similarity:
                    continue
            except Exception:
                pass

        filtered.append(obj)

    print("Total events loaded:", len(filtered))

    return filtered, events_path


# ---------------------------------------------------
# STEP 3 — MAP EVENTS -> PRIMARY INTERNAL THEMES
# ---------------------------------------------------

def generate_event_id(event):
    stable_key = (
        f"{event.get('headline','')}|{event.get('actor','')}|"
        f"{event.get('action','')}{event.get('verb','')}|"
        f"{event.get('target','')}{event.get('object','')}|"
        f"{event.get('geography','')}"
    )
    digest = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()[:16]
    return f"generated://event/{digest}"


def resolve_domain(event):
    for key in ["structural_domain", "predicted_structural_domain", "best_signature_domain", "domain"]:
        value = event.get(key)
        exact = normalize_exact(value)
        if exact:
            return str(value).strip(), key
    return "Unknown Domain", "fallback"


def map_events_to_internal_themes():
    events, input_events_path = load_external_events()
    map_exact, map_relaxed = load_domain_theme_mapping()

    print("\nEvent -> Primary Internal Theme Mapping\n")

    mapped_events = []
    enriched_events = []

    for idx, event in enumerate(events):
        domain, source_field = resolve_domain(event)

        domain_exact = normalize_exact(domain)
        domain_relaxed = normalize_relaxed(domain)

        primary_theme = map_exact.get(domain_exact)
        matched_by = "exact"

        if primary_theme is None:
            primary_theme = map_relaxed.get(domain_relaxed)
            matched_by = "relaxed"

        if primary_theme is None:
            primary_theme = "NOT FOUND"
            matched_by = "none"

        event_id = event.get("event_id") or generate_event_id(event)

        mapped_event = {
            "event_index": idx,
            "event_id": event_id,
            "headline": event.get("headline", "Unknown Event"),
            "summary": event.get("summary"),
            "structural_domain": domain,
            "structural_domain_source_field": source_field,
            "primary_internal_theme": primary_theme,
            "internal_theme": primary_theme,
            "mapped_theme_source_column": "Primary Internal Theme",
            "domain_match_type": matched_by,
            "similarity_score": event.get("similarity_score"),
            "actor": event.get("actor"),
            "verb": event.get("verb") or event.get("action"),
            "object": event.get("object") or event.get("target"),
            "geography": event.get("geography"),
        }

        mapped_events.append(mapped_event)

        enriched_event = dict(event)
        enriched_event["event_id"] = event_id
        enriched_event["structural_domain"] = domain
        enriched_event["structural_domain_source_field"] = source_field
        enriched_event["primary_internal_theme"] = primary_theme
        enriched_event["internal_theme"] = primary_theme
        enriched_event["mapped_theme_source_column"] = "Primary Internal Theme"
        enriched_event["domain_match_type"] = matched_by
        enriched_events.append(enriched_event)

        if idx < 20 or idx % 50 == 0:
            headline = mapped_event["headline"]
            print(
                f"Event {idx:03d} | {headline[:80]} | "
                f"Domain: {domain} ({source_field}) | "
                f"Primary Theme: {primary_theme} [{matched_by}]"
            )

    not_found_count = sum(1 for e in mapped_events if e["primary_internal_theme"] == "NOT FOUND")
    theme_counts = Counter(e["primary_internal_theme"] for e in mapped_events)

    print(f"\nMapping summary: total={len(mapped_events)}, NOT FOUND={not_found_count}")
    print("Theme distribution:", dict(theme_counts))

    save_outputs(mapped_events, map_exact, map_relaxed, enriched_events, input_events_path)

    return mapped_events


# ---------------------------------------------------
# STEP 4 — SAVE OUTPUTS
# ---------------------------------------------------

def save_outputs(mapped_events, map_exact, map_relaxed, enriched_events, input_events_path):
    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, "data")

    mapping_view = []
    for event in mapped_events:
        mapping_view.append({
            "event_index": event["event_index"],
            "headline": event["headline"],
            "structural_domain": event["structural_domain"],
            "structural_domain_source_field": event["structural_domain_source_field"],
            "primary_internal_theme": event["primary_internal_theme"],
            "internal_theme": event["internal_theme"],
            "mapped_theme_source_column": event["mapped_theme_source_column"],
            "domain_match_type": event["domain_match_type"],
        })

    base_external = os.path.join(data_dir, "external_mapped_events.json")
    base_mapping = os.path.join(data_dir, "event_theme_mapping.json")
    input_basename = os.path.basename(input_events_path)
    input_stem = input_basename.rsplit(".", 1)[0]
    base_enriched_jsonl = os.path.join(data_dir, f"{input_stem}_with_internal_theme.jsonl")

    with open(base_external, "w") as f:
        json.dump(mapped_events, f, indent=4)

    with open(base_mapping, "w") as f:
        json.dump(mapping_view, f, indent=4)

    audit_rows = []
    for event in mapped_events:
        domain = event["structural_domain"]
        expected_theme = map_exact.get(normalize_exact(domain))
        if expected_theme is None:
            expected_theme = map_relaxed.get(normalize_relaxed(domain))
        if expected_theme is None:
            expected_theme = "NOT FOUND"

        mapped_theme = event["primary_internal_theme"]

        audit_rows.append(
            {
                "event_index": event["event_index"],
                "event_id": event["event_id"],
                "headline": event["headline"],
                "structural_domain": domain,
                "structural_domain_source_field": event["structural_domain_source_field"],
                "mapped_primary_internal_theme": mapped_theme,
                "expected_primary_internal_theme": expected_theme,
                "is_correct_against_mapping": mapped_theme == expected_theme,
                "domain_match_type": event["domain_match_type"],
            }
        )

    audit_summary = {
        "total_events": len(mapped_events),
        "mapped_events": sum(1 for e in mapped_events if e["primary_internal_theme"] != "NOT FOUND"),
        "not_found_events": sum(1 for e in mapped_events if e["primary_internal_theme"] == "NOT FOUND"),
        "unique_themes_mapped": len(
            {
                e["primary_internal_theme"]
                for e in mapped_events
                if e["primary_internal_theme"] != "NOT FOUND"
            }
        ),
        "theme_distribution": dict(
            Counter(e["primary_internal_theme"] for e in mapped_events)
        ),
        "all_rows_correct_against_mapping": all(
            r["is_correct_against_mapping"] for r in audit_rows
        ),
    }

    audit_output = {
        "summary": audit_summary,
        "rows": audit_rows,
    }

    base_audit = os.path.join(data_dir, "mapping_audit_report.json")
    with open(base_audit, "w") as f:
        json.dump(audit_output, f, indent=4)

    with open(base_enriched_jsonl, "w") as f:
        for row in enriched_events:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("\nSaved:")
    print(base_external)
    print(base_mapping)
    print(base_audit)
    print(base_enriched_jsonl)

    output_tag = get_output_tag()
    if output_tag:
        tagged_external = os.path.join(data_dir, tag_filename("external_mapped_events.json"))
        tagged_mapping = os.path.join(data_dir, tag_filename("event_theme_mapping.json"))

        with open(tagged_external, "w") as f:
            json.dump(mapped_events, f, indent=4)

        with open(tagged_mapping, "w") as f:
            json.dump(mapping_view, f, indent=4)

        tagged_audit = os.path.join(data_dir, tag_filename("mapping_audit_report.json"))
        with open(tagged_audit, "w") as f:
            json.dump(audit_output, f, indent=4)

        enriched_filename = f"{input_stem}_with_internal_theme.jsonl"
        input_stem_lower = input_stem.lower()
        if input_stem_lower == output_tag or input_stem_lower.startswith(f"{output_tag}_"):
            tagged_enriched = os.path.join(data_dir, enriched_filename)
        else:
            tagged_enriched = os.path.join(data_dir, tag_filename(enriched_filename))
        if tagged_enriched != base_enriched_jsonl:
            with open(tagged_enriched, "w") as f:
                for row in enriched_events:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

        print("\nSaved tagged copies:")
        print(tagged_external)
        print(tagged_mapping)
        print(tagged_audit)
        if tagged_enriched != base_enriched_jsonl:
            print(tagged_enriched)


# ---------------------------------------------------
# RUN
# ---------------------------------------------------

if __name__ == "__main__":
    print("\n================ EXTERNAL ENGINE ================\n")
    map_events_to_internal_themes()
