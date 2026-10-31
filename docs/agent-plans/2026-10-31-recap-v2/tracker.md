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
| T12 parity, legacy, CI | P-1, REQ-12 | done | bf6643b | P-1: 16 cases on Redis 8.10.2; F-8: 9 divergences. Final whole suite: 125 passed in 4.40s, zero skips. Both source/golden greps clean. Legacy moved byte-for-byte; converter source locator adapted and tested. T13 fresh-session audit is next. |
| T13 audit | all | audited | repairs 1788921, d508e4a; audit read-only | APPROVED for bounded offline T13 scope at d508e4aff533642981a0556f13f3fa5179004c7e. Independent final proof: 146 passed in 5.18s, zero skips; both greps exit 1 with no matches. All four reproduced defects resolved. P-2/D-1/D-2/D-3 and the legacy deletion boundary remain open. See final audit receipt. |

Open items, outside the delivery gate: P-2 (lab, owner), D-1, D-2, D-3.

Owner publication instruction (2026-10-31): `commit, push , merge`. This explicitly supersedes the earlier no-push/no-merge execution boundary for the completed recap v2 work. Commit the final T13 approval receipt, publish `feat/recap-v2`, and integrate it into the repository's default branch through normal required checks. Preserve unrelated `.DS_Store` files and do not resolve the remaining product decisions or delete retained legacy code.

Owner instruction (2026-10-31): continue autonomously through T12, without the T2/T8 checkpoints. Preserve the other coordinator limits; T13 remains a fresh-session audit.

Owner follow-up `go` (2026-10-31): authorizes the diagnosed T8 repair outside T11 ownership, including a corrective commit for an already committed task, then autonomous continuation of T11/T12. The earlier repeated-failure stop is cleared for this repair.

Owner follow-up `go` after the sandbox explanation (2026-10-31): explicitly authorizes the P-1 harness outside the sandbox to bind only its dedicated scratch Redis on 127.0.0.1:6390 and shut it down with `shutdown nosave`.

## T13 independent audit (2026-10-31)

Historical first audit; subsequent owner-authorized remediation and re-audit receipts follow below.

**Verdict: CHANGES_REQUIRED.** Audited HEAD: `bf6643b77e34408c496db30a75114865ac6bd2b7`, branch `feat/recap-v2`. Auditor: `t13_independent_audit`, fresh context without implementation chat history. No source/test changes, commits, pushes, merges, live calls, Redis startup or P-1 regeneration during this audit. Task completion receipts above record implementation history, not delivery approval.

### Verification and preservation

- Independent command: `rtk proxy .venv/bin/pytest -q` → `125 passed in 4.45s`, zero skips.
- `grep -rE 'redis-cli|EVAL|flushdb' src/` → exit 1, empty output.
- `grep -rE 'admin@admin.com|dev-pierre-lab' src/ tests/golden/` → exit 1, empty output. Both mean no matches, not tool errors.
- Coordinator independently reproduced all three findings using bounded Python/respx calls, without editing files. The verified alternative for finding 1 passes the existing independent verifier.
- Before/after digest for the 51 tracked files excluding this tracker is identical: SHA-256 `6cd05ee7933b6233c28317dc0073dfd4ef76886773ed5414aad3f192434687f7`. Dirty tracker and unrelated `.DS_Store` files were preserved. GitHub-hosted CI and other Python versions were not run.

### Required findings

1. **[P1] REQ-07 — feasible upscale incorrectly refused.** Sources: `src/recap/planner/upscale.py:73`, `:90`; `src/recap/planner/optimize.py:78`. Starting from `upscale-steps.json`, set node 1 free RAM to 1 GiB, node 2 to 4 GiB, and append a copy of node 3 as node 4/rack-d with 3 GiB free and zero shards. The snapshot validates. `can-upscale --snapshot - --db 1 --memory +8GiB --format json` returns exit 1, `infeasible`, `ram: node 1 over capacity`. A valid alternative is migrate shard 4 from node 1 to 4, migrate shard 6 from node 1 to 4, then set DB 1 memory to 10 GiB. The verifier accepts every step and the final goal; final free RAM is `[0, 0, 10, 0] GiB`, with DB 1's own shards unmoved. **Fix:** make migration planning preserve each target-host node's required upscale growth RAM and explore alternative eligible destinations when the preferred destination consumes it. Add this verified feasible alternative as a regression.

