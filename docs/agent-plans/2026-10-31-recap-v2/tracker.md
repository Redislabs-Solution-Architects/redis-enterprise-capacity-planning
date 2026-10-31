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
| T8 optimize | REQ-08 | done | d76db69 | Red: 6 failed, 1 skipped. Focused optimize + verifier: 8 passed, 1 skipped in 0.20s. Whole suite: 108 passed, 2 skipped in 3.78s. P-1 deferred to T12; checkpoint waived by owner. |
| T9 can-upscale | REQ-07 | done | 2ab792e | Red: 6 failed. Focused: 6 passed in 0.12s. Whole suite: 114 passed, 2 skipped in 5.47s. Credential grep in src: zero matches; golden output not generated until T11. |
| T10 cross-check | REQ-10 | running | | Tests-first implementation in progress. |
| T11 report | REQ-11 | planning | | |
| T12 parity, legacy, CI | P-1, REQ-12 | planning | | |
| T13 audit | all | planning | | fresh session |

Open items, outside the delivery gate: P-2 (lab, owner), D-1, D-2, D-3.

Owner instruction (2026-10-31): continue autonomously through T12, without the T2/T8 checkpoints. Preserve the other coordinator limits; T13 remains a fresh-session audit.

## Owner clarification and T2 evidence (2026-10-31)

- Owner approved the REQ-07 scenario 3 correction in this chat: the 1 GiB and 2 GiB replicas in `upscale-steps.json` belong to databases 2 and 3 respectively, each with a primary of the same size. This overrides the scenario's reference to database 2 for both replicas. `docs/spec-v2.md` stays untouched.
- T2 changed paths: `src/recap/cli.py`, `src/recap/snapshot.py`, `src/recap/schemas/snapshot.v1.json`, `tests/test_snapshot.py`, `tests/fixtures/poc-5-nodes.json`, `tests/fixtures/upscale-steps.json`, `tests/fixtures/densify.json`, `tests/fixtures/no-rack.json`, `tools/convert_poc_fixture.py`, and this tracker.
- The converter preserves the POC's recorded shard topology and converts displayed GB/MB with binary multipliers, rounding fractional bytes to the nearest integer. The recorded SHARDS counts for nodes 3 and 4 are 0 despite each hosting a shard; the fixture derives these counts from the shard table and discloses the discrepancy in provenance warnings. Unknown license and absent metadata are disclosed there too.
- Schema validation enforces RFC 3339 timestamps without adding jsonschema's optional format dependencies. Referential checks cover missing nodes, missing databases and exactly one master/replica per replicated slot range. Partial input requires explicit `--allow-partial`.
- Downstream fixture impact: all four snapshots load and validate; deterministic POC conversion reproduces the committed fixture; synthetic topology assertions pass. T3 is the next task after the owner's T2 checkpoint review. No live cluster calls; no push or merge.
