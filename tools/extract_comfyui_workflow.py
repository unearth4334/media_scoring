#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Tuple, Union

def run_ffprobe(path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format_tags:stream_tags",
        "-print_format", "json",
        path
    ]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(cp.stdout)
    except FileNotFoundError:
        print("ERROR: ffprobe not found. Please install ffmpeg (which includes ffprobe).", file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as e:
        print("ERROR: ffprobe failed:", e.stderr, file=sys.stderr)
        sys.exit(3)
    except json.JSONDecodeError:
        print("ERROR: Could not parse ffprobe output as JSON.", file=sys.stderr)
        sys.exit(4)

def json_candidates_from_tags(tags_container: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Return [(source_label, raw_string)] from a tags dict, where raw_string looks like JSON.
    """
    out = []
    if not tags_container:
        return out
    for k, v in tags_container.items():
        # Only consider string-like values
        if isinstance(v, str):
            s = v.strip()
            # Heuristic: strings that look like JSON or escaped JSON
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                out.append((f"tag:{k}", s))
            else:
                # Sometimes JSON is double-encoded/escaped inside quotes
                # Try to unescape once and see if that becomes JSON-ish
                unesc = try_unescape_json_string(s)
                if unesc is not None and ((unesc.strip().startswith("{") and unesc.strip().endswith("}")) or
                                          (unesc.strip().startswith("[") and unesc.strip().endswith("]"))):
                    out.append((f"tag:{k}(unescaped)", unesc))
    return out

def try_unescape_json_string(s: str) -> Union[str, None]:
    """
    If s looks like it contains a JSON object encoded as a string with lots of backslashes,
    try loading and re-serializing it once to remove escaping.
    """
    # Quick gate: has lots of backslashes or quotes that suggest escaping
    if s.count("\\") < 2 and '\\"' not in s:
        return None
    # Try to decode like a JSON string literal
    try:
        # Wrap in quotes if it isn't already a valid JSON string literal
        candidate = s
        if not (candidate.startswith('"') and candidate.endswith('"')):
            candidate = '"' + candidate.replace('"', '\\"') + '"'
        decoded = json.loads(candidate)
        if isinstance(decoded, str):
            return decoded
    except Exception:
        pass
    return None

def parse_all_tag_sets(ffjson: Dict[str, Any]) -> List[Tuple[str, str]]:
    candidates: List[Tuple[str, str]] = []

    # Format-level tags
    fmt = ffjson.get("format", {})
    fmt_tags = fmt.get("tags", {})
    candidates += [(f"format.{src}", text) for (src, text) in json_candidates_from_tags(fmt_tags)]

    # Stream-level tags
    for idx, stream in enumerate(ffjson.get("streams", [])):
        st_tags = stream.get("tags", {})
        candidates += [(f"stream[{idx}].{src}", text) for (src, text) in json_candidates_from_tags(st_tags)]

    return candidates

def looks_like_comfyui_workflow(obj: Any) -> bool:
    """
    Heuristics for ComfyUI workflow JSON:
      - Top-level dict with keys like 'nodes' (list), 'links' (list) commonly present
      - Or nested under things like {'workflow': {...}} or {'prompt': {'workflow': {...}}}
    """
    if isinstance(obj, dict):
        # direct workflow
        if ("nodes" in obj and "links" in obj) or ("last_node_id" in obj and "last_link_id" in obj):
            return True
        # nested patterns commonly seen in metadata
        for key in ("workflow", "prompt", "extra_pnginfo", "workflow_json", "comfyui_workflow"):
            if key in obj and looks_like_comfyui_workflow(obj[key]):
                return True
    return False

def decode_json(text: str) -> Union[Any, None]:
    try:
        return json.loads(text)
    except Exception:
        # Sometimes it's double-encoded
        try:
            unesc = try_unescape_json_string(text)
            if unesc is not None:
                return json.loads(unesc)
        except Exception:
            pass
    return None

def select_workflow_payloads(candidates: List[Tuple[str, str]]) -> List[Tuple[str, Any, str]]:
    """
    From [(source_label, raw_text)], decode JSON and keep those that look like ComfyUI workflow.
    Return list of (source_label, decoded_obj, pretty_text_to_save).
    """
    chosen = []
    for src, raw in candidates:
        obj = decode_json(raw)
        if obj is None:
            continue
        # If nested, try to find the actual workflow dict to save
        workflow_obj = extract_workflow_dict(obj)
        if workflow_obj is not None:
            pretty = json.dumps(workflow_obj, indent=2, ensure_ascii=False)
            chosen.append((src, workflow_obj, pretty))
        elif looks_like_comfyui_workflow(obj):
            pretty = json.dumps(obj, indent=2, ensure_ascii=False)
            chosen.append((src, obj, pretty))
    return chosen

def extract_workflow_dict(obj: Any) -> Union[Dict[str, Any], None]:
    """Return the most plausible workflow dict from nested structures, else None."""
    if isinstance(obj, dict):
        if ("nodes" in obj and "links" in obj) or ("last_node_id" in obj and "last_link_id" in obj):
            return obj
        for key in ("workflow", "workflow_json", "extra_pnginfo", "prompt", "comfyui_workflow"):
            if key in obj:
                sub = extract_workflow_dict(obj[key])
                if sub is not None:
                    return sub
    return None

def main():
    ap = argparse.ArgumentParser(description="Extract ComfyUI workflow JSON embedded in media metadata.")
    ap.add_argument("input", help="Path to media file (e.g., .mp4) that may contain embedded workflow JSON")
    ap.add_argument("-o", "--output", help="Output file path for the extracted JSON. "
                                           "If multiple workflows are found, this is treated as a *prefix*.")
    ap.add_argument("--dump-all", action="store_true",
                    help="Also dump a raw metadata JSON next to the output for debugging.")
    args = ap.parse_args()

    in_path = args.input
    if not os.path.isfile(in_path):
        print(f"ERROR: File not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    ffjson = run_ffprobe(in_path)
    candidates = parse_all_tag_sets(ffjson)
    workflows = select_workflow_payloads(candidates)

    if not workflows:
        print("No ComfyUI workflow JSON found in the metadata.", file=sys.stderr)
        if args.dump_all:
            raw_path = derive_output_path(in_path, args.output, suffix=".metadata.json")
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(ffjson, f, indent=2, ensure_ascii=False)
            print(f"(Dumped all metadata to {raw_path} for manual inspection.)")
        sys.exit(5)

    base_out = args.output
    if not base_out:
        base_out = os.path.splitext(in_path)[0] + ".workflow.json"

    saved = []
    if len(workflows) == 1:
        out_path = base_out
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(workflows[0][2])
        saved.append(out_path)
        print(f"Saved workflow from {workflows[0][0]} -> {out_path}")
    else:
        # Save each with an index and source suffix
        base_root, base_ext = os.path.splitext(base_out)
        for i, (src, _, pretty) in enumerate(workflows, start=1):
            safe_src = re.sub(r"[^A-Za-z0-9_.\-]+", "_", src)[:80]
            out_path = f"{base_root}.{i}_{safe_src}{base_ext or '.json'}"
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(pretty)
            saved.append(out_path)
            print(f"Saved workflow from {src} -> {out_path}")

    if args.dump_all:
        raw_path = derive_output_path(in_path, args.output, suffix=".metadata.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(ffjson, f, indent=2, ensure_ascii=False)
        print(f"(Dumped all metadata to {raw_path} as well.)")

def derive_output_path(in_path: str, base_out: Union[str, None], suffix: str) -> str:
    if base_out:
        root, _ = os.path.splitext(base_out)
        return root + suffix
    else:
        root, _ = os.path.splitext(in_path)
        return root + suffix

if __name__ == "__main__":
    main()