2. **[P1] REQ-02/REQ-03 — partial collection output cannot be consumed with the documented opt-in.** Sources: `src/recap/collect.py:91`, `src/recap/snapshot.py:60`, `:78`. Mock `collect-8.2.json`, replacing `/v1/shards` with its first four entries (`[:-2]`, as in the existing collection test). `collect --allow-partial` exits 0; piping that JSON into `capacity --snapshot - --allow-partial --format json` exits 2 with `bdbs[2].shards_count: replicated database 3 requires one master and one replica per slot range; no shards found`. Full reference/pair validation runs before the partial opt-in. The documented invisible-database-reference condition is similarly unconditionally rejected. **Fix:** reconcile partial visibility and referential/pair checks, keep complete-snapshot validation strict, conservatively represent unknown information and add collect-to-compute round-trip coverage. The current opt-in test only checks metadata and request counts.

3. **[P2] REQ-10 — RS and recap can evaluate different create questions.** Source: `src/recap/crosscheck.py:28`. With a fresh `no-rack.json` and mocked create dry-run, run `cross-check ... can-create --memory 2GiB --shards 1 --replication --rack-aware --placement dense`. The actual request body is `{"memory_size":2147483648,"shards_count":1,"replication":true}`; the local planner receives explicit rack awareness and dense placement, but RS receives neither. **Fix:** send the same resolved rack-awareness and placement settings in the dry-run payload, including defaults, and assert the body in HTTP tests.

### Acceptance coverage

All 31 acceptance scenarios have corresponding Given/When/Then docstrings. The owner-approved distinct-database correction to REQ-07 scenario 3 is documented and tested. Some test bodies do not assert every behavior stated in those docstrings.

| REQ | Scenarios | Evidence / limits |
|---|---:|---|
| REQ-01 | 3/3 | Subprocess JSON/schema/verdict and invalid-input assertions; verdict mapping table present. |
| REQ-02 | 4/4 | CLI-handler HTTP-fixture tests cover complete collection, partial refusal, Flex and 401. Partial opt-in consumption is missing and fails the round trip above. |
| REQ-03 | 2/2 | Subprocess validation/path assertions, deterministic converter and synthetic topologies. |
| REQ-04 | 3/3 | Direct model checks for slots, license and old-version unknown RAM, permitted by its unit strategy; scenario tests do not exercise CLI display. |
| REQ-05 | 3/3 | Four-rack/no-replication/per-database regressions. Create property test varies topology; optimize property varies only one node's RAM in a fixed topology. |
| REQ-06 | 2/2 | Planner-level P-1 and insufficient-RAM tests; scenario-specific CLI exit assertions absent. |
| REQ-07 | 4/4 | Planner-level growth, summed growth, preliminary migrations and unsupported-target checks. Specified CLI exits not asserted in these scenario tests. Scenario 3 calls verifier; independent grep covers forbidden strings. |
| REQ-08 | 4/4 | Planner-level P-1/densify/no-rack/own-shard tests; scenario-specific CLI exits absent. Replay and parity role checks present. |
| REQ-09 | 1/1 | Faulty planner injected into CLI; asserts exit 5, step-1 message and empty stdout. |
| REQ-10 | 3/3 | CLI-handler divergence/version/permission cases and stale-before-HTTP; request-body equivalence missing. |
| REQ-11 | 1/1 | CLI-handler exit, exact node/rack/ladder row counts and golden equality, plus JSON/schema/warnings. |
| REQ-12 | 1/1 | Source scan and independently repeated recursive grep; CI gates distinguish errors from no matches. |

### P-1 divergence inventory

The auditor compared all 16 recorded cases with current recap. Nine diverge, all labeled F-8; seven match. P-1 was audited from the committed file and generator only; recorded Redis version is 8.10.2, without an independent regeneration.

| Case | POC | recap | Recorded reason |
|---|---|---|---|
| Create 10GiB:1, replicated | feasible | infeasible | F-8 |
| Create 50GiB:1, replicated | feasible | infeasible | F-8 |
| Upscale DB 1 to 10GiB:1 | score 2/direct | infeasible | F-8 |
| Upscale DB 2 to 100GiB:2 | score 1/two-step permitted | infeasible | F-8 |
| Upscale DB 4 to 50GiB:1 | score 2/direct | feasible-in-steps | F-8 |
| Upscale DB 5 to 50GiB:1 | score 2/direct | infeasible | F-8 |
| Optimize node 1 | shard 6, 1 → 4 | no moves | F-8 |
| Optimize node 2 | shard 2, 2 → 5 | no moves | F-8 |
| Optimize node 4 | shard 4, 4 → 2 | no moves | F-8 |

