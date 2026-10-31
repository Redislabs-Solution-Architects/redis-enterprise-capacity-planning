# Plan: deliver `recap` v2 from `docs/spec-v2.md`

**Outcome:** implement every non-deferred REQ of `docs/spec-v2.md` as the `recap` Python CLI, with the spec's acceptance scenarios as passing tests and P-1 parity recorded.

## Source and control

| Field | Value |
|---|---|
| Source of truth | `docs/spec-v2.md` (commit `54df49c`, branch `docs/spec-v2`). The spec wins over this plan. Cite stable IDs (`REQ-*`, `SD-*`, `F-*`, `D-*`, `P-*`); never paraphrase them away. |
| Non-goals | The spec's Non-Goals and DEFERRED sections: Redis Flex, Active-Active planning, CCS, any cluster write or `recap apply`, metrics v2 forecasting, optimize level 3, support-package import, Redis Cloud. |
| Terminology | SD-1 (units), SD-2 (snapshot and REST mapping), SD-3 (version matrix), the F-1..F-15 table |
| Persistence | This directory: `plan.md`, `tracker.md`, `coordinator-prompt.md`. `agent_memory` is optional; `tracker.md` is the fallback and the authoritative status. |
| Execution | `plan-only` until the owner launches Codex with `coordinator-prompt.md` |
| Autonomy | `checkpoint`. Stop after T2 (schema and fixtures) and after T8 (optimize) for an owner look. Otherwise continue task by task. |
| Plan maintenance allowed | Yes, only for mechanical tracker updates and evidence-derived fixes to test-file names. Budget: 3 repairs. Classes: `tracker`, `test-selector`. |
| Owner decision required for | Anything touching D-1, D-2 or D-3; any change to a REQ contract; new runtime dependencies beyond the list below; any write to a cluster |
| Commit policy | One commit per task on branch `feat/recap-v2`, created from `docs/spec-v2`. Conventional message plus `Co-Authored-By` if the agent uses one. **No push, no merge, no other branch.** |
| Plan Adequacy | `DELIVERS_INTENT` for every non-deferred REQ. The D-1 and D-2 parts are delivered as the spec's explicit `2d-rack-rule-unverified` / `unknown` paths; deciding them stays open. |
| Intent Coverage | Spec status `DISCOVERY_REQUIRED`. No discovery wave is needed: every task is ready, and D-* blocks no task, only later decisions. |
| Scope downgrade | None |

## Stack (fixed; do not change without owner)

- Python ≥ 3.10, src layout, `pyproject.toml`, installable with `pipx install .`. Entry point `recap = recap.cli:main`.
- CLI built on `argparse` (stdlib).
- Runtime deps: `httpx` (REST), `jsonschema` (schema validation).
- Test deps: `pytest`, `hypothesis`, `respx` (recorded HTTP fixtures).
- No Redis client, no Lua, no `redis-cli` in `src/` (REQ-12).

## File structure

| Path | Responsibility | Owner |
|---|---|---|
| `pyproject.toml`, `README.md` (v2 section), `.gitignore` | packaging, usage docs | T1 (README updated by T12) |
| `src/recap/cli.py` | subcommands, flag parsing, verdict → exit code, text/json output | T1; each feature task adds its own subcommand handler |
| `src/recap/units.py` | SD-1 parsing and formatting | T1 |
| `src/recap/schemas/snapshot.v1.json`, `src/recap/schemas/output.v1.json` | SD-2 schema, REQ-01 output schema | T2 (snapshot), T1 (output) |
| `src/recap/snapshot.py` | load, validate, referential invariants, partial flag | T2 |
| `src/recap/collect.py` | REST collector | T3 |
| `src/recap/model.py` | REQ-04 capacity model | T4 |
| `src/recap/constraints.py` | the single `violations()` | T5 |
| `src/recap/verifier.py` | REQ-09 replay | T6 |
| `src/recap/planner/create.py`, `planner/optimize.py`, `planner/upscale.py` | REQ-06, REQ-08, REQ-07 | T7, T8, T9 |
| `src/recap/render.py` | plan rendering (rladmin, REST templates) | T8 creates it; T9 extends it |
| `src/recap/crosscheck.py` | REQ-10 | T10 |
| `src/recap/report.py` | REQ-11 | T11 |
| `tests/fixtures/poc-5-nodes.json`, `upscale-steps.json`, `densify.json`, `no-rack.json` | REQ-03 fixtures | T2 |
| `tests/fixtures/http/` | recorded REST responses | T3 (T10 adds dry-run responses) |
| `tests/fixtures/poc-parity.json` | P-1 parity record | T12 |
| `tools/convert_poc_fixture.py`, `tools/gen_poc_parity.sh` | fixture conversion, parity generation | T2, T12 |
| `tests/test_<module>.py` | one test file per module | the module's owner task |
| `legacy/` (moved `lua/`, `initcapaplan-*.sh`) | retired POC | T12 |
| `.github/workflows/ci.yml` | pytest, REQ-07 grep, REQ-12 grep | T12 |
| `docs/spec-v2.md` | spec | **nobody edits it**; gaps go to the owner |

