"""Load SD-2 snapshots and check REQ-03's three referential invariants."""
from collections import Counter, defaultdict
from datetime import datetime
from importlib.resources import files
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator, FormatChecker


FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time", raises=ValueError)
def rfc3339(value):
    """Enforce timestamps without jsonschema's optional format dependencies."""
    if not isinstance(value, str):
        return True  # The schema's type check reports non-string input.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):
        return False
    datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
    return True


class SnapshotError(ValueError):
    """Unusable snapshot; the CLI presents every violation with exit 2."""


def json_path(parts):
    path = ""
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else ("." if path else "") + part
    return path or "$"


def validate(snapshot, *, allow_partial=False) -> list[str]:
    """Validate schema and references; explicit partial opt-in tolerates missing visibility.

    Missing nodes and duplicate known pair roles remain errors. An invisible
    database's policy cannot be inferred from its visible shard references.
    """
    schema = json.loads(files("recap").joinpath("schemas/snapshot.v1.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    errors = [f"{json_path(error.absolute_path)}: {error.message}" for error in validator.iter_errors(snapshot)]
    if errors:
        return errors
    partial = allow_partial and snapshot['provenance']['partial']

    nodes = {node["uid"] for node in snapshot["nodes"]}
    bdbs = {bdb["uid"] for bdb in snapshot["bdbs"]}
    pairs = defaultdict(list)
    for index, shard in enumerate(snapshot["shards"]):
        if shard["node_uid"] not in nodes:
            errors.append(f"shards[{index}].node_uid: node {shard['node_uid']} does not exist")
        if shard["bdb_uid"] not in bdbs and not partial:
            errors.append(f"shards[{index}].bdb_uid: database {shard['bdb_uid']} does not exist")
        pairs[shard["bdb_uid"], shard["slots"]].append((index, shard["role"]))

    for index, bdb in enumerate(snapshot["bdbs"]):
        if not bdb["replication"]:
            continue
        ranges = {slots: members for (uid, slots), members in pairs.items() if uid == bdb["uid"]}
        if not ranges and not partial:
            errors.append(f"bdbs[{index}].shards_count: replicated database {bdb['uid']} requires one master and one replica per slot range; no shards found")
        for slots, members in ranges.items():
            roles = Counter(role for _, role in members)
            invalid = any(count > 1 for count in roles.values()) if partial else roles != {"master": 1, "replica": 1}
            if invalid:
                path = f"shards[{members[0][0]}].slots"
                errors.append(f"{path}: database {bdb['uid']}, range {slots!r} requires exactly one master and one replica")
    return errors


def load(path, *, allow_partial=False):
    """Read a file or stdin, validate it and enforce the explicit partial opt-in."""
    try:
        if str(path) == "-":
            snapshot = json.load(sys.stdin)
        else:
            snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SnapshotError(f"{path}: {exc}") from exc
    errors = validate(snapshot, allow_partial=allow_partial)
    if errors:
        raise SnapshotError("\n".join(errors))
    if snapshot["provenance"]["partial"] and not allow_partial:
        reasons = "; ".join(snapshot["provenance"]["partial_reasons"])
        raise SnapshotError(f"partial snapshot requires --allow-partial: {reasons}")
    return snapshot