The recorded explanation is DB 5's existing same-rack primary/replica pair (nodes 2 and 5 on europe-west1-c). Whole-state checking rejects plans that retain it; DB 4 requires preliminary moves. The generator's classification is broad: it assigns F-8 to any mismatch when all baseline violations are rack-awareness violations. This is not case-specific causality proof and can hide unrelated future regressions; no currently recorded unexplained mismatch was observed. P-1 emits no create placement because all create rungs are infeasible, and only the node-5 optimize parity case emits a migration. Separate synthetic tests provide additional heuristic coverage.

### Remaining boundaries and next work

- P-2 OPEN: owner live-lab comparison and version-fact confirmation, outside the delivery gate.
- D-1 OPEN: exact second rack field and 2D rule. First-dimension checks and unverified warning exist.
- D-2 OPEN: pre-8.0 free RAM at the shard limit. Explicit unknown path exists.
- D-3 OPEN: RS failure mode and presentation emphasis.
- REQ-12's spec deletion sentence conflicts with T12's move-only execution contract; legacy remains retained. An owner decision is needed to resolve literal retirement completeness; the auditor did not delete files.
- Required next work: repair the three reproduced findings with regressions, address the coverage/parity evidence limitations, then rerun independent T13. No APPROVED verdict or full-delivery claim is justified by the green suite alone.

## T13 remediation authorized by owner (2026-10-31)

- Owner request: `go to fix`. Scope: repair the three reproduced audit findings, strengthen their CLI/round-trip/property evidence and P-1 causal classifications, then re-audit independently. Preserve unrelated dirty work, immutable spec and legacy contents; D-1/D-2/D-3 and the conflicting legacy deletion sentence remain owner decisions.
- Tests first: `tests/test_audit_regressions.py` initially produced `8 failed, 1 passed in 0.34s`, reproducing the upscale false negative, partial output refusal and omitted dry-run flags. The stricter P-1 test failed before generation because recorded divergences lacked a case-specific proof.
- REQ-07: upscale now reserves summed growth per target-host node when choosing migration destinations, and stops when its concrete final placement fits. The four-node audit example succeeds with migrations 4→node4 and 6→node4, then memory update, preserving target DB shards. Every emitted step still passes the independent verifier. Standalone optimizer defaults and ranking are unchanged.
- REQ-02/03: only snapshots marked partial and accepted with `--allow-partial` may have invisible database references or missing pair members. Schema errors, absent node references and duplicate known roles remain errors; complete snapshots retain strict validation. Unknown database shards stay counted by reported node resources, are excluded from migrations, and do not receive invented rack policies or sizes. Upscale of a target with missing copies returns a partial-marked infeasible result explaining incomplete placement. New synthetic database IDs avoid visible references to invisible databases.
- REQ-10: create dry-runs now send effective `rack_aware` and `shards_placement` values including resolved defaults; recorded-request tests cover explicit true/false and inherited policy.
- Coverage: added CLI exit/schema assertions for feasible/infeasible create, direct/stepwise/infeasible/unsupported upscale, beneficial/densify/unmet-goal optimize; partial collect-to-capacity/create/upscale/all/optimize/report round trips for wholly missing DB shards, one missing copy and invisible database metadata; generated optimizer topologies vary 3–6 nodes, 1–5 shard pairs, sizes, used memory, slots, rack policy and levels 1/2.
- P-1: regenerated all 16 cases on the previously authorized dedicated Redis 8.10.2 harness; exit 0 with automatic shutdown nosave. Nine F-8 divergences remain. Each now has a per-database-rack counterfactual proof: changing only the offending database's rack policy makes that exact verdict/move list match POC, with replay of every counterfactual step. The generator rejects unclassified mismatches; CI recomputes the proof instead of trusting its label. The actual fixture and its rack policy are unchanged.
- Focused audit regressions + parity: `21 passed in 0.70s`. Full suite: `144 passed in 4.77s`, zero skips. Both grep gates return zero matches, and `git diff --check` passes. `docs/spec-v2.md` and `legacy/` are unchanged.
- Changed paths: `src/recap/snapshot.py`, `src/recap/constraints.py`, `src/recap/planner/create.py`, `src/recap/planner/optimize.py`, `src/recap/planner/upscale.py`, `src/recap/crosscheck.py`, `tests/test_audit_regressions.py`, `tests/test_parity.py`, `tests/fixtures/poc-parity.json`, `tools/gen_poc_parity.sh`, and this tracker. Independent re-audit required before an approval claim.

## T13 second audit and follow-up repair (2026-10-31)