## REQ → Task → Verification

| REQ / proof | Task(s) | Verify with |
|---|---|---|
| REQ-01 | T1, completed by T7 | `pytest tests/test_cli.py -q` |
| REQ-02 | T3 | `pytest tests/test_collect.py -q` |
| REQ-03 | T2 | `pytest tests/test_snapshot.py -q` |
| REQ-04 | T4 | `pytest tests/test_model.py -q` |
| REQ-05 | T5 | `pytest tests/test_constraints.py -q`; the property test runs in T7/T8 |
| REQ-06 | T7 | `pytest tests/test_create.py -q` |
| REQ-07 | T9 | `pytest tests/test_upscale.py -q`, plus the credential grep |
| REQ-08 | T8 | `pytest tests/test_optimize.py -q` |
| REQ-09 | T6, wired in T7/T8/T9 | `pytest tests/test_verifier.py -q` |
| REQ-10 | T10 | `pytest tests/test_crosscheck.py -q` |
| REQ-11 | T11 | `pytest tests/test_report.py -q` |
| REQ-12 | T12 | `grep -rE "redis-cli|EVAL|flushdb" src/` must return nothing |
| P-1 | T12 | `pytest tests/test_parity.py -q` |
| P-2 | owner, manual | not a gate; T13 lists it as pending |
| D-1, D-2 | T5, T4 | explicit fallback paths tested; decisions stay open |
| D-3 | T10 | no default highlight; presentation stays neutral |
| F-1..F-15 | traced in each task's `Spec trace` | regression test per finding where the spec gives one |

Spec Test Strategy: each REQ's `Verification` field is the test strategy. Each task copies its REQ's acceptance scenarios **verbatim** as test cases: one test per Given/When/Then, named `test_req<NN>_<slug>`.

## Tasks

Common fields, the same for every task unless stated:
- provider `codex`; role `implementer`; class `implement`; effort `mid`.
- Repo branch `feat/recap-v2`. `Commit allowed: yes, one commit per task on feat/recap-v2`.
- Spec gap policy: stop and report `NEEDS_CONTEXT` with the REQ id and the exact question. Do not design around the gap.
- Do not touch: `docs/spec-v2.md`; other tasks' modules, except to import them.
- Verification cycle: write the scenario tests first and watch them fail, then implement until they pass. Every task ends with `pytest -q` green over the whole suite.
- Done evidence: test command output, the list of changed files, the commit sha.

### T1: scaffold, units, CLI skeleton
- Spec trace: REQ-01, SD-1, F-2, F-12
- Mission: `pyproject.toml`; `units.py` (SD-1, including `G`=GiB, decimal `GB`, `+SIZE` grammar, bare-number rejection); `cli.py` with every subcommand registered; the verdict enum, the exit-code table 0–5, `--format`, the partial convention; `output.v1.json`.
- Not the mission: any compute logic. Unimplemented subcommands exit 2 with `not implemented`.
- Produces: `recap --help` works; `units.parse`; exit-code mapping.
- Verify with: `pip install -e '.[test]' && pytest tests/test_units.py tests/test_cli.py -q`. This covers REQ-01 scenarios 2 and 3 (scenario 1 completes in T7) and a verdict → exit-code table test.

