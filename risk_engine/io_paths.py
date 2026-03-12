import os
import re


def get_output_tag() -> str:
    raw = os.getenv("OUTPUT_TAG", "").strip().lower()
    if not raw:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return normalized


def tag_filename(filename: str) -> str:
    tag = get_output_tag()
    if not tag:
        return filename
    return f"{tag}_{filename}"


def data_path(base_dir: str, filename: str) -> str:
    return os.path.join(base_dir, "data", filename)
