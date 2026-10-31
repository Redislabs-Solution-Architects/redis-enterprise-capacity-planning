"""REQ-01 subprocess acceptance and CLI scaffold contracts."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


def run(*args):
    return subprocess.run([sys.executable, "-m", "recap.cli", *args], capture_output=True, text=True)


def test_req01_bare_memory_rejected():
    """Given: any valid snapshot
    When: `recap can-create --snapshot s.json --memory 50 --shards 2`
    Then: exit 2, and stderr names the accepted unit suffixes.
    """
    result = run("can-create", "--snapshot", "s.json", "--memory", "50", "--shards", "2")
    assert result.returncode == 2
    for suffix in ("B", "KiB", "MiB", "GiB", "TiB", "KB", "MB", "GB", "TB", "G"):
        assert suffix in result.stderr


def test_req01_old_sentinel_rejected():
    """Given: any valid snapshot
    When: `recap optimize node --snapshot s.json --node 3 --shard-used-max -1`
    Then: exit 2, and stderr suggests `--shard-used-max none`.
    """
    result = run("optimize", "node", "--snapshot", "s.json", "--node", "3", "--shard-used-max", "-1")
    assert result.returncode == 2
    assert "--shard-used-max none" in result.stderr


@pytest.mark.parametrize("verdict,code", [
    ("ok", 0), ("feasible", 0), ("feasible-in-steps", 0), ("goal-met", 0),
    ("infeasible", 1), ("goal-not-met", 1), ("no-plan", 1),
])
def test_req01_verdict_exit_codes(verdict, code):
    from recap.cli import Verdict, exit_code
    assert exit_code(Verdict(verdict)) == code


def test_req01_partial_output_schema(capsys):
    from recap.cli import emit
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).parents[1] / "src/recap/schemas/output.v1.json").read_text())
    snapshot = {"source": "fixture", "collected_at": "2026-10-31T00:00:00Z", "provenance": {"partial": True}}
    assert emit("capacity", "ok", snapshot, output_format="json") == 0
    output = json.loads(capsys.readouterr().out)
    Draft202012Validator(schema).validate(output)
    assert output["partial"] is True
    assert output["snapshot"]["source"] == "fixture"
    emit("capacity", "ok", snapshot)
    assert capsys.readouterr().out.startswith("PARTIAL: ok")
    invalid = dict(output, verdict="maybe")
    assert not Draft202012Validator(schema).is_valid(invalid)
    assert not Draft202012Validator(schema).is_valid(dict(output, verdict="infeasible", reasons=[]))


@pytest.mark.parametrize("command", ["collect", "capacity", "can-create", "can-upscale", "optimize", "report", "snapshot", "cross-check"])
def test_req01_subcommand_help(command):
    assert run(command, "--help").returncode == 0


def test_req01_unimplemented_handler():
    result = run("can-create", "--snapshot", "-", "--memory", "50GiB", "--shards", "2")
    assert result.returncode == 2
    assert "not implemented" in result.stderr


def test_req01_relative_only_for_upscale():
    result = run("can-upscale", "--snapshot", "-", "--db", "1", "--memory", "+10GiB")
    assert result.returncode == 2
    assert "not implemented" in result.stderr
    result = run("can-create", "--snapshot", "-", "--memory", "+10GiB", "--shards", "2")
    assert result.returncode == 2
    assert "not implemented" not in result.stderr
