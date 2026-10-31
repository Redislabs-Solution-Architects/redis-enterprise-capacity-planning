# Getting started with recap

This walkthrough is for a Redis Software administrator trying the CLI for the
first time. It uses small synthetic snapshots included in a repository clone.
No credentials, network access or running Redis instance are needed after installation.

## 1. Install from the repository

```bash
pipx install .
recap --help
```

Run these commands from the repository root. The package installs the executable;
the fixture paths in this tutorial refer to files in the clone.

If you prefer a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install .
recap --help
```

## 2. Validate a snapshot

```bash
recap snapshot validate --snapshot tests/fixtures/no-rack.json
```

Expected result: `ok`, exit `0`. This fixture has three nodes and a replicated
1 GiB shard pair. Rack awareness is disabled for the database.

Validation checks the JSON schema and shard references and pairs. Invalid input
exits `2` and identifies the affected JSON path.

## 3. Read capacity

```bash
recap capacity --snapshot tests/fixtures/no-rack.json --shard-size 1GiB --format json
```

Expected result: verdict `ok`, exit `0`. The node capacities are `0`, `10` and
`1` one-GiB shards, for a cluster capacity of `11`. Capacity describes individual
shards; it does not guarantee that a replicated database can be placed.

## 4. Place a new database

```bash
recap can-create --snapshot tests/fixtures/no-rack.json --memory 2GiB --shards 1 --replication --format json
```

Expected result: verdict `feasible`, exit `0`, with a concrete placement in the
JSON output. Here `--memory 2GiB` covers both copies: one primary and one replica
of 1 GiB each. The planner keeps a primary and its replica on different nodes.

Try a target that cannot fit:

```bash
recap can-create --snapshot tests/fixtures/no-rack.json --memory 1TiB --shards 2 --replication --format json
```

Expected result: verdict `infeasible`, exit `1`, with a RAM reason. A shell with
`set -e` will stop at that result unless the script handles exit `1` explicitly.

## 5. Inspect a migration suggestion

```bash
recap optimize node --snapshot tests/fixtures/no-rack.json --node 1
```

Expected result: `goal-met`, exit `0`, including:

```text
rladmin migrate shard 2 preserve_roles target_node 2
```

This line is printed for review. Nothing is executed on a cluster. Each new CLI
invocation starts again from the snapshot; an earlier suggestion does not mutate
that file or persist simulated placement.

## 6. Try an upscale that needs preliminary moves

```bash
recap can-upscale --snapshot tests/fixtures/upscale-steps.json --db 1 --memory +4GiB --format json
```

Expected result: `feasible-in-steps`, exit `0`. The plan moves other databases'
replicas before updating database 1. Its existing shards stay on their current
nodes. REST rendering uses `{url}` and environment-variable credential placeholders.

## 7. Produce a shareable report

```bash
recap report --snapshot tests/fixtures/no-rack.json --format markdown
```

Expected result: exit `0`, with node/rack capacity, create/upscale ladders,
unsupported targets and provenance warnings. Individual ladder rows may be
infeasible even though report generation succeeds.

Continue with the [operating guide](operating-guide.md) to collect a real snapshot,
or the [CLI reference](cli-reference.md) to choose other flags.
