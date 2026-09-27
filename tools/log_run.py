#!/usr/bin/env python3
"""
log_run.py --agent <name> --status success|failed --summary "<one line>" --output "<path or none>"

Replacement for the old PostToolUse/SubagentStop hook logging (JR-3), now
that the six Jarvis agents are skills running inline in the current chat
instead of sub-agents. A skill's last step is one call to this script,
which appends a single JSON line to Data/tasks.jsonl in the same shape
the old hook wrote, so the control room's analytics keep working
unchanged.

Never fails loudly: on any error, prints a short warning to stderr and
exits 0, so a skill's last step never blocks on a logging bug.

Usage:
    python3 log_run.py --agent email-drafter --status success \
        --summary "Drafted email to Prof X about deadline" \
        --output none
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import os

VAULT_ROOT = Path(os.path.expanduser(os.environ.get("JARVIS_VAULT_ROOT", "~/vault")))
TASKS_LOG = VAULT_ROOT / "AI BUILDS" / "JARVIS CONTROL ROOM" / "Data" / "tasks.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--status", required=True, choices=["success", "failed"])
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", default="none")
    args = parser.parse_args()

    output = None if args.output in ("none", "", None) else args.output

    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": args.agent,
        "trigger": "chat",
        "status": args.status,
        "skills": [],
        "summary": args.summary,
        "output": output,
        "jobId": None,
    }

    try:
        TASKS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with TASKS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"WARNING: log_run.py could not write tasks.jsonl: {e}", file=sys.stderr)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
