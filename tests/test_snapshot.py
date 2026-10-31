"""REQ-03 acceptance, SD-2 validation and consuming-fixture contracts."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
GIB = 2**30


def read_fixture(name="poc-5-nodes"):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def run_validate(path, *flags, stdin=None):
    return subprocess.run(
        [sys.executable, "-m", "recap.cli", "snapshot", "validate", "--snapshot", str(path), *flags],
        input=stdin, text=True, capture_output=True,
    )


def test_req03_poc_snapshot_validates():
    """Given: `tests/fixtures/poc-5-nodes.json`
    When: `recap snapshot validate --snapshot tests/fixtures/poc-5-nodes.json`
    Then: exit 0.
    """
    result = run_validate(FIXTURES / "poc-5-nodes.json")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_req03_missing_node_reports_path(tmp_path):
    """Given: the same fixture with one shard's `node_uid` set to a node that does not exist
    When: `recap snapshot validate ...`
    Then: exit 2, and the violation names `shards[<i>].node_uid`.
    """
    snapshot = read_fixture()
    snapshot["shards"][0]["node_uid"] = 999
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(snapshot))
    result = run_validate(path)
    assert result.returncode == 2
    assert "shards[0].node_uid" in result.stderr
    assert not result.stdout


def test_req03_lists_all_reference_and_pair_violations(tmp_path):
    snapshot = read_fixture()
    snapshot["shards"][0]["node_uid"] = 999
    snapshot["shards"][2]["bdb_uid"] = 999
    snapshot["shards"][1]["role"] = "master"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(snapshot))
    result = run_validate(path)
    assert result.returncode == 2
    for text in ("shards[0].node_uid", "shards[2].bdb_uid", "slots", "one master and one replica"):
        assert text in result.stderr


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "different-slots", "empty"])
def test_req03_replicated_slot_pair_invariant(mutation):
    from recap.snapshot import validate
    snapshot = read_fixture()
    if mutation == "missing":
        snapshot["shards"].pop(1)
    elif mutation == "duplicate":
        duplicate = deepcopy(snapshot["shards"][1])
        duplicate["uid"] = 999
        snapshot["shards"].append(duplicate)
    elif mutation == "different-slots":
        snapshot["shards"][1]["slots"] = "0-8191"
    else:
        snapshot["shards"] = [s for s in snapshot["shards"] if s["bdb_uid"] != 1]
    assert any("one master and one replica" in error for error in validate(snapshot))


def test_req03_nonreplicated_database_has_no_pair_requirement():
    from recap.snapshot import validate
    snapshot = read_fixture()
    snapshot["bdbs"][0]["replication"] = False
    snapshot["shards"].pop(1)
    assert validate(snapshot) == []


@pytest.mark.parametrize("name", ["upscale-steps", "densify", "no-rack"])
def test_req03_synthetic_schema_and_uniform_pair_sizes(name):
    from recap.snapshot import validate
    snapshot = read_fixture(name)
    assert validate(snapshot) == []
    assert run_validate(FIXTURES / f"{name}.json").returncode == 0
    for db in snapshot["bdbs"]:
        shards = [s for s in snapshot["shards"] if s["bdb_uid"] == db["uid"]]
        assert len(shards) == db["shards_count"] * (2 if db["replication"] else 1)
    for node in snapshot["nodes"]:
        assert node["shard_count"] == sum(s["node_uid"] == node["uid"] for s in snapshot["shards"])


def test_req03_upscale_steps_topology():
    """REQ-07 scenario 3, with the owner's 2026-10-31 distinct-database correction."""
    snapshot = read_fixture("upscale-steps")
    dbs = {db["uid"]: db for db in snapshot["bdbs"]}
    nodes = {n["uid"]: n for n in snapshot["nodes"]}
    master = next(s for s in snapshot["shards"] if s["bdb_uid"] == 1 and s["role"] == "master")
    assert nodes[master["node_uid"]]["provisional_ram"] == 0  # +4 GiB needs +2 per copy.
    movable = [s for s in snapshot["shards"] if s["node_uid"] == master["node_uid"] and s["role"] == "replica"]
    assert len(movable) == 2
    assert len({s["bdb_uid"] for s in movable}) == 2
    sizes = [dbs[s["bdb_uid"]]["memory_size"] // (2 * dbs[s["bdb_uid"]]["shards_count"]) for s in movable]
    assert sorted(sizes) == [GIB, 2 * GIB]
    assert all(s["bdb_uid"] != 1 for s in movable)
    destination = next(n for n in nodes.values() if n["uid"] != master["node_uid"] and n["provisional_ram"] >= 3 * GIB)
    assert destination["max_redis_servers"] - destination["shard_count"] >= 2
    assert nodes[master["node_uid"]]["rack_id"] != destination["rack_id"]


def test_req03_densify_topology():
    snapshot = read_fixture("densify")
    target = next(n for n in snapshot["nodes"] if n["provisional_ram"] == 5 * GIB // 2)
    dbs = {db["uid"]: db for db in snapshot["bdbs"]}
    assert 0 < target["shard_count"] < target["max_redis_servers"] - 1
    reserve = max(db["memory_size"] // (db["shards_count"] * (2 if db["replication"] else 1)) for db in dbs.values())
    assert reserve > target["provisional_ram"]
    replicas = [s for s in snapshot["shards"] if s["role"] == "replica" and s["node_uid"] != target["uid"]]
    assert len(replicas) == 5
    nodes = {n["uid"]: n for n in snapshot["nodes"]}
    for replica in replicas:
        assert dbs[replica["bdb_uid"]]["memory_size"] == 2 * GIB
        master = next(s for s in snapshot["shards"] if s["bdb_uid"] == replica["bdb_uid"] and s["role"] == "master")
        assert nodes[master["node_uid"]]["rack_id"] != target["rack_id"]


def test_req03_no_rack_topology():
    snapshot = read_fixture("no-rack")
    assert len(snapshot["nodes"]) == 3
    assert all(n["rack_id"] is None and n["second_rack_id"] is None for n in snapshot["nodes"])
    assert not snapshot["cluster"]["rack_aware"]
    db = snapshot["bdbs"][0]
    assert db["memory_size"] == 2 * GIB and db["shards_count"] == 1
    assert {(s["node_uid"], s["role"]) for s in snapshot["shards"]} == {(1, "replica"), (3, "master")}
    assert snapshot["nodes"][1]["provisional_ram"] == 10 * GIB


def test_req03_converter_reproduces_binary_topology(tmp_path):
    output = tmp_path / "converted.json"
    result = subprocess.run([sys.executable, str(ROOT / "tools/convert_poc_fixture.py"), "--out", str(output)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    snapshot = json.loads(output.read_text())
    assert snapshot == read_fixture()
    assert len(snapshot["nodes"]) == 5
    assert {n["rack_id"] for n in snapshot["nodes"]} == {"europe-west1-b", "europe-west1-c", "europe-west1-d"}
    assert snapshot["cluster"]["rs_version"] == "6.2.10-100"
    assert {db["uid"]: db["memory_size"] for db in snapshot["bdbs"]} == {1: 2 * GIB, 2: 50 * GIB, 4: 10 * GIB, 5: 10 * GIB}
    assert [n["provisional_ram"] for n in snapshot["nodes"]] == [int((Decimal(x) * GIB).to_integral_value()) for x in ("43.39", "43.55", "24.49", "24.49", "39.6")]
    assert [(s["bdb_uid"], s["node_uid"], s["role"]) for s in snapshot["shards"]] == [
        (1, 1, "master"), (1, 2, "replica"), (2, 3, "master"), (2, 4, "replica"),
        (4, 5, "master"), (4, 1, "replica"), (5, 2, "master"), (5, 5, "replica"),
    ]
    expected_used = ("14.72", "14.6", "58.72", "58.6", "58.01", "57.97", "58.09", "58.05")
    assert [s["used_memory"] for s in snapshot["shards"]] == [int((Decimal(x) * 2**20).to_integral_value()) for x in expected_used]
    assert all(s["slots"] == "0-16383" for s in snapshot["shards"])


@pytest.mark.parametrize("section", [None, "cluster", "nodes", "bdbs", "shards", "provenance"])
def test_sd2_required_fields(section):
    from recap.snapshot import validate
    snapshot = read_fixture()
    container = snapshot if section is None else snapshot[section]
    if isinstance(container, list):
        container = container[0]
    for key in list(container):
        if key == "license" or section != "cluster" or key in ("name", "rs_version", "mixed_versions", "rack_aware", "default_shards_placement"):
            mutated = deepcopy(snapshot)
            target = mutated if section is None else mutated[section]
            if isinstance(target, list):
                target = target[0]
            del target[key]
            errors = validate(mutated)
            assert any(key in error for error in errors), (section, key, errors)


@pytest.mark.parametrize("field,value", [("collected_at", "yesterday"), ("schema_version", 2), ("source", "other")])
def test_sd2_invalid_metadata(field, value):
    from recap.snapshot import validate
    snapshot = read_fixture()
    snapshot[field] = value
    assert any(field in error for error in validate(snapshot))


@pytest.mark.parametrize("timestamp,valid", [
    ("2026-10-31T12:34:56Z", True), ("2026-10-31t12:34:56z", True),
    ("2026-10-31T12:34:56.123+01:00", True),
    ("2026-10-31T12:34:56", False), ("2026-02-30T00:00:00Z", False),
    ("2026-10-31", False),
])
def test_sd2_rfc3339_timestamp(timestamp, valid):
    from recap.snapshot import validate
    snapshot = read_fixture()
    snapshot["collected_at"] = timestamp
    assert (validate(snapshot) == []) is valid


def test_req03_stdin_json_and_partial_policy():
    snapshot = read_fixture()
    result = run_validate("-", "--format", "json", stdin=json.dumps(snapshot))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["verdict"] == "ok"
    snapshot["provenance"]["partial"] = True
    snapshot["provenance"]["partial_reasons"] = ["scoped visibility"]
    result = run_validate("-", stdin=json.dumps(snapshot))
    assert result.returncode == 2
    assert "--allow-partial" in result.stderr
    result = run_validate("-", "--allow-partial", stdin=json.dumps(snapshot))
    assert result.returncode == 0
    assert result.stdout.startswith("PARTIAL: ok")
    result = run_validate("-", "--allow-partial", "--format", "json", stdin=json.dumps(snapshot))
    assert json.loads(result.stdout)["partial"] is True


@pytest.mark.parametrize("content", ["{broken", "null", "[]", "{}", '{"nodes": false}'])
def test_req03_malformed_input_is_usage_error(content):
    result = run_validate("-", stdin=content)
    assert result.returncode == 2
    assert result.stderr and "Traceback" not in result.stderr


def test_req03_unreadable_file_is_usage_error(tmp_path):
    result = run_validate(tmp_path / "missing.json")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
