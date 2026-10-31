"""Convert recorded POC tables without executing the shell script or using Redis.

REQ-03 gives rladmin GB/MB a binary meaning, independent of CLI SD-1 parsing.
Displayed fractions are rounded to the nearest byte (Decimal half-even).
"""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re


def binary_bytes(value):
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(GB|MB)", value)
    if match is None:
        raise ValueError(f"unexpected rladmin size: {value}")
    factor = 2**30 if match[2] == "GB" else 2**20
    return int((Decimal(match[1]) * factor).to_integral_value())


def table(source, name):
    match = re.search(rf'^{name}="(.*?)"', source, re.MULTILINE | re.DOTALL)
    if match is None:
        raise ValueError(f"missing recorded table: {name}")
    return [line.split() for line in match[1].splitlines()[2:]]


def uid(value):
    return int(value.lstrip("*").split(":")[-1])


def convert(path):
    source = Path(path).read_text(encoding="utf-8")
    nodes = []
    versions = []
    for row in table(source, "nodesinfo"):
        reported_count, maximum = map(int, row[8].split("/"))
        nodes.append({"uid": uid(row[0]), "rack_id": row[16], "second_rack_id": None,
                      "total_memory": binary_bytes(row[10].split("/")[1]),
                      "provisional_ram": binary_bytes(row[11].split("/")[0]),
                      "max_redis_servers": maximum, "shard_count": reported_count,
                      "accept_servers": True, "status": "active"})
        versions.append(row[14])
    shards = [{"uid": uid(row[2]), "bdb_uid": uid(row[0]), "node_uid": uid(row[3]),
               "role": "replica" if row[4] == "slave" else row[4],
               "slots": row[5], "used_memory": binary_bytes(row[6])}
              for row in table(source, "shardsinfo")]
    response = re.search(r'^response="(.*)"$', source, re.MULTILINE)
    memory_limits = {item["uid"]: item["memory_size"] for item in json.loads(response[1].replace(r'\"', '"'))}
    bdbs = [{"uid": uid(row[0]), "name": row[1], "memory_size": memory_limits[uid(row[0])],
             "shards_count": int(row[4]), "replication": row[6] == "enabled", "rack_aware": True,
             "sharding": int(row[4]) > 1, "shard_key_regex": [], "shards_placement": row[5],
             "bigstore": False, "crdt": False, "unsupported_reason": None}
            for row in table(source, "databasesinfo")]
    warnings = ["Recorded rladmin GB/MB use binary units; displayed fractions rounded to the nearest whole byte.",
                "Unknown POC license, second rack IDs and shard regexes are represented by null or empty values; unreported feature flags use the POC's RAM-only, rack-aware topology."]
    # The recorded SHARDS column says 0 for nodes 3/4 despite listing their shards.
    # Preserve the actual topology, and disclose the source-table discrepancy.
    counts = Counter(shard["node_uid"] for shard in shards)
    for node in nodes:
        if node["shard_count"] != counts[node["uid"]]:
            warnings.append(f"node {node['uid']}: recorded shard_count {node['shard_count']} replaced by {counts[node['uid']]} from the recorded shard table.")
        node["shard_count"] = counts[node["uid"]]
    return {"schema_version": 1, "collected_at": "2026-10-31T00:00:00Z", "source": "fixture",
            "cluster": {"name": "poc-5-nodes", "rs_version": min(versions, key=lambda v: tuple(map(int, re.findall(r"\d+", v)))),
                        "mixed_versions": len(set(versions)) > 1, "rack_aware": True,
                        "default_shards_placement": "sparse", "license": None},
            "nodes": nodes, "bdbs": bdbs, "shards": shards,
            "provenance": {"collector_user_role": None, "partial": False, "partial_reasons": [],
                           "warnings": warnings, "rs_semantics": {"provisional_ram": "pre-8.0"}}}


def main():
    root = Path(__file__).resolve().parents[1]
    poc = root / "legacy" if (root / "legacy/initcapaplan-test.sh").exists() else root
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=poc / "initcapaplan-test.sh")
    parser.add_argument("--out", type=Path, default=root / "tests/fixtures/poc-5-nodes.json")
    args = parser.parse_args()
    snapshot = convert(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
