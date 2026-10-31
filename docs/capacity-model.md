# Capacity model and limitations

A snapshot is the input to every compute command. The CLI creates a mutable
in-memory simulation for one invocation, verifies proposed steps and discards that
simulated state when it exits. It does not reserve resources or persist plans into
a cluster. Re-running a command on the same file starts from the same captured state.

## Memory limits and shard copies

A database memory limit covers primary and replica copies:

```text
one shard size = database memory_size / (primary shard count × copies per primary)
copies per primary = 2 with replication, otherwise 1
```

For example, a 50 GiB database with two primary shards and replication has four
12.5 GiB copies. Internal quantities are whole bytes. Inputs that do not yield an
integer-byte shard size are rejected rather than silently rounded.

## Independent capacity bounds

For each active node that accepts shards:

```text
free RAM = max(0, provisional RAM − headroom × total memory)
free slots = max Redis servers − reported shard count
capacity(size) = min(floor(free RAM / size), free slots)
```

Headroom defaults to zero. `capacity --ram-headroom` applies a reserve for that
calculation; planning commands otherwise use the snapshot's reported provisional RAM.
Rack capacity aggregates node capacities. Cluster capacity also observes the
remaining known RAM-shard license allowance. Unknown license usage is reported
explicitly, so an offline answer cannot establish license entitlement.

On pre-8.0 snapshot semantics, a node at its shard limit with zero provisional RAM
has `unknown` free RAM. This separates unavailable RAM information from zero
available slots. Memory-only upscale that relies on such a node is refused with
`ram-unknown-pre-8.0`.

## Placement constraints

The shared checker enforces node RAM and slot limits, known license allowance,
`accept_servers`, and separation of a primary from its replica. For replicated
rack-aware databases, copies must also be on different first-dimension rack IDs.
The database's policy is used, not a global guess about every database. Databases
without replication have no replica rack rule.

Verification evaluates the complete simulated state after every step. An existing
violation elsewhere in the snapshot can therefore prevent a new create or upscale
plan even when that new database appears to fit in isolation. Reasons identify the
violating placement; investigate the snapshot rather than treating aggregate free
RAM as proof of feasibility.

When nodes carry a second rack ID, output includes `2d-rack-rule-unverified`.
Only the first dimension is enforced. The second-dimension field interpretation
and placement rule still require validation against the target environment.

## Planning heuristics

Create assigns every copy to a concrete node. Dense placement prefers less free RAM;
sparse prefers more. The planner backtracks when a tentative placement prevents
completion and breaks equal-RAM ties by node UID ascending.

Optimization moves replicas first, optionally adding failover-plus-migration steps
at level 2. Node/rack/DB candidates are ordered by shard size plus used memory,
ascending; cluster densification reverses that ordering. Candidates must satisfy
the shared checker. Target ranking uses:

```text
capacity(shard size) + (free RAM modulo reserve shard size) / 1 GiB
```

Scores read the live simulated state and target ties use node UID descending.
The reserve defaults to the largest known shard. DB-scope targets on the database's
existing hosts must preserve that reserve. Upscale planning additionally preserves
the target's required growth RAM on each host and stops when the final placement fits.

The independent verifier replays migrations, failovers, placements and simulated
updates, checks every intermediate state, and verifies the final goal. Exit `5`
means the proposed plan failed that check; the plan is withheld.

## Partial snapshots

A partial snapshot is explicitly marked and requires `--allow-partial` at computation.
The model trusts reported node resources for visible and invisible workload alike.
It does not assign unknown databases an invented size or rack policy, and does not
migrate their shards. An incomplete target placement cannot establish an upscale
and returns an explicit partial-placement reason. Partial status remains visible
in both JSON and human-readable results.

## Limitations

- Plans are suggestions from a captured state, not live placement guarantees. Real
  cluster comparison and validation are still needed before operational changes.
- Redis Flex and Active-Active databases are unsupported planning targets. Their
  reported node resource use still reduces the available capacity.
- RS chooses actual placement during a reshard. Conditional plans require a fresh
  snapshot and another check before the subsequent memory update.
- The second rack dimension and pre-8.0 unknown-RAM derivation remain unresolved.
- RS dry-run output is an optional comparison signal, not the placement oracle.
  Version and permission skips do not change the local verdict.
- Optimization is heuristic; it does not guarantee a globally optimal or shortest plan.
- Automatic execution, node draining, growth forecasting and Redis Cloud sizing
  are not implemented.

Historical POC comparison records are described in the [development guide](development.md).
They are fixture evidence and do not replace validation on a live Redis Software cluster.
