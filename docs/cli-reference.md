# CLI reference

Run `recap COMMAND --help` for parser-generated help. For optimization, use
`recap optimize SCOPE --help`; for validation, use `recap snapshot validate --help`.

## Common input and output

Compute commands take `--snapshot PATH`. Use `--snapshot -` to read JSON from stdin.
They reject partial snapshots unless `--allow-partial` is provided.

`--format text|json` defaults to `text`. `report` also accepts `markdown` and `html`. Collection
always writes snapshot JSON, rather than the compute-result envelope.

Compute JSON includes `schema_version`, `command`, `verdict`, `reasons`, `partial`
and snapshot provenance, plus command-specific data and `plan` when present.
Schema files are available for [snapshots](../src/recap/schemas/snapshot.v1.json)
and [outputs](../src/recap/schemas/output.v1.json).

### Sizes

| Suffix | Meaning |
|---|---|
| `B` | Bytes |
| `KiB`, `MiB`, `GiB`, `TiB` | Powers of 1024 |
| `KB`, `MB`, `GB`, `TB` | Powers of 1000 |
| `G` | Alias for GiB |

Bare numbers are rejected. Fractions such as `2.5GiB` must resolve to whole bytes.
Only `can-upscale --memory` accepts `+SIZE`, relative to the database's current
memory limit. Use the literal `none` for an unlimited `--shard-used-max`; `-1` is invalid.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | `ok`, `feasible`, `feasible-in-steps`, or `goal-met` |
| `1` | `infeasible`, `goal-not-met`, or `no-plan`; reasons are non-empty |
| `2` | Invalid flags, unusable input, refused partial input, or stale cross-check snapshot |
| `3` | Collection/API, network, authentication or TLS failure |
| `4` | Unsupported planning target, such as Flex or Active-Active |
| `5` | Internal plan-verification failure; no plan is printed |

Cross-check skips and divergences keep the local planning verdict's exit code.

## collect

```text
recap collect --url HTTPS_URL [--out PATH] [--netrc] [--ca-cert PATH] [--insecure] [--allow-partial]
```

| Option | Behavior |
|---|---|
| `--url` | Required HTTPS API endpoint without embedded credentials |
| `--out` | Output file; default `-` writes JSON to stdout |
| `--netrc` | Use matching host credentials from the user's netrc file |
| `--ca-cert` | Certificate authority bundle for TLS verification |
| `--insecure` | Explicitly disable certificate verification and record a warning |
| `--allow-partial` | Permit collection with known visibility gaps |

Without `--netrc`, credentials use `RECAP_USER` and `RECAP_PASSWORD`, prompting for
missing values. Collection only reads list endpoints, including topology/statistics
and version-gated license usage.

## snapshot validate

```text
recap snapshot validate --snapshot PATH [--allow-partial] [--format text|json]
```

Checks schema and references. Complete replicated databases require one master and
one replica per visible slot range. Explicitly accepted partial snapshots may have
missing database metadata or pair members; missing nodes and duplicate known pair
roles remain errors. Failures name the affected JSON paths.

## capacity

```text
recap capacity --snapshot PATH [--shard-size SIZE ...] [--ram-headroom FRACTION] [--format text|json]
```

Without explicit sizes, reports each distinct known database shard size. Headroom
defaults to `0` and must be between `0` and `1`. Reports node, rack and cluster
capacity with binding constraints: `ram`, `slots`, `license`, `node-inactive`, `none`.
`none` means no single constraint was selected for that row, not unlimited capacity.

## can-create

```text
recap can-create --snapshot PATH --memory SIZE --shards N [--replication]
                 [--rack-aware|--no-rack-aware] [--placement dense|sparse] [--format text|json]
```

`N` counts primary shards; replication doubles the number of copies. Memory includes
all copies. Rack and placement defaults come from the snapshot's cluster policy.
Dense placement prefers the feasible node with least free RAM; sparse prefers most.
Ties use node UID ascending. A feasible result includes concrete placement.

## can-upscale

```text
recap can-upscale --snapshot PATH --db UID_OR_NAME --memory SIZE_OR_RELATIVE [--shards N] [--url HTTPS_URL]
recap can-upscale --snapshot PATH --all [--ladder SIZE:N,SIZE:N,...]
```

Both forms accept `--format text|json` and `--allow-partial`. Without `--shards`,
the count remains unchanged. Memory and shard count cannot shrink.

