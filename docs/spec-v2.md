# Change Delta: Capacity planner v2 (`recap`)

Spec format: compact
Source of truth: owner requests from 2026-10-30 and 2026-10-31 (architecture and CLI audit of this POC, RS 7.8 → 8.2 release-note review, "RS dry-run is not the oracle", "leave Flex aside for now"); current POC sources `lua/capaplan.lua`, `initcapaplan-api.sh`, `initcapaplan-rladmin.sh`, `initcapaplan-test.sh` and `README.md`; the Redis Software docs listed under [Sources](#sources)
Date: 2026-10-31
Delivery status: DISCOVERY_REQUIRED

Status detail: every REQ can be built now. Two parts wait on a decision: the 2D rack rule in REQ-05 waits on D-1, and free RAM before RS 8.0 in REQ-04 waits on D-2. Until those are decided, both paths return explicit `unverified` and `unknown` outcomes.

## Summary

**Outcome.** Replace the Lua-on-Redis POC with a standalone CLI, `recap`. It answers four questions about a Redis Software (RS) cluster:
- How much capacity is left, per shard size?
- Can I create this database?
- Can I upscale this database?
- How do I free space or densify?

Each answer comes from an in-house placement simulator, and an internal verifier replays every step.

**Problems with the POC today.**
- It needs a scratch Redis server. The init scripts `flushdb` it, so the server must be dedicated.
- The engine is a single `EVAL` script driven by positional arguments, and it prints free text.
- Rack checks only handle exactly 1, 2 or 3 racks that have capacity.
- Credentials and the cluster URL are hardcoded.
- Several known bugs (F-1 to F-15 below) make some answers wrong.

**Resulting behavior.**
- The source of truth is a versioned JSON snapshot, collected read-only from the RS REST API or loaded from a file.
- All computation runs in memory.
- Every command can emit JSON and uses defined exit codes.
- The POC heuristics stay, because they are the product's differentiator. REQ-08 states their exact order and scoring:
  - move replicas before masters;
  - prefer small, lightly used shards;
  - prefer target nodes that keep room for large shards;
  - densify small shards onto nodes that can no longer take large ones.
- RS dry-run APIs are an **optional cross-check only**. The owner found RS placement checks less reliable than the POC planner, and RS release notes through 8.2.0-78 keep fixing placement and migration bugs. RS output never overrides a `recap` verdict.

**Narrowed scope.**
- Redis Flex / Auto Tiering is out of scope (see Non-Goals). Flex databases are detected and marked unsupported; they are never modeled.
- Plan *execution* and growth *forecasting* are DEFERRED.

### POC findings carried into v2

Each finding is mapped to the REQ that resolves it. Line numbers refer to the files as of commit `f4ce74c`.

| ID | Finding | Location | Resolved by |
|---|---|---|---|
| F-1 | Hardcoded `admin@admin.com` and `https://cluster.dev-pierre-lab.demo.redislabs.com` in the upscale plan | `lua/capaplan.lua:479-480` | REQ-02, REQ-07 |
| F-2 | `shard_used_max == -1` compares a string ARGV with a number, so the "no limit" sentinel never matches | `lua/capaplan.lua:527-531` | REQ-01, REQ-08 |
| F-3 | Rack feasibility is aggregate arithmetic that only branches on `nb_rack_ok == 1/2/3` (the count of racks with capacity ≥ 1, `:73`). With 4 or more such racks, or 0 of them in `canUpscale`, no rack check runs and the answer passes. | `lua/capaplan.lua:269-288`, `:437-472` | REQ-05, REQ-06 |
| F-4 | `densifyNode` reads `memory_target` once and never decrements it, so a plan can over-fill the target node | `lua/capaplan.lua:689`, `:701-715` | REQ-08, REQ-09 |
| F-5 | The reserve shard size is hardcoded at 25 GB: as a scoring key (`nodes:candidates:25G`) and as the hard `< 25` threshold in DB scope | `lua/capaplan.lua:595`, `:600`, `:653`, `:735-739` | REQ-08 |
| F-6 | When replication is off, `isRackAware = not isRackAware` flips a non-rack-aware cluster *into* rack checks, so it can answer a false "no" | `lua/capaplan.lua:202`, `:254-258` | REQ-05, REQ-06 |
| F-7 | `optimizeNode` and `densifyNode` only produce plans when `isRackAware`; non-rack-aware clusters always get "no plan" | `lua/capaplan.lua:580`, `:700` | REQ-08 |
| F-8 | Rack awareness is one global flag inferred from `node:1`'s rack id, not each database's `rack_aware`. On the REST path, `jq -r .rack_id` yields `null` or empty, never `-`, so the flag is always `true`. | `initcapaplan-api.sh:198-206`, `lua/capaplan.lua:3` | REQ-05 |
| F-9 | The `0.82 * total_memory` value is computed and stored but never read by the engine; capacity uses `provisional_memory`. Unexplained and dead. | `initcapaplan-api.sh:122` | REQ-04 |
| F-10 | `flushdb async` on the target Redis at every init, plus `Clean()` on every call | `initcapaplan-api.sh:86`, `lua/capaplan.lua:8-18` | REQ-02, REQ-12 |
| F-11 | Default `admin@admin.com` / `admin` credentials; TLS verification disabled (`curl -k`); N+1 `stats/last` calls | `initcapaplan-api.sh:69-79`, `:103`, `:125`, `:150` | REQ-02 |
| F-12 | Free-text output and escalating "loser" messages on a wrong usage | `lua/capaplan.lua:996-1017` | REQ-01 |
| F-13 | Simulated state updates are inverted. `temp:nodes` holds free memory, but each move subtracts the shard from the *source* and adds it to the *target*, so the target looks roomier after every move and the plan over-fills it. | `lua/capaplan.lua:609-610`, `:662-663` | REQ-08, REQ-09 |
| F-14 | The memory-only upscale checks each shard's growth separately against the node's full free RAM, so it under-counts when one node hosts several shards of the same database | `lua/capaplan.lua:374-385` | REQ-07 |
| F-15 | The `used_memory` parser expects a `GB` suffix, but the REST collector writes `G`. Values of 1 GiB or more are truncated and divided by 1000, which breaks the used-memory filter on REST-collected data. | `lua/capaplan.lua:115-118`, `initcapaplan-api.sh:155-160` | REQ-02 |

## Shared definitions

### SD-1: Units and sizes
- All internal quantities are **bytes** (integers).
- **Accepted suffixes.**
  - Binary: `KiB`, `MiB`, `GiB`, `TiB`.
  - Decimal: `KB`, `MB`, `GB`, `TB` (powers of 1000).
  - `B` for bytes.
  - `G` is an alias for `GiB`, matching the POC (`memory_size * 1024 * 1024 * 1024`, `lua/capaplan.lua:481`).
- A bare number is rejected, with exit code 2 and a message naming the accepted suffixes.
- **Relative sizes.** `+SIZE` is accepted only by `can-upscale --memory`. It means "the current `memory_size` plus SIZE".
- **Output.** Human output prints GiB with two decimals. JSON output prints bytes.
- **Shard size.** RS defines a database memory limit as covering "all database replicas and shards, including both primary and replica shards" ([memory limits](https://redis.io/docs/latest/operate/rs/databases/memory-performance/memory-limit/)). The size of one shard is therefore `memory_size / (shards_count × (replication ? 2 : 1))`. This matches the POC (`lua/capaplan.lua:100-108`).
- **Rounding.** The POC floors `memory_size` to whole GiB (`initcapaplan-api.sh:100`) and scales MB values by 1/1000 (`lua/capaplan.lua:118`). `recap` keeps exact bytes, so differences that come only from POC rounding are an allowed P-1 divergence class, `rounding`.

### SD-2: Snapshot (v1 schema)
A snapshot is a JSON document. It is the only input of every compute command.
- `schema_version`, `collected_at` (RFC 3339), and `source`, one of `rest`, `file` or `fixture`.
- `cluster`:
  - `name`.
  - `rs_version`: the **lowest** `software_version` across nodes.
  - `mixed_versions`: `true` when nodes differ. Feature gates (SD-3) use `rs_version`, so a mixed cluster gets the features of its oldest node.
  - `rack_aware`: the cluster policy.
  - `default_shards_placement`: `dense` or `sparse`.
  - overbooking settings, as reported.
  - `license`: `ram_shards_limit` and `ram_shards_in_use`, or `null` when unknown.
- `nodes[]`: `uid`, `rack_id`, `second_rack_id` (or `null`), `total_memory`, `provisional_ram`, `max_redis_servers`, `shard_count`, `accept_servers`, `status`.
- `bdbs[]`: `uid`, `name`, `memory_size`, `shards_count`, `replication`, `rack_aware`, `sharding`, `shard_key_regex`, `shards_placement`, `bigstore`, `crdt`, `unsupported_reason` (or `null`).
- `shards[]`: `uid`, `bdb_uid`, `node_uid`, `role` (`master` or `replica`), `slots`, `used_memory`.
- `provenance`:
  - `collector_user_role`.
  - `partial` (boolean) and `partial_reasons[]`.
  - `warnings[]`.
  - `rs_semantics`: a map of version-gated interpretations. For example, `provisional_ram` is either `"pre-8.0"` or `"8.0+"` (REQ-04).

**Field mapping from the REST API.** This mapping is taken from the POC collector, `initcapaplan-api.sh`.

| Snapshot field | REST source |
|---|---|
| `nodes[].provisional_ram` | `provisional_memory`, from `GET /v1/nodes/stats/last` (POC: `:125-131`) |
| `nodes[].rack_id`, `shard_count`, `total_memory` | `GET /v1/nodes`, fields `rack_id`, `shard_count`, `total_memory` (POC: `:116-120`). An empty or `null` `rack_id` becomes `null`. |
| `shards[].role` | `GET /v1/shards`, field `role`. `slave` maps to `replica`. |
| `shards[].slots` | `assigned_slots` (POC: `:141`) |
| `shards[].used_memory` | `used_memory` in bytes, from `GET /v1/shards/stats/last` (POC: `:150-160`), fetched as one list call |
| `bdbs[]` sizes | `GET /v1/bdbs`, fields `memory_size` (bytes) and `shards_count` |
| All other fields | The same-named fields of `GET /v1/cluster`, `/v1/nodes` and `/v1/bdbs`. These were not used by the POC, so P-2 confirms the exact names. |

### SD-3: Version feature matrix
`recap` detects the RS version at collect time and enables only the features that version supports. Offline commands (snapshot in, answer out) work on a snapshot from any version. Version facts come from the release notes listed under [Sources](#sources) and were researched on 2026-10-31. P-2 re-confirms them on the lab.

| RS version | Feature | Used by | Notes |
|---|---|---|---|
| all supported | `GET /v1/cluster`, `/v1/nodes`, `/v1/bdbs`, `/v1/shards`, `/v1/nodes/stats/last`, `/v1/shards/stats/last` | REQ-02 | Core collection. List calls only, never N+1 (fixes F-11). |
| < 8.0 | `provisional_ram` reports 0 once `max_redis_servers` is reached | REQ-04 | RS 8.0 release notes. See D-2. |
| ≥ 7.8 | `PUT /v1/bdbs/{uid}/actions/rebalance?dry_run=true`. The doc lists permission `view_bdb_info` ([rebalance](https://redis.io/docs/latest/operate/rs/references/rest-api/requests/bdbs/actions/rebalance/)). | REQ-10 | RS blueprint, used for comparison only. |
| ≥ 7.22 | `PUT /v1/bdbs/{uid}/actions/revamp?dry_run=true`, permission `update_bdb_with_action` | REQ-10 | Called only when the account holds that permission; otherwise skipped. |
| ≥ 7.22 | `GET /v1/usage_report` ([usage report](https://redis.io/docs/latest/operate/rs/references/rest-api/requests/usage_report/)) | REQ-02 | Gives license RAM shards in use and the limit. |
| ≥ 7.22 | 2D rack-zone awareness (second rack id) | REQ-05 | Field name and rule unresolved (D-1). |
| ≥ 7.22 | `optimize_shards_placement` deprecated | — | Not used. |
| ≥ 8.0 | `provisional_ram` keeps reporting real free RAM after `max_redis_servers` is reached | REQ-04 | |
| ≥ 8.0 | Metrics v2 GA on `:8070/v2`; `metrics_auth` basic auth | DEFERRED (forecast) | |
| ≥ 8.2 | Database-scoped `db_viewer` and `db_member` roles (field `resources`) | REQ-02 | Visibility becomes partial, so the snapshot must be flagged. |
| ≥ 8.2 | `db_tags` in metrics v2; local metrics storage in the support package | DEFERRED (forecast) | |

## ADDED

### REQ-01: The CLI has explicit subcommands, flags, units, JSON output, verdicts and exit codes
- Evidence checked:
  - The current entry point is `redis-cli --raw EVAL "$(cat lua/capaplan.lua)" 0 <ACTION> <positional args>` (`README.md`, `lua/capaplan.lua:790-812`).
  - Positional parsing is fragile (`lua/capaplan.lua:523-531`, `:884-885`); see F-2 and F-12.
- Impacted files/components: new `recap` package (Python ≥ 3.10, installable with `pipx`): the CLI entry point, the output formatters, and the output JSON Schema.
- Depends on: REQ-03
- Required / forbidden behavior:
  - **Subcommands:** `collect`, `capacity`, `can-create`, `can-upscale`, `optimize`, `report`, `snapshot validate`, `cross-check` (REQ-10).
  - **Inputs.**
    - Every compute subcommand takes `--snapshot PATH`, where `-` means stdin.
    - Flags are named, for example `--memory 50GiB --shards 4 --replication`. Positional sizes are forbidden.
    - Sizes follow SD-1.
    - `--shard-used-max` accepts a size or the literal `none`. The POC sentinel `-1` is rejected with exit code 2 and a hint naming `none`.
  - **Output.** `--format text|json`, default `text`. JSON output carries `schema_version`, `command`, `verdict`, `reasons[]`, `plan[]` (when any), `partial` (boolean) and `snapshot` provenance.
  - **Verdict.** `verdict` is a closed enum:
    - `can-create`: `feasible` | `infeasible`.
    - `can-upscale`: `feasible` | `feasible-in-steps` | `infeasible`.
    - `optimize`: `goal-met` | `goal-not-met` | `no-plan`.
    - `capacity`, `report`, `collect` and `snapshot validate`: `ok`.
  - **Partial snapshots.** Partial status is carried only by `"partial": true`. Text output also prefixes the verdict line with `PARTIAL:`.
  - **Exit codes:**

    | Code | Meaning |
    |---|---|
    | `0` | `ok`, `feasible`, `feasible-in-steps` or `goal-met` |
    | `1` | `infeasible`, `goal-not-met` or `no-plan`. `reasons[]` is non-empty. |
    | `2` | Usage error or unusable input: bad flags, invalid snapshot, partial snapshot without `--allow-partial`, stale snapshot (REQ-10) |
    | `3` | Collection or RS API failure: network, TLS or auth |
    | `4` | Unsupported target or precondition: Flex or Active-Active database, RS version lacks a required feature |
    | `5` | Internal error: a plan failed verification (REQ-09) |

  - **Optimize goals.** With `--need`, the goal is "free at least that much in scope". Without it, the goal is "at least one beneficial move".
  - **Forbidden:**
    - persistent state between invocations, such as the "loser" counter;
    - writing anything to the RS cluster;
    - requiring a Redis server.
- Acceptance scenarios:
  - Given: the fixture snapshot from REQ-03
    When: `recap can-create --snapshot tests/fixtures/poc-5-nodes.json --memory 50GiB --shards 2 --replication --format json`
    Then: the process exits 0 or 1; stdout parses against the output JSON Schema; `verdict` is `feasible` exactly when the exit code is 0; and `reasons[]` is non-empty when the exit code is 1.
  - Given: any valid snapshot
    When: `recap can-create --snapshot s.json --memory 50 --shards 2`
    Then: exit 2, and stderr names the accepted unit suffixes.
  - Given: any valid snapshot
    When: `recap optimize node --snapshot s.json --node 3 --shard-used-max -1`
    Then: exit 2, and stderr suggests `--shard-used-max none`.
- Verification: `pytest` CLI tests that run the entry point as a subprocess, assert the exit code, and validate JSON stdout against the output schema. A table test asserts that each verdict maps to exactly one exit code. These tests catch exit-code regressions and schema drift.

### REQ-02: `collect` builds a complete, read-only, versioned snapshot from the RS REST API
- Evidence checked:
  - `initcapaplan-api.sh` calls `/v1/bdbs`, `/v1/nodes` and `/v1/shards`, plus a `stats/last` call per object (`:103`, `:125`, `:150`). It uses `-k`, defaults to `admin@admin.com`/`admin` (`:69-79`), and runs `flushdb async` (`:86`).
  - `initcapaplan-rladmin.sh` parses `rladmin status` columns with awk.
  - The POC has no license shard limit.
  - DB-scoped roles in RS 8.2 hide the databases a user is not scoped to.
  - See also F-15.
- Impacted files/components: `recap collect`; the snapshot writer; SD-2 and SD-3.
- Required / forbidden behavior:
  - **Inputs.** `--url https://<fqdn>:9443`. Credentials come from `RECAP_USER`/`RECAP_PASSWORD`, `--netrc`, or an interactive prompt. They are never accepted as a flag value and never written to the snapshot or to logs.
  - **TLS.** Verification is on by default, with `--ca-cert PATH`. `--insecure` disables it explicitly, prints a warning, and is recorded in `provenance.warnings[]`.
  - **Requests.**
    - Only `GET` requests are made; the dry-run endpoints belong to REQ-10.
    - Only the list endpoints of the SD-2 mapping are used. Per-object `stats/last` loops are forbidden.
    - `used_memory` is stored in bytes, with no string suffix (fixes F-15).
    - On RS ≥ 7.22, `GET /v1/usage_report` fills `cluster.license`. On older versions `license` is `null` and a warning is recorded.
  - **rladmin parsing is removed.** REST is the only online collector.
  - **Partial visibility detection.** The snapshot gets `provenance.partial = true`, with reasons, when either holds:
    - `sum(nodes[].shard_count)` differs from `len(shards)`;
    - a shard references a `bdb_uid` that is not in `bdbs[]`.

    When the snapshot is partial:
    - `collect` exits 2 and writes nothing, unless `--allow-partial` is passed.
    - Every compute command refuses a partial snapshot with exit 2, unless `--allow-partial` is passed. With the flag, outputs follow the partial convention in REQ-01.
  - **Unsupported databases.** Databases with `bigstore: true` (Flex / Auto Tiering) or `crdt: true` (Active-Active) get `unsupported_reason` set to `flex` or `active-active`. Their shards still count against node RAM and slots (REQ-04).
  - **Errors and output.**
    - A network, TLS or HTTP auth failure exits 3.
    - The snapshot goes to `--out PATH` (default stdout) and must validate against the SD-2 JSON Schema before it is written.
- Acceptance scenarios:
  - Given: recorded REST responses (an HTTP fixture) for a 3-node RS 8.2 cluster where all shards are visible
    When: `recap collect --url https://c:9443 --out s.json`, with credentials in env
    Then: exit 0; `s.json` validates; `provenance.partial == false`; every `shards[].used_memory` is an integer; and the test password appears neither in `s.json` nor on stderr.
  - Given: recorded responses where `/v1/shards` omits the shards of one database, as a scoped `db_viewer` would see
    When: `recap collect ...` without `--allow-partial`
    Then: exit 2; stderr names the mismatch (expected vs. visible shard count); no file is written.
  - Given: recorded responses that include a database with `bigstore: true`
    When: `recap collect ...`
    Then: that database has `unsupported_reason == "flex"`, and its shards are present in `shards[]`.
  - Given: an HTTP fixture that answers 401
    When: `recap collect ...`
    Then: exit 3.
- Verification: `pytest` with recorded HTTP fixtures (no live cluster), plus a secret-scan assertion on all outputs. The live check is manual (Proof P-2).

### REQ-03: The POC test fixture is ported as a snapshot file, and snapshots can be validated offline
- Evidence checked: `initcapaplan-test.sh` hardcodes 5 nodes on racks `europe-west1-b/c/d`, RS 6.2.10, and databases 1, 2, 4 and 5.
- Impacted files/components: `tests/fixtures/poc-5-nodes.json`, `tests/fixtures/upscale-steps.json`, `tests/fixtures/densify.json`, `tests/fixtures/no-rack.json`; `recap snapshot validate`.
- Required / forbidden behavior:
  - **Synthetic fixtures.** REQ-03 also produces the hand-built snapshots that REQ-07 and REQ-08 consume. Each one must contain the topology its consuming scenario describes, and must pass `snapshot validate`.
  - **Fixture content.** The fixture reproduces the POC topology: nodes, racks, databases, shard roles, slots and `used_memory`.
  - **Conversion.** rladmin prints `GB` and `MB` with a binary meaning (GiB and MiB). The fixture conversion therefore multiplies by 2^30 and 2^20. This conversion rule belongs to REQ-03 and is independent of SD-1 suffix parsing. The conversion script is committed next to the fixture.
  - **Validation.** `recap snapshot validate --snapshot PATH` checks the schema plus three referential invariants:
    - every shard's node exists;
    - every shard's database exists;
    - for each replicated database, every slot range has exactly one master and one replica.
  - **Exit codes.** It exits 0 when everything holds. Otherwise it exits 2 and lists each violation with its JSON path.
- Acceptance scenarios:
  - Given: `tests/fixtures/poc-5-nodes.json`
    When: `recap snapshot validate --snapshot tests/fixtures/poc-5-nodes.json`
    Then: exit 0.
  - Given: the same fixture with one shard's `node_uid` set to a node that does not exist
    When: `recap snapshot validate ...`
    Then: exit 2, and the violation names `shards[<i>].node_uid`.
- Verification: `pytest` over the fixture and mutated copies of it. Proof P-1 also compares results against the POC on the same topology.

### REQ-04: The capacity model separates RAM, shard slots and license shards per node, rack and cluster
- Evidence checked:
  - The POC computes `floor(available_memory / size)` per node from `provisional_memory` (`lua/capaplan.lua:50-70`, `initcapaplan-api.sh:125-131`).
  - It ignores `max_redis_servers` and license limits.
  - Before RS 8.0, `provisional_ram` reports 0 once a node reaches `max_redis_servers` (SD-3).
  - See also F-9.
- Impacted files/components: the `recap` model module; `recap capacity`.
- Depends on: REQ-02
- Required / forbidden behavior:
  - **Per node.**
    - `free_ram = max(0, provisional_ram - headroom × total_memory)`. `headroom` is set with `--ram-headroom FRACTION`. The policy default is `0`, which trusts RS-reported values. The unused `0.82` constant is dropped (F-9).
    - `free_slots = max_redis_servers - shard_count`.
    - `capacity(size) = min(floor(free_ram / size), free_slots)`.
    - A node with `accept_servers == false`, or a status other than `active`, has capacity 0 and a reason.
  - **Cluster.** Capacity is also bounded by `license.ram_shards_limit - license.ram_shards_in_use` when the license is known.
  - **Output.** `recap capacity --snapshot s.json [--shard-size SIZE ...]` reports capacity per node, per rack and per cluster, for each requested size. The default sizes are the distinct shard sizes present in the snapshot. Each row states its **binding constraint**: `ram`, `slots`, `license`, `node-inactive` or `none`.
  - **Pre-8.0 semantics** (`provenance.rs_semantics.provisional_ram == "pre-8.0"`). When a node has `free_slots == 0` and `provisional_ram == 0`:
    - its `free_ram` is reported as `unknown`, never as 0;
    - any memory-only upscale that depends on that node is infeasible, with reason `ram-unknown-pre-8.0`;
    - this holds until D-2 decides how to derive the real value.
  - **Forbidden:** treating "0 RAM" and "0 slots" as the same condition.
- Acceptance scenarios:
  - Given: a node with 100 GiB `provisional_ram`, `max_redis_servers = 10` and `shard_count = 9`
    When: `recap capacity --shard-size 5GiB`
    Then: that node's capacity is 1, with binding constraint `slots`.
  - Given: license `ram_shards_limit = 20` and `ram_shards_in_use = 19`, with nodes that have RAM and slots for 10 shards
    When: `recap capacity --shard-size 1GiB`
    Then: cluster capacity is 1, with binding constraint `license`.
  - Given: a pre-8.0 snapshot in which a node has `shard_count == max_redis_servers` and `provisional_ram == 0`
    When: `recap capacity`
    Then: that node's `free_ram` prints `unknown`, and its capacity is 0 with binding constraint `slots`.
- Verification: `pytest` unit tests on synthetic snapshots, one per binding constraint. A single mixed test would hide which constraint is wrong.

### REQ-05: The placement constraint checker supports N racks, per-database rack awareness and anti-affinity
- Evidence checked:
  - See F-3, F-6 and F-8.
  - RS rack-zone awareness places a master and its replica on different racks, has "no limitation on the number of racks", and can be set per database ([rack-zone awareness](https://redis.io/docs/latest/operate/rs/clusters/configure/rack-zone-awareness/)).
  - RS 7.22 adds a second rack dimension (SD-3).
- Impacted files/components: the `recap` constraints module. REQ-06, REQ-07, REQ-08 and REQ-09 use it.
- Depends on: REQ-04
- Required / forbidden behavior:
  - **One function.** `violations(state) -> list[Violation]` is the single source of placement validity. No other module re-implements these rules.
  - **Rules that always apply:**
    - A master and its replica (same `slots`) are never on the same node.
    - No shard is placed on a node with `accept_servers == false`.
    - On every node, `free_ram >= 0` and `free_slots >= 0`. The license limit holds (REQ-04).
  - **Rule when the database has `rack_aware == true`:**
    - A master and its replica are on different `rack_id`s, for any number of racks.
    - The database's own `rack_aware` decides this, not a cluster-wide guess.
  - **No replication:** a database without replication has no rack rule (fixes F-6).
  - **2D rack awareness** (a node carries a second rack id): the rule is unresolved (D-1).
    - Every verdict carries the warning `2d-rack-rule-unverified`.
    - The checker applies only the first-dimension rule.
- Acceptance scenarios:
  - Given: a rack-aware cluster with 4 racks. Rack A has two nodes with 15 GiB `free_ram` each; racks B, C and D have one node each with 5 GiB.
    When: `recap can-create --memory 40GiB --shards 4 --replication` (8 shards of 5 GiB)
    Then: exit 1, with a reason that starts `rack-awareness:`.
    - Capacity is 3 + 3 + 1 + 1 + 1 = 9, so node anti-affinity alone would allow the database (pairs can split across A1 and A2).
    - The rack rule limits rack A to one shard per pair, which leaves 4 + 3 = 7 < 8. So `rack-awareness` is the only valid reason.
    - On the same input the POC answers "yes", because `nb_rack_ok == 4` skips every rack check (F-3).
  - Given: a cluster with `rack_aware == false` and no rack ids
    When: `recap can-create --memory 10GiB --shards 1` (no replication)
    Then: JSON `reasons[]` contains no `rack-awareness` entry (F-6).
  - Given: database A with `rack_aware == true` and database B with `rack_aware == false`
    When: `violations()` evaluates a state where each database's replica is on its master's rack (on different nodes)
    Then: exactly one violation, for A.
- Verification: table-driven `pytest` over the scenarios above, plus a Hypothesis property test. The property test generates random topologies and asserts that every intermediate state of every plan the planner emits has empty `violations()`.

### REQ-06: `can-create` simulates the full placement of the new database's shards
- Evidence checked: the POC `canCreate` compares aggregate counts per rack, using `floor(n/2)` arithmetic over the top three racks (`lua/capaplan.lua:238-288`). It never places individual shards.
- Impacted files/components: the `recap` planner (placement simulation); `recap can-create`.
- Depends on: REQ-03, REQ-05
- Required / forbidden behavior:
  - **Inputs.** `--memory SIZE --shards N [--replication] [--rack-aware|--no-rack-aware] [--placement dense|sparse]`.
    - The rack-aware default is `cluster.rack_aware`.
    - The placement default is `cluster.default_shards_placement`.
  - **Simulation.**
    - Every master and replica is assigned to a node, under REQ-05.
    - `dense` picks the feasible node with the least `free_ram`; `sparse` picks the one with the most.
    - Ties break by node `uid` ascending, so the result is deterministic.
  - **Feasible:** exit 0, with the full placement (shard → node) in JSON.
  - **Infeasible:** exit 1. `reasons[]` names the binding constraint: `ram`, `slots`, `license`, `rack-awareness` or `anti-affinity`.
    - If the cluster's total `free_ram` would hold every shard but placement still fails, the output adds the hint `optimize may help`. This keeps the POC's "theoretically enough RAM" message (`lua/capaplan.lua:243-246`).
  - **Forbidden:** answering `feasible` without a concrete placement that passes `violations()`.
- Acceptance scenarios:
  - Given: `tests/fixtures/poc-5-nodes.json`
    When: each `CANCREATE` case recorded in P-1 is replayed as `recap can-create`
    Then: the verdict equals the POC verdict, or the case carries a `divergence_reason` from P-1.
  - Given: 2 nodes on 2 racks, each with `free_ram` of exactly 5 GiB
    When: `recap can-create --memory 20GiB --shards 2 --replication` (4 shards of 5 GiB)
    Then: exit 1, with reason `ram`.
- Verification: `pytest` scenario tests, plus Proof P-1.

### REQ-07: `can-upscale` evaluates the final placement and emits an ordered, templated plan
- Evidence checked:
  - See F-1 and F-14.
  - The POC `canUpscale` handles the memory-only case per node (`lua/capaplan.lua:371-396`) and the more-shards case (`:400-473`).
  - Its two-step plan reshards first (`sharding: true`, `shards_count` and a default regex pair), then sets `memory_size` (`:475-486`). It offers that plan when the upscale is not direct but either a fresh database of the target size could be created or the rack check passes (`:477-478`).
  - The auto-check ladder runs only for replicated databases (`:763-785`).
- Impacted files/components: `recap can-upscale`; the plan renderer.
- Depends on: REQ-03, REQ-05, REQ-08
- Required / forbidden behavior:
  - **Inputs.** `--db UID|NAME --memory SIZE|+SIZE [--shards N]`. Replication and rack awareness come from the database in the snapshot.
  - **Unsupported databases** (`unsupported_reason` set): exit 4 with `unsupported: <reason>`.
  - **Memory-only** (`N` equals the current count). For each node, the **sum** of the growth of all this database's shards on that node must fit in its `free_ram` (fixes F-14). A node whose `free_ram` is `unknown` (REQ-04) makes the answer `infeasible`, with reason `ram-unknown-pre-8.0`.
  - **Verdicts:**
    - `feasible`: the target fits with every existing shard of the database left in place. The plan holds only RS update calls: one call, or two when the shard count changes. This covers the POC's "two steps" plan.
    - `feasible-in-steps`: the target fits only after other shards move. The plan is: `optimize` moves (REQ-08) that keep the database's own shards in place, then the RS update. The verifier (REQ-09) checks every intermediate state.
    - `infeasible`: no such plan exists. `reasons[]` names the binding constraint.
  - **RS update order.** When the shard count changes, the update keeps the POC order: first `shards_count`, then `memory_size`, as two calls.
    - If the database is not sharded, step 1 sets `sharding: true` with the POC default regex pair `.*\{(?<tag>.*)\}.*` and `(?<tag>.*)`. Otherwise it keeps the database's own `shard_key_regex`.
    - RS chooses where the new shards go. The plan therefore records the placement `recap` assumed, marks the step `conditional: rs-placement`, and tells the user to re-collect and re-run before step 2.
  - **Rendering.** Plan steps print as REST calls in which `{url}` is a placeholder (or the `--url` value), and credentials are always `$RECAP_USER:$RECAP_PASSWORD`.
  - **Auto-check.** `--all` evaluates every supported, replicated database against the next rung of a ladder of `size:shards` pairs.
    - The default ladder is `10GiB:1,50GiB:1,100GiB:2,200GiB:4`, from the POC (`:772-779`). Override it with `--ladder`.
    - The next rung is the first one whose size is greater than the current `memory_size`. The POC instead required an exact match.
    - The rung's shard count is `max(rung shards, current shards_count)`, because RS does not reduce the shard count.
    - This ladder is a policy default inherited from the POC, not a measurement.
- Acceptance scenarios:
  - Given: a replicated database with 1 shard per node, where each node has 6 GiB `free_ram`
    When: `recap can-upscale --db 1 --memory +10GiB` (+5 GiB per shard)
    Then: exit 0, verdict `feasible`.
  - Given: a database with 2 shards on one node, each growing by 4 GiB, on a node with 6 GiB `free_ram`
    When: `recap can-upscale --db 1 --memory +16GiB` (+4 GiB per shard over 4 shards)
    Then: exit 1, verdict `infeasible`, reason `ram` on that node. The POC answers "yes" (F-14).
  - Given: `tests/fixtures/upscale-steps.json`, where database 1's master node lacks 2 GiB but a 1 GiB and a 2 GiB replica of database 2 on it can move to a node with room
    When: `recap can-upscale --db 1 --memory +4GiB --format json`
    Then: exit 0, verdict `feasible-in-steps`, `plan[0].action == "migrate"`, the last step is the RS update, and the rendered text contains neither `admin@admin.com` nor `dev-pierre-lab`.
  - Given: a database with `unsupported_reason == "flex"`
    When: `recap can-upscale --db <it> --memory 20GiB`
    Then: exit 4, with `unsupported: flex`.
- Verification: `pytest` scenario tests, plus a CI grep asserting that no source file or rendered golden output contains `admin@admin.com` or `dev-pierre-lab`.

### REQ-08: `optimize` keeps the POC heuristics, fixes their bugs and adds failover moves
- Evidence checked:
  - See F-2, F-4, F-5, F-7 and F-13.
  - POC scopes are `D`, `N`, `R` and `C` (`lua/capaplan.lua:496-521`). Level 1 moves replicas only. Levels 2 (failovers) and 3 (drain) are WIP.
  - The candidate and ordering rules are described below with their source lines.
- Impacted files/components: `recap optimize`; the planner.
- Depends on: REQ-03, REQ-05
- Required / forbidden behavior:
  - **Command.** `recap optimize db|node|rack|cluster`.
    - The scope id flag: `db` takes `--db`, `node` takes `--node`, `rack` takes `--rack`, and `cluster` takes an optional `--rack`.
    - Common flags:
      - `--shard-size-min SIZE` and `--shard-size-max SIZE`;
      - `--shard-used-max SIZE|none`;
      - `--level 1|2`;
      - `--need SIZE`;
      - `--reserve-shard-size SIZE`. The policy default is the largest shard size in the snapshot; this replaces the hardcoded 25 GB (F-5).
      - `--explain`.
    - Default filters for node, rack and cluster scope: `--shard-size-min 0B`, `--shard-size-max` equal to the largest shard size in the snapshot, and `--shard-used-max none`.
  - **Movable shards** (level 1: replicas only, with roles preserved).
    - Node and rack scope: replicas in scope, filtered by size range and `used_memory <= max`. They are ordered by `shard_size + used_memory` ascending, which is the POC `ZINTER` score order (`:568-579`, `:636-640`).
    - DB scope: the replicas on the nodes that host the target database, **excluding that database's own replicas** (`:570-575`). The default filters are 1–5 GiB size and ≤ 5 GiB used, from the POC `optimizeDB` (`:754`); flags override them.
    - Cluster scope (densify): replicas cluster-wide not already on the target node, ordered by `shard_size + used_memory` **descending** (`:695-699`).
  - **Target node, per move.**
    - The candidate must pass `violations()` after the move.
    - It is never the source node.
    - Rack scope: never a node in the scope rack (`:651-652`).
    - DB scope: never a node of the target database, unless it keeps at least `reserve` of `free_ram` after the move (`:592-598`).
    - Candidates are ranked by `capacity(shard_size) + (free_ram mod reserve) / 1 GiB`, descending. Ties break by node `uid` **descending**, which matches the POC's `ZREVRANGE` (`:603`, `:656`). This is the POC soft score from `ZINTERSTORE ... nodes:candidates:25G` (`:600`, `:653`). The `capacity` term dominates, so the score mostly prefers the node with the most room. It is a ranking, not a filter, and it is kept for parity.
    - The ranking reads the **live** simulated state. The POC reads scores frozen at `capacity()` time, and only its accept check reads the live `temp:nodes`. P-1 therefore allows the divergence class `live-ranking` for differences in the move list after the first move. The POC's lexicographic member order (`node:10` sorts before `node:2`) is allowed as the class `tie-break`.
  - **Densify target** (cluster scope). Among nodes that host shards and have `capacity(reserve) == 0`, optionally within `--rack`, pick the lowest `shard_count + (free_ram mod reserve) / 1 GiB` (`:735-740`). Then fill it while it has room.
  - **State.** The planner keeps one mutable simulated state. After every move, the source's `free_ram` and slots increase and the target's decrease, before the next move is evaluated (fixes F-4 and F-13).
  - **Rack awareness** is per database (REQ-05). Plans are produced for clusters that are not rack-aware too (fixes F-7).
  - **Level 2** adds failovers: a master becomes a replica and its replica is promoted, when that unblocks a replica move or frees the needed RAM.
  - **Goal.** `--need` stops planning once the goal is met. Exit codes and verdicts follow REQ-01.
  - **Output.**
    - An ordered `plan[]` of `{step, action: migrate|failover, shard_uid, from_node, to_node, freed_bytes, state_after_summary}`, plus the total freed per scope.
    - `--explain` adds rejected candidates with reasons.
    - Steps render as `rladmin migrate shard <id> preserve_roles target_node <n>` (as in the POC) and `rladmin failover shard <id>`. These run from a shell on a cluster node.
  - **Level 3** (drain a node) is DEFERRED.
- Acceptance scenarios:
  - Given: `tests/fixtures/poc-5-nodes.json`
    When: each `O N` case recorded in P-1 is replayed as `recap optimize node`
    Then: every emitted step moves a replica; every intermediate state passes `violations()`; and the move list equals the POC's, or the case carries a `divergence_reason` (expected: F-13).
  - Given: `tests/fixtures/densify.json`. The densify target has 2.5 GiB `free_ram` and free slots; 5 replicas of 1 GiB exist on other nodes, and their masters are on other racks.
    When: `recap optimize cluster`
    Then: exit 0, verdict `goal-met`, and exactly 2 migrations target that node (F-4 regression).
  - Given: `tests/fixtures/no-rack.json`: 3 nodes with no rack ids. Node 1 hosts a 1 GiB replica whose master is on node 3, and node 2 has 10 GiB `free_ram`.
    When: `recap optimize node --node 1`
    Then: exit 0, and `plan[]` has at least 1 step (F-7 regression).
  - Given: `tests/fixtures/poc-5-nodes.json`
    When: `recap optimize db --db 1`
    Then: no step moves a shard of database 1.
- Verification: `pytest` scenario tests, the REQ-05 property test applied to `optimize` outputs, and Proof P-1 for the level-1 node scope.

### REQ-09: An internal verifier replays every plan step against the model
- Evidence checked: the POC prints plans without re-checking them (`lua/capaplan.lua:543-560`), and F-4 and F-13 show plans that over-fill nodes. The owner considers RS dry-runs unreliable as an oracle (Summary).
- Impacted files/components: the `recap` verifier, called by REQ-06, REQ-07 and REQ-08 before any output.
- Depends on: REQ-05
- Required / forbidden behavior:
  - **Replay.** The verifier starts from the snapshot, applies the steps one by one, and calls `violations()` after each step.
  - **Goal check.** It re-checks the stated goal on the final state: the database is placed, the needed RAM is freed, or the target fits.
  - **On failure:** exit 5 with `internal-error: plan failed verification at step <k>` and the violation, and no plan is printed. This signals a planner bug, never a user answer.
  - **Independence.** The verifier is separate from the planner and shares only the constraints module (REQ-05).
- Acceptance scenarios:
  - Given: a planner patched in a test to emit a move that over-fills its target
    When: `recap optimize cluster` runs with that planner
    Then: exit 5, with `plan failed verification at step 1`.
- Verification: a `pytest` test that injects a faulty planner. It proves the verifier is in the output path, not only unit-tested.

### REQ-10: `cross-check` compares `recap` with RS dry-runs as a divergence signal only
- Evidence checked:
  - SD-3 rows for rebalance (`view_bdb_info`) and revamp (`update_bdb_with_action`).
  - The owner observed RS placement checks being less reliable than the POC.
  - Release notes list placement and migration fixes through RS 8.2.0-78 (Sources).
- Impacted files/components: `recap cross-check`.
- Depends on: REQ-02
- Required / forbidden behavior:
  - **Command.** `recap cross-check --url ... --snapshot s.json <can-create|can-upscale|rebalance> [args]`.
  - **RS dry-run called:**
    - `can-create`: `POST /v1/bdbs?dry_run`.
    - `can-upscale`: `PUT /v1/bdbs/{uid}/actions/revamp?dry_run=true`, on RS ≥ 7.22.
    - `rebalance`: the rebalance dry-run, on RS ≥ 7.8.
  - **Output.** Both verdicts are printed side by side, classified as `agree`, `rs-refuses-recap-accepts`, `rs-accepts-recap-refuses` or `placement-differs`.
  - **Skips.** A comparison is skipped, with a reason, when:
    - the RS version lacks the endpoint (SD-3);
    - RS answers 401 or 403, reason `permission-denied`.
  - **Exit code.** It is always `recap`'s own verdict code for the same question (REQ-01). Divergence and skips never change it.
  - **Stale snapshot.** Older than `--max-age` (policy default 10 minutes) → exit 2, because a stale model makes divergence meaningless.
  - **Forbidden:** calling any non-dry-run endpoint, and being invoked implicitly by another subcommand.
- Acceptance scenarios:
  - Given: recorded RS responses where the rebalance dry-run returns a blueprint different from the `recap` plan
    When: `recap cross-check rebalance --db 1 ...`
    Then: the output shows `placement-differs`, and the exit code equals that of `recap optimize db --db 1` on the same snapshot.
  - Given: an RS 7.4 snapshot
    When: `recap cross-check can-upscale ...`
    Then: the revamp call is skipped with `requires RS >= 7.22`.
  - Given: recorded responses where `POST /v1/bdbs?dry_run` returns 403
    When: `recap cross-check can-create ...`
    Then: the comparison is skipped with `permission-denied`, and the exit code equals that of `recap can-create` with the same arguments.
- Verification: `pytest` with recorded HTTP fixtures, plus a test asserting that the HTTP client only issues requests whose URL carries `dry_run`. Live comparison is Proof P-2 (manual).

### REQ-11: `report` produces a shareable capacity summary from a snapshot
- Evidence checked:
  - The POC Grafana dashboard reads raw Redis keys through the redis-datasource (`grafana/Redis Enterprise Cluster Capacity-1677605338798.json`).
  - It shows the `db:cancreate` and `db:canUpscale` results, which come from the init scripts' `CANCREATE 10 1`, `50 1`, `100 2` and `200 4` runs (`initcapaplan-api.sh:213-216`) and from the upscale ladder.
- Impacted files/components: `recap report`.
- Depends on: REQ-03, REQ-04, REQ-07
- Required / forbidden behavior:
  - `recap report --snapshot s.json [--format text|json|markdown] [--ladder ...]` outputs:
    - the cluster summary (RS version, mixed versions, nodes, racks, license usage);
    - per-node and per-rack capacity for each shard size present, with binding constraints (REQ-04);
    - the **can-create ladder**: `can-create` with replication for each rung of the REQ-07 ladder;
    - the **can-upscale ladder**: the `can-upscale --all` results (REQ-07);
    - unsupported databases;
    - provenance warnings.
  - Markdown output is self-contained, so it can be pasted into a ticket or a customer document.
- Acceptance scenarios:
  - Given: the fixture
    When: `recap report --snapshot tests/fixtures/poc-5-nodes.json --format markdown`
    Then: exit 0; the output contains one row per node, one row per rack, and one can-create row per ladder rung.
- Verification: a `pytest` golden-file test. The golden file is regenerated only on intentional changes, so the test detects silent formatting or aggregation drift.

## REMOVED

### REQ-12: The POC runtime (Lua engine, scratch Redis, init scripts, Redis-backed dashboard) is retired
- Evidence checked: `README.md` (setup flow), `lua/capaplan.lua`, `initcapaplan-*.sh`, `grafana/`; findings F-10 and F-11.
- Impacted files/components: the files in the table below.
- Depends on: REQ-03
- Required / forbidden behavior:
  - Each component is replaced as the table states.
  - `lua/` and `initcapaplan-*.sh` move to `legacy/` and stay there until P-1 passes; then they are deleted.
  - No `recap` code path invokes `redis-cli`, Lua, or a Redis connection.
- Acceptance scenarios:
  - Given: the v2 tree after P-1 passes
    When: running `grep -rE "redis-cli|EVAL|flushdb" src/`
    Then: there are no matches.
- Verification: the grep runs as a CI step. It detects a reintroduced runtime dependency on Redis.

| Removed | Replaced by | Compatibility |
|---|---|---|
| Lua engine run through `redis-cli EVAL` (`lua/capaplan.lua`) | `recap` in-memory planner (REQ-04 to REQ-09) | Kept under `legacy/` until P-1 passes. |
| Scratch Redis as the data store, `Clean()`, `flushdb async` (F-10) | JSON snapshot (SD-2) | No migration: snapshots are re-collected. |
| `initcapaplan-rladmin.sh` (awk parsing of `rladmin status`) | `recap collect` over REST (REQ-02) | rladmin column formats differed across versions; REST is versioned. |
| `initcapaplan-api.sh` | `recap collect` (REQ-02) | Same endpoints, list-based, TLS verified. |
| `initcapaplan-test.sh` | `tests/fixtures/poc-5-nodes.json` (REQ-03) | Same topology. |
| Grafana dashboard on the redis-datasource | `recap report` (REQ-11); forecasting via metrics v2 is DEFERRED | The dashboard needs the scratch Redis. |

## Shared proofs

- **P-1 (automated, required): POC parity on the fixture.**
  - Load the POC fixture into a throwaway Redis (`redis-server --port 6390 --save ""`).
  - Run these POC cases:
    - `CAPA`;
    - the four `CANCREATE` rungs;
    - the POC upscale ladder (`capaUpDB`, `lua/capaplan.lua:763-785`), whose `db:canUpscale` score is the UDB verdict per replicated database;
    - level-1 `O N` for each node, with arguments `1 25 25`. The value `25` replaces `-1`, which F-2 breaks. The arguments are recorded per case in the parity file.
  - Record verdicts, arguments and move lists in `tests/fixtures/poc-parity.json`.
  - **UDB verdict mapping:**
    - POC score `2` (direct) maps to `feasible`.
    - Score `1` (not direct, rack check met, two-step plan) maps to `feasible` or `feasible-in-steps`.
    - Score `0` maps to `infeasible`.
  - For each case, `recap` must match the POC, or the case must carry a `divergence_reason`. Allowed reasons: a fixed finding (F-1 to F-15), `rounding` (SD-1), `live-ranking` or `tie-break` (REQ-08).
  - Purpose: detect regressions in the heuristics the owner considers the product's differentiator.
  - Prerequisite: `redis-server` on the dev machine, for one-time generation. The parity file is committed, so CI does not need Redis.
- **P-2 (manual, not a delivery gate): live check on the owner's RS 8.2 lab cluster.**
  - Run `recap collect`, then `capacity`, `can-create`, `optimize` and `cross-check rebalance`, with a `cluster_viewer` account.
  - Record the divergences.
  - Re-confirm the SD-3 version facts.
  - Prerequisites: lab access. It is blocked until the owner runs it, and it feeds D-1, D-2 and D-3.

## Non-Goals

- **Redis Flex / Auto Tiering sizing.** The owner deferred it on 2026-10-31. RS 8.0 changed Flex sizing for databases on 8.2+, which would need two models. Flex databases are detected and their RAM shards are counted, but they are never planned for (REQ-02, REQ-07).
- **Active-Active (CRDB) planning across clusters.** It is out of the POC's scope too. CRDB instances count as local shards only.
- **Reading or writing the RS internal config store (CCS).** It is unsupported; REST is the contract.
- **Any write to the cluster**, including plan execution (DEFERRED).
- **Redis Cloud.** It has a different capacity model and is not controlled by the operator.

## Open Decisions

| ID | Question | Owner | Due or revisit trigger | Blocked scope / affected REQs |
|---|---|---|---|---|
| D-1 | What is the exact 2D rack-awareness rule, and what is the field name? Docs say `second_rack_id` on the rack-zone page and `secondary_rack_id` in the 7.22 release note. Is the constraint "different zones", "different racks within a zone", or both? | Pierre | P-2 on the RS 8.2 lab, or confirmation from the RS product team | REQ-05, 2D part only |
| D-2 | On RS < 8.0, how is free RAM derived for a node at `max_redis_servers`, where `provisional_ram == 0`? Options: `total_memory` minus the sum of shard memory limits, or a permanent `unknown`. | Pierre | P-2 on a 7.x lab, or when a 7.x customer needs memory-only upscales | REQ-04 (pre-8.0 path), REQ-07 (memory-only on such nodes) |
| D-3 | Which RS failure mode did the owner see: refusing valid plans, accepting plans that then failed, or sub-optimal placements? It decides which `cross-check` divergence class is highlighted by default. | Pierre | Before REQ-10 output wording is finalized | REQ-10, presentation only |

## DEFERRED

| Item | Owner | Revisit trigger | Delivery impact |
|---|---|---|---|
| Plan execution (`recap apply`): `cluster-state-id` header; availability gate with `extend_check=lag` (RS 8.0) between steps; `GET /v2/actions` progress (7.22); re-collect and re-verify between steps; abort on divergence | Pierre | After P-2 shows the plans are sound on the lab | None: v2 only exports commands |
| Growth forecast in `report` from metrics v2 (`predict_linear`), with `metrics_auth` (8.0), `db_tags` per team (8.2), and local metrics storage via the support package (8.2) | Pierre | After REQ-11 ships | None |
| Optimize level 3 (drain a node) | Pierre | After level 2 is validated by P-2 | None |
| Snapshot import from a support package (`GET /v1/cluster/debuginfo`), for customers who cannot grant API access | Pierre | First customer request | None |
| Optional shared multi-cluster inventory, using Redis as a store for several snapshots | Pierre | When more than one cluster is tracked routinely | None |
| Redis Flex modeling | Pierre | Owner reopens the scope | Flex databases stay unsupported |

## Sources

- POC: `lua/capaplan.lua`, `initcapaplan-api.sh`, `initcapaplan-rladmin.sh`, `initcapaplan-test.sh`, `README.md` at commit `f4ce74c`
- [RS release notes index](https://redis.io/docs/latest/operate/rs/release-notes/)
- [RS 7.8.x](https://redis.io/docs/latest/operate/rs/release-notes/rs-7-8-releases/), [RS 7.8.2-34](https://redis.io/docs/latest/operate/rs/release-notes/rs-7-8-releases/rs-7-8-2-34/)
- [RS 7.22.0-95](https://redis.io/docs/latest/operate/rs/release-notes/rs-7-22-releases/rs-7-22-0-95/)
- [RS 8.0.x](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-0-releases/), [RS 8.0.2-17](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-0-releases/rs-8-0-2-17/)
- [RS 8.2.x](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-2-releases/), [RS 8.2.0-25](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-2-releases/rs-8-2-0-25/)
- [Rebalance API](https://redis.io/docs/latest/operate/rs/references/rest-api/requests/bdbs/actions/rebalance/)
- [Usage report API](https://redis.io/docs/latest/operate/rs/references/rest-api/requests/usage_report/)
- [Rack-zone awareness](https://redis.io/docs/latest/operate/rs/clusters/configure/rack-zone-awareness/)
- [Database memory limits](https://redis.io/docs/latest/operate/rs/databases/memory-performance/memory-limit/)