- First repair commit: `1788921793a51dc3a9d3b287b06295384a3cb16a`. Independent fresh-context auditor `t13_reaudit_fixes` returned CHANGES_REQUIRED: `144 passed in 7.49s`, zero skips; both greps returned 1 with empty output. All three original reproductions were fixed. The auditor independently replayed all nine F-8 counterfactual plans and verified that an unrelated fabricated mismatch is rejected by the generator classifier.
- Remaining [P2] REQ-02/07 finding: the partial-target guard checked total visible count only. The expected count can be present with incomplete members split across extra slot ranges. Reproduction: partial `upscale-steps.json`, omit DB 3 shards, split DB 1's master and replica into `0-8191` and `8192-16383`; `can-upscale --allow-partial --db 1 --memory +2GiB` returned internal-error exit 5. An independent four-copy/three-range variant also failed.
- Follow-up regression tests reproduced both variants before implementation: `2 failed, 19 deselected in 0.29s`. The guard now requires exactly the expected number of target ranges and exactly one master/replica per replicated range (or one master for a non-replicated range). Incomplete partial placement returns the existing partial-marked infeasible explanation; strict complete-snapshot checks and verifier remain unchanged.
- CI now explicitly replays counterfactual create and upscale plans as well as optimizer plans, closing the second auditor's proof-maintenance observation.
- Follow-up focused proof: `23 passed in 0.64s`. Full suite: `146 passed in 5.58s`, zero skips. Changed follow-up files: `src/recap/planner/upscale.py`, `tests/test_audit_regressions.py`, `tests/test_parity.py`, and this tracker. Fresh independent final verification pending.

## T13 final independent approval (2026-10-31)

**APPROVED for the bounded offline T13 gate.** Exact audited HEAD: `d508e4aff533642981a0556f13f3fa5179004c7e`, branch `feat/recap-v2`. Fresh-context auditor: `t13_final_verification`. No new material defect or required corrective finding remains. Corrective commits: `1788921793a51dc3a9d3b287b06295384a3cb16a` and `d508e4aff533642981a0556f13f3fa5179004c7e`.

- Independent `rtk proxy .venv/bin/pytest -q`: **146 passed in 5.18s**, zero skips, exit 0.
- Both exact required greps returned exit 1 and empty output (no matches, no execution error): Redis runtime patterns in `src/`; embedded cluster identity patterns in `src/` and `tests/golden/`.
- All four reproduced defects are resolved: per-node upscale growth reservation; partial collection consumption; effective create dry-run options; partial target pair/range completeness. The auditor confirmed the original upscale's alternative migration plan and final `[0,0,10,0] GiB` RAM, partial collect/compute round trips and strict complete validation, explicit/default request bodies, conservative incomplete targets, and additional complete partial target cases with one/two ranges and with/without replication.
- All 31 Given/When/Then acceptance scenarios were checked. Coverage counts: REQ-01 3/3; REQ-02 4/4; REQ-03 2/2; REQ-04 3/3; REQ-05 3/3; REQ-06 2/2; REQ-07 4/4; REQ-08 4/4; REQ-09 1/1; REQ-10 3/3; REQ-11 1/1; REQ-12 1/1. Planner-level scenarios are supplemented by shared exit-code checks, CLI regressions and independent exact subprocess probes. The accepted distinct-database REQ-07 scenario correction is retained.
- P-1: 16 cases; seven matches and nine F-8 divergences, identical case inventory to the audit tables above. The final auditor independently repeated every per-database-rack counterfactual and replayed every plan. Each exact divergent verdict/move list then matches POC. CI now replays counterfactual create/upscale plans too. Counts: **F-8 = 9; all other classes = 0**. Recorded Redis version 8.10.2; this audit did not regenerate it.
- Read-only preservation: no auditor edits, commits, Redis startup or real-cluster calls. The coordinator verified identical before/after digest for all 52 tracked files except this tracker: SHA-256 `58b541feb01112803b8b586f10a751f6db38a64f7939a1de45525d28c21631a9`. The immutable spec, retained legacy contents and unrelated `.DS_Store` files remain preserved. This final audit receipt is intentionally not committed during read-only T13.
- Boundaries remain explicit: **P-2, D-1, D-2, D-3 OPEN**. Legacy is retained under the owner's move-only/no-deletion execution authorization despite the conflicting spec deletion sentence. The approval does not resolve that owner boundary, establish hosted CI or cross-version execution, qualify live RS behavior, or approve execution of exported plans. No push or merge occurred.

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
