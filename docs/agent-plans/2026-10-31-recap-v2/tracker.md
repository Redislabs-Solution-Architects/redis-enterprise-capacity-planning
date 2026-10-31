# Tracker: recap v2

Statuses: `planning`, `running`, `blocked`, `failed`, `done`, `audited`. A task is `done` only with test output and a commit sha.

| Task | REQ | Status | Commit | Evidence / notes |
|---|---|---|---|---|
| T1 scaffold, units, CLI | REQ-01, SD-1 | done | f77b7b9 | Tests first: 38 failed before package implementation (missing recap package). Editable install succeeded. Focused suite: 38 passed in 1.86s. Whole suite: 38 passed in 1.42s. REQ-01 scenarios 2 and 3 covered; scenario 1 subsequently completed by T7. |
| T2 schema, validate, fixtures | REQ-03, SD-2 | done | 3c066af | Tests first: 25 failed, 6 passed before implementation. Focused suite: 37 passed in 3.35s. Whole suite: 75 passed in 4.21s. REQ-03 scenarios: 2/2. Checkpoint waived by owner. T12 adapts the converter's source locator after the authorized legacy move. |
| T3 collector | REQ-02 | done | f712edd | Red: 6 failed. Focused: 6 passed in 1.10s. Whole suite: 81 passed in 3.91s. REQ-02: 4/4 scenarios. |
| T4 capacity model | REQ-04 | done | effde8c | Red: 8 failed. Focused: 8 passed in 0.11s. Whole suite: 89 passed in 4.13s. REQ-04: 3/3 scenarios. |
| T5 constraints | REQ-05 | done | 24321f1 | Red: 7 failed. Focused: 7 passed in 0.11s. Whole suite: 96 passed in 3.69s. REQ-05 scenario 3; scenarios 1/2 and property proof in T7. |
| T6 verifier | REQ-09 | done | d67f1ae | Red: 2 failed. Focused: 2 passed in 0.22s. Whole suite: 98 passed in 4.08s. Injected faulty planner rejected in CLI output path. |
| T7 can-create | REQ-06 | done | a920333 | Red: 4 failed, 1 skipped. Focused: 31 passed, 1 skipped in 1.41s. Whole suite: 102 passed, 1 skipped in 3.99s. P-1 deferred to T12; REQ-01 scenario 1 and REQ-05 regressions/property covered. |
| T8 optimize | REQ-08 | done | d76db69; repair 8b8f3ed | Owner-authorized repair checks the failover intermediate state before considering migration. New regression failed before the fix. Optimize/verifier/upscale/report: 17 passed, 1 skipped in 0.64s. Whole suite: 121 passed, 2 skipped in 7.35s. |
| T9 can-upscale | REQ-07 | done | 2ab792e | Red: 6 failed. Focused: 6 passed in 0.12s. Whole suite: 114 passed, 2 skipped in 5.47s. Credential grep in src: zero matches; golden output not generated until T11. |
| T10 cross-check | REQ-10 | done | cdd08ea | Red: 4 failed. Focused: 4 passed in 0.29s. Whole suite: 118 passed, 2 skipped in 7.76s. REQ-10: 3/3 scenarios; only dry_run request URLs; stale snapshot rejected before HTTP. |
| T11 report | REQ-11 | done | 5a71fc9 | T8 blocker resolved. Markdown golden generated and reviewed; all report assertions pass. Combined focused proof: 17 passed, 1 skipped in 0.64s. Whole suite: 121 passed, 2 skipped in 7.35s. |
| T12 parity, legacy, CI | P-1, REQ-12 | running | | Ready to commit. P-1: 16 cases on Redis 8.10.2; F-8: 9 divergences. Final whole suite: 125 passed in 4.40s, zero skips. Both source/golden greps clean. Legacy moved byte-for-byte; converter source locator adapted and tested. |
| T13 audit | all | planning | | fresh session |

Open items, outside the delivery gate: P-2 (lab, owner), D-1, D-2, D-3.

Owner instruction (2026-10-31): continue autonomously through T12, without the T2/T8 checkpoints. Preserve the other coordinator limits; T13 remains a fresh-session audit.

Owner follow-up `go` (2026-10-31): authorizes the diagnosed T8 repair outside T11 ownership, including a corrective commit for an already committed task, then autonomous continuation of T11/T12. The earlier repeated-failure stop is cleared for this repair.

Owner follow-up `go` after the sandbox explanation (2026-10-31): explicitly authorizes the P-1 harness outside the sandbox to bind only its dedicated scratch Redis on 127.0.0.1:6390 and shut it down with `shutdown nosave`.

## T12 final verification (2026-10-31)

- P-1 generation succeeded before and after the legacy move: 16 recorded cases (3 CAPA sizes, 4 CANCREATE rungs, 4 replicated-database upscale targets, 5 level-1 node optimizations). Actual Redis version: 8.10.2. Both harness runs returned 0, after readiness and ownership checks, with automatic `shutdown nosave` teardown. A post-run localhost ping confirmed connection refused after the first run.
- Divergences: F-8 = 9; all other allowed classes = 0. Each divergent case records the original arguments/output and explains the existing DB 5 primary/replica pair on the same rack and the stricter per-database constraint checks. This is fixture parity evidence, not live RS qualification. The independent T13 audit must assess the classifications.
- Focused P-1/create/optimize verification: `15 passed in 0.22s`. Final complete suite after the legacy move: `125 passed in 4.40s`; zero skips. The former T7/T8 P-1 skips are now resolved.
- Both CI grep gates ran locally and returned no matches (expected grep status 1, wrapper status 0): `redis-cli|EVAL|flushdb` in `src/`; `admin@admin.com|dev-pierre-lab` in `src/` and `tests/golden/`. `git diff --check` passed. GitHub-hosted CI itself has not run; no push is authorized.
- Legacy move: `lua/capaplan.lua` and the three `initcapaplan-*.sh` files moved under `legacy/`, each detected by Git as a 100% identical rename, with zero line changes. They are retained under T12's explicit move-only contract. The converter's default source locator now resolves `legacy/initcapaplan-test.sh`; its existing round-trip test failed immediately after the move, then passed after this mechanical integration repair. No other T2 behavior changed.
- T12 changed paths: `README.md`, `.github/workflows/ci.yml`, `tools/gen_poc_parity.sh`, `tools/convert_poc_fixture.py`, `tests/test_parity.py`, `tests/fixtures/poc-parity.json`, the four legacy renames, and this tracker. Unrelated `.DS_Store` files and `docs/spec-v2.md` remain untouched.
- Delivery boundary: implementation through T12; T13 audit NOT RUN, verdict NOT APPROVED. P-2, D-1, D-2 and D-3 remain open. No push, merge, or live cluster request.

