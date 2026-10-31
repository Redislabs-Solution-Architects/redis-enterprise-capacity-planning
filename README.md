# recap — Redis Software capacity planning

`recap` is a standalone Python CLI for collecting a Redis Software cluster
snapshot and planning capacity changes offline. It answers:

- How much capacity remains for each shard size?
- Can a new database be placed on the current nodes?
- Can an existing database grow, directly or after moving other shards?
- Which replica migrations or failovers could free space or densify placement?

The CLI simulates placement in memory and replays proposed plans through an
independent verifier. Collection reads the REST API. Optional cross-checks use
RS dry-run endpoints. Exported commands are suggestions for an operator to
review; `recap` does not execute them. Normal use needs no Redis server or Lua.

## Install

Python 3.10 or later is required. From a clone of this repository:

```bash
git clone https://github.com/Redislabs-Solution-Architects/redis-enterprise-capacity-planning.git
cd redis-enterprise-capacity-planning
pipx install .
recap --help
```

For development, install into a virtual environment with `pip install -e '.[test]'`.
The examples below use fixtures from the repository; they do not contact a cluster.

## Try it offline

```bash
recap snapshot validate --snapshot tests/fixtures/no-rack.json
recap capacity --snapshot tests/fixtures/no-rack.json --shard-size 1GiB
recap can-create --snapshot tests/fixtures/no-rack.json --memory 2GiB --shards 1 --replication --format json
recap optimize node --snapshot tests/fixtures/no-rack.json --node 1
recap can-upscale --snapshot tests/fixtures/upscale-steps.json --db 1 --memory +4GiB --format json
recap report --snapshot tests/fixtures/no-rack.json --format markdown
```

A negative feasibility answer exits with code `1`; it is a result, not a CLI
failure. Sizes require a suffix: `50GiB` is valid, while bare `50` is rejected.
`G` means GiB, while `GB` is decimal. Human output uses GiB; JSON uses bytes.

## Use a cluster snapshot

```bash
recap collect --url https://cluster.example:9443 --out /path/outside/repository/snapshot.json
recap capacity --snapshot /path/outside/repository/snapshot.json --format json
```

Collection prompts for credentials unless supplied through the environment or
`--netrc`. TLS verification is enabled by default. See the collection guide
before configuring certificates or accepting a partial snapshot.

## Guides

| Document | Purpose |
|---|---|
| [Getting started](docs/getting-started.md) | A complete offline walkthrough with expected results |
| [Operating guide](docs/operating-guide.md) | Collect snapshots, investigate constraints and prepare changes |
| [CLI reference](docs/cli-reference.md) | Commands, flags, defaults, verdicts and exit codes |
| [Capacity model and limitations](docs/capacity-model.md) | How placement works and how to interpret its limits |
| [Development](docs/development.md) | Run tests, inspect fixtures and reproduce historical POC comparisons |

## Scope

The planner targets RAM databases on Redis Software. Redis Flex and Active-Active
databases are excluded from target planning, while their reported resource use
still affects node capacity. Redis Cloud sizing, forecasting and automatic plan
execution are outside the current implementation. Live cluster validation remains
an operator responsibility; see [limitations](docs/capacity-model.md#limitations).

The retired Lua engine and initialization scripts are retained under `legacy/`.
The Grafana assets describe that historical POC and are not part of the `recap`
runtime. Use the commands and guides above for the Python CLI.
