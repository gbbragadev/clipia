"""Mandatory gate before switching to a pre-SQL-refine ClipIA binary.

Run from the repository root:
    python -m scripts.pre_rollback_refine_gate

Exit 0 proves every committed SQL balance was projected to the legacy Redis
key read by ba03321 and SQL authority was handed off atomically. Any remaining
row blocks the application rollback.

Operational prerequisite: remove the current/new API, worker and beat from
traffic, then prevent writes by both versions for the whole gate-to-switch
window. Start ba03321 only after this command exits zero. A successful gate is
not a lock against writes committed after it returns.

The old-to-new roll-forward has the same no-mixed-writers requirement: quiesce
the ba03321 API and workers before the new API/worker/beat begin lazy imports.
"""

from __future__ import annotations

import asyncio
import json

from app.worker.tasks import _prepare_refine_balance_rollback_async


def main() -> int:
    result = asyncio.run(_prepare_refine_balance_rollback_async())
    print(json.dumps(result, sort_keys=True))
    return 0 if result["remaining"] == 0 else 1


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