## Integration blocker found during T11 (2026-10-31)

Resolved by owner-authorized corrective commit `8b8f3ed`; T11 committed as `5a71fc9`. The following records preserve the original diagnosis.

- Reproduction: `pytest tests/test_report.py -q` fails `test_req11_markdown_report`; the subsequent whole-suite run reproduces the same failure. Both executions report `internal-error: plan failed verification at step 1: rack-awareness: database 5 range 0-16383 shares a rack`.
- Root cause: the POC records database 5's master on node 2 and replica on node 5, both on rack `europe-west1-c`. The T2 converter marks the RAM-only POC databases rack-aware, following its global policy. T8's level-2 path checks the migrated state, but omits `violations()` on the intermediate failover state. T9 consequently advertises DB 1's ladder target as `feasible-in-steps`, with `failover 7`, then migration `2 -> 4`. T11's independent replay correctly rejects the first step.
- Required repair: add a regression and a constraint check for the failover intermediate state in T8 (`src/recap/planner/optimize.py`, `tests/test_optimize.py`); reject such candidates without weakening the verifier or changing fixture rack semantics. Then rerun T9/T11 and whole-suite proof. Those files are outside T11 ownership, and T8 already has its one task commit; the coordinator's ownership/one-commit limits and repeated-failure stop require owner direction before rework.
- Protected/unrelated `.DS_Store` files remain untouched. `docs/spec-v2.md` remains unchanged. T12 has not started.

## T12 environment blocker (2026-10-31)

Resolved: the owner explicitly authorized running the parity harness outside the sandbox. The permitted rerun succeeded; the following bullets preserve the original blocked-state evidence.

- Installed server version: `Redis server v=8.10.2`. `bash -n tools/gen_poc_parity.sh` passed.
- Tests first: `pytest tests/test_parity.py -q` produced `1 failed, 1 passed in 0.14s`; the failing P-1 test requires the not-yet-generated `tests/fixtures/poc-parity.json`, while REQ-12's source scan passed.
- `bash tools/gen_poc_parity.sh` started only its dedicated scratch server and failed immediately with `Could not create server TCP listening socket 127.0.0.1:6390: bind: Operation not permitted`, followed by `BLOCKED: port bind`; exit 2. The server exited before readiness, so no shutdown command was sent to any other process. No cluster calls were made.
- Uncommitted T12 work: `tools/gen_poc_parity.sh`, `tests/test_parity.py`, `.github/workflows/ci.yml`, README v2 usage updates, and tracker evidence. The harness checks ownership before shutdown, uses `shutdown nosave` for its own ready server, and records POC CAPA/create/upscale/node-optimize cases when binding is permitted. CI is prepared but not executed or qualified; the parity file is absent.
- Legacy files remain in their original locations. No legacy move/deletion, T12 commit, push, merge, or T13 audit occurred. P-1 divergence counts are unavailable. P-2, D-1, D-2, D-3 remain open.
- Last full-suite proof before adding the T12 tests: `121 passed, 2 skipped in 7.35s`. The two skipped P-1 comparisons remain pending; current T12 verification is blocked and is not claimed green.

## Owner clarification and T2 evidence (2026-10-31)

- Owner approved the REQ-07 scenario 3 correction in this chat: the 1 GiB and 2 GiB replicas in `upscale-steps.json` belong to databases 2 and 3 respectively, each with a primary of the same size. This overrides the scenario's reference to database 2 for both replicas. `docs/spec-v2.md` stays untouched.
- T2 changed paths: `src/recap/cli.py`, `src/recap/snapshot.py`, `src/recap/schemas/snapshot.v1.json`, `tests/test_snapshot.py`, `tests/fixtures/poc-5-nodes.json`, `tests/fixtures/upscale-steps.json`, `tests/fixtures/densify.json`, `tests/fixtures/no-rack.json`, `tools/convert_poc_fixture.py`, and this tracker.
- The converter preserves the POC's recorded shard topology and converts displayed GB/MB with binary multipliers, rounding fractional bytes to the nearest integer. The recorded SHARDS counts for nodes 3 and 4 are 0 despite each hosting a shard; the fixture derives these counts from the shard table and discloses the discrepancy in provenance warnings. Unknown license and absent metadata are disclosed there too.
- Schema validation enforces RFC 3339 timestamps without adding jsonschema's optional format dependencies. Referential checks cover missing nodes, missing databases and exactly one master/replica per replicated slot range. Partial input requires explicit `--allow-partial`.
- Downstream fixture impact: all four snapshots load and validate; deterministic POC conversion reproduces the committed fixture; synthetic topology assertions pass. T3 is the next task after the owner's T2 checkpoint review. No live cluster calls; no push or merge.
