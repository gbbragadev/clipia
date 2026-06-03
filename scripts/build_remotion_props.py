"""CLI: build Remotion props (CompositionData) for a generated job.

Thin wrapper around app.services.remotion.build_composition_props (DRY).

Usage:
    python -m scripts.build_remotion_props <job_id> [out_path] [backend_url]
"""

import json
import sys
from pathlib import Path

from app.services.remotion import build_composition_props

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m scripts.build_remotion_props <job_id> [out_path] [backend_url]")
        sys.exit(2)
    job_id = sys.argv[1]
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("storage/remotion-spike/props.json")
    backend = sys.argv[3] if len(sys.argv) > 3 else None
    props = build_composition_props(job_id, backend)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"wrote {out_path}: {len(props['scenes'])} scenes, {len(props['words'])} words, {len(props['mediaUrls'])} media"
    )