### T2: snapshot schema, validation, fixtures
- depends_on: T1. Spec trace: REQ-03, SD-2, SD-1 (rounding note)
- Mission:
  - `snapshot.v1.json` with every SD-2 field;
  - `snapshot.py` with load, schema validation, the three referential invariants and partial-flag reading;
  - `recap snapshot validate`;
  - `tools/convert_poc_fixture.py`, which turns the topology hardcoded in `initcapaplan-test.sh` into `poc-5-nodes.json` using the REQ-03 binary conversion;
  - the three synthetic fixtures, built exactly as the REQ-07 and REQ-08 scenarios describe them.
- Not the mission: the REST collector.
- Verify with: `pytest tests/test_snapshot.py -q`. Covers the REQ-03 scenarios, plus one test per synthetic fixture asserting that it validates and contains the topology its consuming scenario names.
- **Checkpoint after T2:** stop and report.

### T3: REST collector
- depends_on: T2. Spec trace: REQ-02, SD-2 mapping, SD-3, F-8, F-11, F-15
- Mission: `collect.py` and `recap collect`, following REQ-02 exactly:
  - credentials from env, netrc or a prompt;
  - TLS verified by default, `--insecure` as an explicit opt-out;
  - list endpoints only; `used_memory` in bytes;
  - `usage_report` on RS ≥ 7.22;
  - partial detection and `--allow-partial`;
  - `unsupported_reason`;
  - exit 3 on network, TLS or auth failure.
- Not the mission: dry-run calls; rladmin parsing.
- Verify with: `pytest tests/test_collect.py -q`, using respx fixtures under `tests/fixtures/http/`. Covers the four REQ-02 scenarios and the secret-scan assertion.

### T4: capacity model
- depends_on: T3. Spec trace: REQ-04, F-9, D-2 (the `unknown` path only)
- Mission: `model.py` and `recap capacity`, per REQ-04:
  - `free_ram`, `free_slots`, `capacity(size)`;
  - the license bound;
  - the binding constraint;
  - `--ram-headroom`;
  - pre-8.0 `unknown` free RAM.
- Verify with: `pytest tests/test_model.py -q` (the three REQ-04 scenarios, one test per binding constraint).

### T5: constraint checker
- depends_on: T4. Spec trace: REQ-05, F-3, F-6, F-8, D-1 (the warning path only)
- Mission: `constraints.py` with the single `violations(state)`:
  - anti-affinity;
  - `accept_servers`;
  - RAM, slots and license;
  - per-database rack rule for N racks;
  - no rack rule without replication;
  - the `2d-rack-rule-unverified` warning.
- Verify with: `pytest tests/test_constraints.py -q`. Covers REQ-05 scenario 3 directly; scenarios 1 and 2 are asserted in T7 once `can-create` exists.

### T6: verifier
- depends_on: T5. Spec trace: REQ-09, F-4, F-13
- Mission: `verifier.py`, which replays plan steps, calls `violations()` after each step, checks the goal, and maps failure to exit 5. It shares only `constraints.py` with the planner.
- Verify with: `pytest tests/test_verifier.py -q`. Covers the REQ-09 scenario (faulty planner injected, exit 5).

### T7: can-create
- depends_on: T6. Spec trace: REQ-06, REQ-01 (scenario 1), REQ-05 (scenarios 1–2 and the property test)
- Mission: `planner/create.py`:
  - dense/sparse placement with deterministic tie-break;
  - binding-constraint reasons;
  - the `optimize may help` hint;
  - verifier wired before output.
- Verify with: `pytest tests/test_create.py tests/test_cli.py tests/test_constraints.py -q`. Includes the Hypothesis property test from REQ-05.