`--all` evaluates supported replicated databases against the first ladder rung
larger than their current memory. A rung never reduces the existing shard count.
Default ladder: `10GiB:1,50GiB:1,100GiB:2,200GiB:4`. Databases already beyond the
last rung have no next-rung row. The ladder is a planning policy, not a measurement.

When reshards are needed, output includes two conditional REST updates in order:
shard count, then memory. The plan keeps an existing shard-key regex or uses the
fallback pair when enabling sharding. Re-collect before the memory update.

## optimize

```text
recap optimize db --db UID_OR_NAME --snapshot PATH [OPTIONS]
recap optimize node --node UID --snapshot PATH [OPTIONS]
recap optimize rack --rack RACK_ID --snapshot PATH [OPTIONS]
recap optimize cluster --snapshot PATH [--rack RACK_ID] [OPTIONS]
```

| Option | Default / meaning |
|---|---|
| `--shard-size-min SIZE` | 1 GiB in DB scope; 0 B elsewhere |
| `--shard-size-max SIZE` | 5 GiB in DB scope; largest known shard elsewhere |
| `--shard-used-max SIZE\|none` | 5 GiB in DB scope; unlimited elsewhere |
| `--reserve-shard-size SIZE` | Largest known shard size; reserve used by target selection |
| `--level 1\|2` | Default 1, replica migrations; 2 also allows failovers |
| `--need SIZE` | Stop when at least this much RAM has been freed in scope |
| `--explain` | Include rejected candidates and reasons |
| `--format text\|json` | Default text; text includes exported commands |

Node/rack/DB scopes consider smaller, less-used candidates first. DB scope excludes
its own database's shards. Cluster scope densifies larger candidates first onto a
selected target. State updates after each move; full rules are explained in the
[capacity model](capacity-model.md).

With `--need`, verdict is `goal-met` or `goal-not-met`. Without it, a useful plan
is `goal-met`; otherwise it is `no-plan`. The algorithm is heuristic and does not
promise a globally optimal or shortest plan.

## cross-check

```text
recap cross-check --url HTTPS_URL --snapshot PATH [--max-age SECONDS] can-create CREATE_OPTIONS
recap cross-check --url HTTPS_URL --snapshot PATH [--max-age SECONDS] can-upscale --db UID_OR_NAME --memory SIZE_OR_RELATIVE [--shards N]
recap cross-check --url HTTPS_URL --snapshot PATH [--max-age SECONDS] rebalance --db UID_OR_NAME
```

Supports `--format text|json` and `--allow-partial`. Use one database target for
upscale comparisons; `--all` is an offline `can-upscale` operation.

| Comparison | RS request used by the client | Client version gate |
|---|---|---|
| Create | `POST /v1/bdbs?dry_run` | No additional version gate |
| Upscale | `PUT /v1/bdbs/{uid}/actions/revamp?dry_run=true` | RS 7.22 or newer |
| Rebalance | `PUT /v1/bdbs/{uid}/actions/rebalance?dry_run=true` | RS 7.8 or newer |

The default snapshot age limit is 600 seconds. Credentials use the environment or
prompts. HTTP 401/403 yields `permission-denied`; unavailable endpoints are skipped
with a version reason. Output classifications are `agree`, `rs-refuses-recap-accepts`,
`rs-accepts-recap-refuses`, `placement-differs`, or `skipped`. The local verdict and
exit code remain authoritative for this comparison.

## report

```text
recap report --snapshot PATH [--ladder SIZE:N,SIZE:N,...] [--format text|json|markdown|html] [--allow-partial]
recap report --snapshot PATH --format html --out PATH [--open] [--allow-partial]
```

Outputs cluster/version/license summary, node and rack capacity, replicated
can-create ladder, supported replicated database upscale ladder, unsupported
entries and provenance warnings. Report generation exits `0` even when ladder
entries are infeasible. Text output is table-formatted; Markdown is suitable for
pasting into a ticket. Use JSON for machine processing and HTML for a standalone
visual report with charts, tables and expandable plans.

`--out PATH` writes HTML as UTF-8. Without it, or with `--out -`, HTML goes to stdout.
`--out` is currently HTML-only and cannot overwrite the input snapshot. The parent
directory must already exist. `--open` requires `--format html --out PATH` and opens
the completed local file after successful calculation and verification. A browser
launch failure prints a warning and leaves the generated report usable. Other
formats and the default text output are unchanged.
