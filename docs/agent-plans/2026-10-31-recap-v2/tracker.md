# Tracker: recap v2

Statuses: `planning`, `running`, `blocked`, `failed`, `done`, `audited`. A task is `done` only with test output and a commit sha.

| Task | REQ | Status | Commit | Evidence / notes |
|---|---|---|---|---|
| T1 scaffold, units, CLI | REQ-01, SD-1 | done | f77b7b9 | Tests first: 38 failed before package implementation (missing recap package). Editable install succeeded. Focused suite: 38 passed in 1.86s. Whole suite: 38 passed in 1.42s. REQ-01 scenarios 2 and 3 covered; scenario 1 remains assigned to T7. |
| T2 schema, validate, fixtures | REQ-03, SD-2 | done | 3c066af | Tests first: 25 failed, 6 passed before implementation. Focused suite: 37 passed in 3.35s. Whole suite: 75 passed in 4.21s. REQ-03 scenarios: 2/2. Checkpoint reached; awaiting owner review before T3. |
| T3 collector | REQ-02 | done | f712edd | Red: 6 failed. Focused: 6 passed in 1.10s. Whole suite: 81 passed in 3.91s. REQ-02: 4/4 scenarios. |
| T4 capacity model | REQ-04 | done | effde8c | Red: 8 failed. Focused: 8 passed in 0.11s. Whole suite: 89 passed in 4.13s. REQ-04: 3/3 scenarios. |
| T5 constraints | REQ-05 | done | 24321f1 | Red: 7 failed. Focused: 7 passed in 0.11s. Whole suite: 96 passed in 3.69s. REQ-05 scenario 3; scenarios 1/2 and property proof in T7. |
| T6 verifier | REQ-09 | done | d67f1ae | Red: 2 failed. Focused: 2 passed in 0.22s. Whole suite: 98 passed in 4.08s. Injected faulty planner rejected in CLI output path. |
| T7 can-create | REQ-06 | done | a920333 | Red: 4 failed, 1 skipped. Focused: 31 passed, 1 skipped in 1.41s. Whole suite: 102 passed, 1 skipped in 3.99s. P-1 deferred to T12; REQ-01 scenario 1 and REQ-05 regressions/property covered. |
| T8 optimize | REQ-08 | done | d76db69; repair 8b8f3ed | Owner-authorized repair checks the failover intermediate state before considering migration. New regression failed before the fix. Optimize/verifier/upscale/report: 17 passed, 1 skipped in 0.64s. Whole suite: 121 passed, 2 skipped in 7.35s. |
| T9 can-upscale | REQ-07 | done | 2ab792e | Red: 6 failed. Focused: 6 passed in 0.12s. Whole suite: 114 passed, 2 skipped in 5.47s. Credential grep in src: zero matches; golden output not generated until T11. |
| T10 cross-check | REQ-10 | done | cdd08ea | Red: 4 failed. Focused: 4 passed in 0.29s. Whole suite: 118 passed, 2 skipped in 7.76s. REQ-10: 3/3 scenarios; only dry_run request URLs; stale snapshot rejected before HTTP. |
| T11 report | REQ-11 | running | | T8 blocker resolved. Markdown golden generated and reviewed; all report assertions pass. Combined focused proof: 17 passed, 1 skipped in 0.64s. Whole suite: 121 passed, 2 skipped in 7.35s. Commit pending. |
| T12 parity, legacy, CI | P-1, REQ-12 | planning | | |
| T13 audit | all | planning | | fresh session |

Open items, outside the delivery gate: P-2 (lab, owner), D-1, D-2, D-3.

Owner instruction (2026-10-31): continue autonomously through T12, without the T2/T8 checkpoints. Preserve the other coordinator limits; T13 remains a fresh-session audit.

Owner follow-up `go` (2026-10-31): authorizes the diagnosed T8 repair outside T11 ownership, including a corrective commit for an already committed task, then autonomous continuation of T11/T12. The earlier repeated-failure stop is cleared for this repair.

## Integration blocker found during T11 (2026-10-31)

- Reproduction: `pytest tests/test_report.py -q` fails `test_req11_markdown_report`; the subsequent whole-suite run reproduces the same failure. Both executions report `internal-error: plan failed verification at step 1: rack-awareness: database 5 range 0-16383 shares a rack`.
- Root cause: the POC records database 5's master on node 2 and replica on node 5, both on rack `europe-west1-c`. The T2 converter marks the RAM-only POC databases rack-aware, following its global policy. T8's level-2 path checks the migrated state, but omits `violations()` on the intermediate failover state. T9 consequently advertises DB 1's ladder target as `feasible-in-steps`, with `failover 7`, then migration `2 -> 4`. T11's independent replay correctly rejects the first step.
- Required repair: add a regression and a constraint check for the failover intermediate state in T8 (`src/recap/planner/optimize.py`, `tests/test_optimize.py`); reject such candidates without weakening the verifier or changing fixture rack semantics. Then rerun T9/T11 and whole-suite proof. Those files are outside T11 ownership, and T8 already has its one task commit; the coordinator's ownership/one-commit limits and repeated-failure stop require owner direction before rework.
- Protected/unrelated `.DS_Store` files remain untouched. `docs/spec-v2.md` remains unchanged. T12 has not started.

## Owner clarification and T2 evidence (2026-10-31)

- Owner approved the REQ-07 scenario 3 correction in this chat: the 1 GiB and 2 GiB replicas in `upscale-steps.json` belong to databases 2 and 3 respectively, each with a primary of the same size. This overrides the scenario's reference to database 2 for both replicas. `docs/spec-v2.md` stays untouched.
- T2 changed paths: `src/recap/cli.py`, `src/recap/snapshot.py`, `src/recap/schemas/snapshot.v1.json`, `tests/test_snapshot.py`, `tests/fixtures/poc-5-nodes.json`, `tests/fixtures/upscale-steps.json`, `tests/fixtures/densify.json`, `tests/fixtures/no-rack.json`, `tools/convert_poc_fixture.py`, and this tracker.
- The converter preserves the POC's recorded shard topology and converts displayed GB/MB with binary multipliers, rounding fractional bytes to the nearest integer. The recorded SHARDS counts for nodes 3 and 4 are 0 despite each hosting a shard; the fixture derives these counts from the shard table and discloses the discrepancy in provenance warnings. Unknown license and absent metadata are disclosed there too.
- Schema validation enforces RFC 3339 timestamps without adding jsonschema's optional format dependencies. Referential checks cover missing nodes, missing databases and exactly one master/replica per replicated slot range. Partial input requires explicit `--allow-partial`.
- Downstream fixture impact: all four snapshots load and validate; deterministic POC conversion reproduces the committed fixture; synthetic topology assertions pass. T3 is the next task after the owner's T2 checkpoint review. No live cluster calls; no push or merge.
