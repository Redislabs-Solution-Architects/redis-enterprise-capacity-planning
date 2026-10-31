# Codex coordinator prompt: recap v2

You are implementing the `recap` CLI in the repo `redis-enterprise-capacity-planning`.

**Start here**
1. `git switch docs/spec-v2 && git switch -c feat/recap-v2`. If `feat/recap-v2` already exists, switch to it.
2. Read `docs/spec-v2.md` in full. It is the source of truth.
3. Read `docs/agent-plans/2026-10-31-recap-v2/plan.md`, which holds the task contracts, and `tracker.md`.
4. Take the first task in `tracker.md` that is not `done`, and whose `depends_on` tasks are all `done`.

**For each task**
- Change only the files the task lists in plan.md's File structure.
- Never edit `docs/spec-v2.md`.
- Write the task's acceptance scenarios as tests first, copying the spec's Given/When/Then **verbatim**, one test per scenario, named `test_req<NN>_<slug>`. Run them and see them fail.
- Implement until the task's `Verify with` passes, then run `pytest -q` on the whole suite.
- Commit once on `feat/recap-v2` with message `feat(recap): T<n> <title> (REQ-xx)`.
- Update `tracker.md` with status `done`, the sha, and the pytest summary line.

**Hard limits**
- No push, no merge, no other branch.
- No network calls to a real cluster. Tests use recorded fixtures only.
- No Redis, Lua or `redis-cli` in `src/`. `redis-server` is allowed only in T12's parity script, on port 6390, with `shutdown nosave` afterwards.
- No new runtime dependencies beyond `httpx` and `jsonschema`. Test-only dependencies: `pytest`, `hypothesis`, `respx`.
- Never invent behavior when the spec is silent or ambiguous. Instead, stop and report `NEEDS_CONTEXT: <REQ> <question>`.
- Do not decide D-1, D-2 or D-3. Implement only the fallback paths the spec defines.
- Never write credentials into files, logs or test fixtures. Use the literal `test-password` in HTTP fixtures.

**Stops**
- After T2 and after T8 (checkpoints): report and wait.
- On `NEEDS_CONTEXT` or `BLOCKED` (for example, port binding is denied), or after 2 failed attempts at the same test: report and wait.
- T13 (the audit) is not yours. Stop after T12.

**Report format (each stop)**
```
TASK: T<n> <status>
COMMITS: <sha> ...
PYTEST: <summary line>
SPEC TRACE: REQ-xx scenarios covered: <n>/<n>
DIVERGENCES (T12 only): <reason>: <count>
NEXT: <task or blocker>
```
Keep it under 15 lines. No diff dumps.