### T8: optimize
- depends_on: T7. effort `max` (heuristic parity is the product's differentiator). Spec trace: REQ-08, F-2, F-4, F-5, F-7, F-13
- Mission: `planner/optimize.py` and `render.py`, implementing **every** REQ-08 bullet:
  - movable-shard sets and their orderings per scope;
  - the target rules, the soft score, and the tie-break by uid descending;
  - live ranking;
  - the densify target;
  - level 2 failovers;
  - the `--need` goal and the default filters;
  - rladmin rendering;
  - verifier wired.
- Not the mission: level 3; any execution.
- Verify with: `pytest tests/test_optimize.py -q`. Covers the four REQ-08 scenarios (the P-1 scenario is skipped until T12 creates `poc-parity.json`), plus the property test applied to optimize outputs.
- **Checkpoint after T8:** stop and report.

### T9: can-upscale
- depends_on: T8. Spec trace: REQ-07, F-1, F-14
- Mission: `planner/upscale.py`, per REQ-07:
  - memory-only check summed per node;
  - `feasible` / `feasible-in-steps` / `infeasible`;
  - RS call order and the regex fallback;
  - `conditional: rs-placement`;
  - templated REST rendering;
  - `--all` with the ladder, using `max(rung, current)` shards;
  - exit 4 for unsupported databases.
- Verify with: `pytest tests/test_upscale.py -q` (the four REQ-07 scenarios) and `! grep -rE "admin@admin.com|dev-pierre-lab" src/ tests/golden/`.

### T10: cross-check
- depends_on: T9. Spec trace: REQ-10, D-3 (neutral presentation)
- Mission: `crosscheck.py`:
  - dry-run calls only;
  - version and permission skips;
  - divergence classes;
  - exit code is always `recap`'s own;
  - `--max-age` → exit 2.
- Verify with: `pytest tests/test_crosscheck.py -q`. Covers the three REQ-10 scenarios, plus an assertion that every request URL contains `dry_run`.

### T11: report
- depends_on: T9. Spec trace: REQ-11
- Mission: `report.py`, with text/json/markdown output, the can-create and can-upscale ladders, unsupported databases and warnings.
- Verify with: `pytest tests/test_report.py -q`. Covers the REQ-11 scenario and the golden file under `tests/golden/`.

### T12: POC parity, legacy move, CI
- depends_on: T10, T11. Spec trace: P-1, REQ-12, F-10
- Mission:
  - `tools/gen_poc_parity.sh` runs the POC cases listed in P-1 against a throwaway `redis-server --port 6390 --save ""`, then shuts it down with `shutdown nosave`;
  - commit `poc-parity.json`;
  - `tests/test_parity.py` compares recap with it, accepting only P-1's allowed `divergence_reason`s;
  - move `lua/` and `initcapaplan-*.sh` to `legacy/` (`git mv`);
  - add CI with pytest plus the two greps;
  - add a README v2 usage section.
- Runtime harness: `redis-server` 8.x is at `/opt/homebrew/bin/redis-server`. Readiness: `redis-cli -p 6390 ping` returns `PONG` within 5 s. Teardown is always `shutdown nosave`. If the sandbox forbids binding a port, stop with `BLOCKED: port bind` and do not work around it.
- Do not touch: `legacy/` contents, beyond the move itself.
- Verify with: `pytest -q`, then `grep -rE "redis-cli|EVAL|flushdb" src/` returning nothing.

### T13: audit
- depends_on: T12. role `auditor`, class `audit`, effort `max`. Must run in a **fresh session** (independence). Commit allowed: no.
- Mission: re-run `pytest -q` and both greps. For every REQ, check that each acceptance scenario has a test whose Given/When/Then matches the spec text. List every P-1 divergence and its reason. List P-2, D-1, D-2 and D-3 as open.
- Output: a verdict `APPROVED` / `CHANGES_REQUIRED`, plus a findings list `REQ: problem. fix.`

## Final report contract (coordinator → owner)

`tracker.md` up to date, plus one message containing:
- task status;
- commit shas on `feat/recap-v2`;
- the `pytest -q` summary line;
- P-1 divergence counts by reason;
- the audit verdict;
- the open items (P-2, D-1, D-2, D-3).

Never claim full delivery without T13 `APPROVED`.
