# Development and verification

## Local setup

Use Python 3.10 or later from the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

Runtime dependencies are `httpx` and `jsonschema`. Tests additionally use `pytest`,
`hypothesis` and `respx`. Network-facing tests use HTTP fixtures; ordinary test runs
need no cluster credentials or Redis instance.

## Source layout

| Path | Responsibility |
|---|---|
| `src/recap/cli.py` | CLI parsing, verdicts, formatting and verification before output |
| `src/recap/collect.py` | Read-only REST snapshot collection |
| `src/recap/snapshot.py`, `schemas/` | Snapshot loading, validation and public JSON contracts |
| `src/recap/model.py`, `constraints.py` | Capacity bounds and shared placement constraints |
| `src/recap/planner/` | Create, upscale and optimization simulation |
| `src/recap/verifier.py` | Independent replay and final-goal checks |
| `src/recap/render.py`, `report.py` | Exported commands and capacity reports |
| `tests/fixtures/`, `tests/golden/` | Offline examples, recorded HTTP/POC cases and expected report output |
| `legacy/` | Unchanged retired POC engine and initialization scripts |

## Fixtures and report output

Use `no-rack.json`, `upscale-steps.json` and `densify.json` for focused walkthroughs.
The historical five-node POC fixture includes an existing same-rack primary/replica
pair; its create and planning answers can differ from a clean synthetic cluster.

The report golden is `tests/golden/report-poc.md`. Update it only when the intended
output changes and review the resulting diff. See `tests/test_audit_regressions.py`
for partial visibility, per-node growth reservation and CLI output regressions.

## Reproduce historical POC comparisons

Only this optional generation step needs Redis 8.x and `redis-cli` available locally:

```bash
bash tools/gen_poc_parity.sh
pytest tests/test_parity.py -q
```

The harness starts its own temporary Redis on `127.0.0.1:6390`, checks ownership
and readiness, and shuts it down with `shutdown nosave`. It refuses an occupied
port. A sandbox may need explicit permission to bind that loopback port.
The normal application never opens a Redis connection.

The committed record has 16 cases. Nine F-8 divergences are explained by an
existing same-rack pair in the historical fixture and stricter per-database checks.
Each divergent case contains a counterfactual proof: changing only the offending
DB's rack policy in memory makes that exact case match the POC. Tests recompute
those verdicts/move lists and replay the plans. This does not alter the real fixture
or establish correctness against a live cluster.

`tools/convert_poc_fixture.py` reproduces the five-node JSON from the recorded
`legacy/initcapaplan-test.sh` tables without executing that shell script. Its
conversion treats displayed rladmin GB/MB as binary and rounds fractional bytes.

## CI and publication hygiene

CI runs pytest on Python 3.10, 3.12 and 3.14. It checks that the runtime has no
`redis-cli`, `EVAL` or `flushdb` references and that source/golden output contains
no embedded historical cluster identity. The parity record is committed, so CI
does not start Redis.

Local planning documents are ignored and are not part of the published repository.
Keep cluster snapshots, credentials and customer-specific material outside the
checkout. User documentation belongs under `docs/`; the README links its entry points.
