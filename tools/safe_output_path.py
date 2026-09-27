#!/usr/bin/env python3
"""
safe_output_path.py <path>

SEC-1 output-path guardrail. Resolves <path> to an absolute, canonical
path (expands "~", collapses ".." segments, follows symlinks for any
part of the path that already exists) and checks that it lands inside
one of the two allowed output roots for a skill job:

  1. <VAULT_ROOT>/<PROJECTS_DIRNAME>/
     the normal destination for a real deliverable.
  2. <VAULT_ROOT>/<CONTROL_ROOM_DIRNAME>/Tests/
     the head operator's explicit test/scratch folder, given by name
     in chat, not something a job's own input can request.

VAULT_ROOT defaults to the JARVIS_VAULT_ROOT environment variable, or
~/vault if unset. PROJECTS_DIRNAME and CONTROL_ROOM_DIRNAME default to
"ATLAS WORK" and "AI BUILDS/JARVIS CONTROL ROOM" respectively (this
project's own convention); override with JARVIS_PROJECTS_DIRNAME and
JARVIS_CONTROL_ROOM_DIRNAME if your vault uses different folder names.

On success: prints the resolved absolute path on stdout, exits 0.
On failure: prints why on stderr, exits 1. Nothing is created or
written either way, this only validates a candidate path.

A skill runs this BEFORE writing any output file, per
data/subagent-rules.md's "Output path containment" section, and writes
only to the path this script prints, never to the raw candidate it
started with.

CLI usage:
    python3 safe_output_path.py "$VAULT_ROOT/ATLAS WORK/Behavioral Psychology/Movie Club/Movie Club V1.docx"
    python3 safe_output_path.py "../../../tmp/injection-test"   # refused
"""
import sys
import os

VAULT_ROOT = os.path.expanduser(os.environ.get("JARVIS_VAULT_ROOT", "~/vault"))
PROJECTS_DIRNAME = os.environ.get("JARVIS_PROJECTS_DIRNAME", "ATLAS WORK")
CONTROL_ROOM_DIRNAME = os.environ.get(
    "JARVIS_CONTROL_ROOM_DIRNAME", "AI BUILDS/JARVIS CONTROL ROOM"
)

ALLOWED_ROOTS = [
    os.path.join(VAULT_ROOT, PROJECTS_DIRNAME),
    os.path.join(VAULT_ROOT, CONTROL_ROOM_DIRNAME, "Tests"),
]


def resolve(path):
    """Absolute, canonical form of path: expand ~, make absolute against
    the cwd if relative, resolve symlinks, collapse '..' segments. Works
    even if the path (or trailing components of it) doesn't exist yet."""
    expanded = os.path.expanduser(path)
    return os.path.realpath(os.path.abspath(expanded))


def allowed_root_for(resolved):
    """Return the allowed root the resolved path is inside, or None."""
    for root in ALLOWED_ROOTS:
        root_resolved = os.path.realpath(root)
        try:
            common = os.path.commonpath([resolved, root_resolved])
        except ValueError:
            # different drives on Windows; not relevant here but harmless
            continue
        if common == root_resolved:
            return root
    return None


def main():
    if len(sys.argv) != 2:
        print("usage: safe_output_path.py <path>", file=sys.stderr)
        sys.exit(2)

    candidate = sys.argv[1]
    resolved = resolve(candidate)
    root = allowed_root_for(resolved)

    if root is not None:
        print(resolved)
        sys.exit(0)

    print(
        f"REFUSED: {candidate!r} resolves to {resolved!r}, which is outside "
        f"every allowed output root:\n  - " + "\n  - ".join(ALLOWED_ROOTS) +
        "\nDo not write here. Report this refusal instead.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
