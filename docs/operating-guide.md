# Operating guide

Use these procedures to answer a capacity question from a saved Redis Software
snapshot. Store real cluster snapshots and exported reports outside the repository.
They contain operational topology even though credentials are excluded.

## Collect a snapshot

Choose an account that can read the cluster, node, database and shard lists and
their list statistics. Cluster-wide visibility gives the most useful model.
Collection prompts for the user and password when environment credentials are absent:

```bash
recap collect --url https://cluster.example:9443 --out /path/outside/repository/snapshot.json
```

For non-interactive use, supply `RECAP_USER` and `RECAP_PASSWORD` through your secret
management environment. There are no username/password CLI flags. `--netrc` explicitly
uses the matching host entry in the current user's netrc file instead:

```bash
recap collect --url https://cluster.example:9443 --netrc --out /path/outside/repository/snapshot.json
```

Keep that credential file private. Credentials are not included in the snapshot.
TLS certificates are verified by default. For an internal certificate authority:

```bash
recap collect --url https://cluster.example:9443 --ca-cert /path/to/ca.pem --out /path/outside/repository/snapshot.json
```

`--insecure` disables verification explicitly, prints a warning and records it in
the snapshot. An API, authentication, network or TLS failure exits `3`.

Collection uses list endpoints for cluster topology and statistics. The lowest
node version determines version-gated behavior. License usage is collected on
versions the client recognizes as supporting it; otherwise it is marked unknown.

## Handle partial visibility

Collection refuses to write a snapshot when reported and visible shard counts
differ, or when visible shards reference an invisible database. It exits `2` and
explains the mismatch. Prefer collecting with sufficient visibility.

If partial visibility is intentional, opt in at both collection and computation:

```bash
recap collect --url https://cluster.example:9443 --allow-partial --out /path/outside/repository/partial.json
recap capacity --snapshot /path/outside/repository/partial.json --allow-partial --format json
```

Results carry `partial: true`; text verdicts use `PARTIAL:`. Missing node references
and duplicate known pair roles still make input invalid. Unknown database shards
remain represented by the reported node RAM/slot usage and are excluded from moves
that would require an unknown size or policy. An upscale target with incomplete
visible placement is reported infeasible with an explicit partial-placement reason.

## Identify a binding constraint

```bash
recap capacity --snapshot /path/to/snapshot.json --shard-size 1GiB 5GiB 25GiB
```

Inspect `capacity`, `free_ram`, `free_slots` and `binding_constraint` together.
A node may have substantial free RAM but no remaining shard slots. A known license
limit can cap cluster capacity independently of those node resources.

For a more conservative capacity report, reserve a fraction of each node's total RAM:

```bash
recap capacity --snapshot /path/to/snapshot.json --shard-size 5GiB --ram-headroom 0.05
```

This flag applies to this capacity calculation only. It does not configure a
persistent policy or change the placement planners' inputs.

## Check a new database

```bash
recap can-create --snapshot /path/to/snapshot.json --memory 50GiB --shards 2 --replication --placement sparse --format json
```

`--memory` includes all copies. This example needs four shards of 12.5 GiB each.
By default, rack awareness and dense/sparse placement come from the cluster policy.
Override rack policy with `--rack-aware` or `--no-rack-aware` when checking a specific intent.

An infeasible result names constraints such as RAM, slots, license, anti-affinity
or rack awareness. `optimize may help` indicates that total free RAM would suffice
but the current placement prevents a solution. It is a hint, not a verified promise
that a migration plan exists.

## Free space on a node or rack

```bash
recap optimize node --snapshot /path/to/snapshot.json --node 3 --need 10GiB --explain
recap optimize rack --snapshot /path/to/snapshot.json --rack rack-a --shard-used-max none
```

Level 1 moves replicas while preserving their roles. Level 2 additionally permits
failovers that enable moves:

```bash
recap optimize node --snapshot /path/to/snapshot.json --node 3 --level 2 --need 10GiB
```

Read the ordered plan and the rejected-candidate explanations. With `--need`, the
planner stops when that much RAM has been freed in scope. A result of `goal-not-met`
can contain verified intermediate moves that do not reach the requested amount.
Without `--need`, `goal-met` means a beneficial move was found.

For database scope, the target database's own shards are excluded from migrations:

```bash
recap optimize db --snapshot /path/to/snapshot.json --db 1
```

Use cluster scope to densify replicas onto a node that cannot take another reserve-sized shard:

```bash
recap optimize cluster --snapshot /path/to/snapshot.json
```

## Plan an upscale

```bash
recap can-upscale --snapshot /path/to/snapshot.json --db 1 --memory +10GiB --format json
recap can-upscale --snapshot /path/to/snapshot.json --db 1 --memory 100GiB --shards 2 --format json
recap can-upscale --snapshot /path/to/snapshot.json --all --ladder '10GiB:1,50GiB:1,100GiB:2,200GiB:4' --format json
```

`feasible` means the target fits with the existing database shards left in place.
`feasible-in-steps` adds preliminary moves of other shards. Growth is summed on each
host node, and migration targets preserve the RAM needed for that growth.

When the shard count changes, the exported order is shard-count update first,
then memory-size update. The assumed placement is marked `conditional: rs-placement`:
RS chooses the actual new placement. Re-collect and re-run before the memory update.
Exported REST commands contain `{url}` unless you provide `--url`; credentials
remain `$RECAP_USER:$RECAP_PASSWORD`. Inspect commands rather than piping them to a shell.

## Compare with RS dry-runs

Re-collect immediately before a comparison. Only this explicit subcommand issues dry-run requests:

```bash
recap cross-check --url https://cluster.example:9443 --snapshot /path/to/fresh.json can-create --memory 50GiB --shards 2 --replication --placement sparse
recap cross-check --url https://cluster.example:9443 --snapshot /path/to/fresh.json can-upscale --db 1 --memory +10GiB
recap cross-check --url https://cluster.example:9443 --snapshot /path/to/fresh.json rebalance --db 1
```

Credentials come from the environment or prompts. Permission or version skips are
reported explicitly. Snapshots older than 600 seconds are rejected by default;
`--max-age SECONDS` changes that age limit. RS results never replace recap's verdict
or exit code. A rebalance comparison is a divergence signal: its RS blueprint and
recap's database-scope optimization have different operational objectives.

## Export a report

```bash
recap report --snapshot /path/to/snapshot.json --format markdown > /path/outside/repository/capacity-report.md
```

Before sharing it, check the snapshot date, partial status, unsupported targets,
unknown license/RAM values and provenance warnings. The report describes a model
of the captured state; it does not reserve resources on the cluster.
