# recap capacity report

Cluster: poc-5-nodes
RS: 6.2.10-100; mixed versions: false
Nodes: 5; racks: 3
License RAM shards: unknown

## Nodes

| Node | Rack | Free RAM | Free slots | Capacity by shard size |
| --- | --- | --- | --- | --- |
| node:1 | europe-west1-b | 43.39 GiB | 98 | 1.00 GiB: 43 (ram); 5.00 GiB: 8 (ram); 25.00 GiB: 1 (ram) |
| node:2 | europe-west1-c | 43.55 GiB | 98 | 1.00 GiB: 43 (ram); 5.00 GiB: 8 (ram); 25.00 GiB: 1 (ram) |
| node:3 | europe-west1-d | 24.49 GiB | 99 | 1.00 GiB: 24 (ram); 5.00 GiB: 4 (ram); 25.00 GiB: 0 (ram) |
| node:4 | europe-west1-b | 24.49 GiB | 99 | 1.00 GiB: 24 (ram); 5.00 GiB: 4 (ram); 25.00 GiB: 0 (ram) |
| node:5 | europe-west1-c | 39.60 GiB | 98 | 1.00 GiB: 39 (ram); 5.00 GiB: 7 (ram); 25.00 GiB: 1 (ram) |

## Racks

| Rack | Capacity by shard size |
| --- | --- |
| rack:europe-west1-b | 1.00 GiB: 67 (ram); 5.00 GiB: 12 (ram); 25.00 GiB: 1 (ram) |
| rack:europe-west1-c | 1.00 GiB: 82 (ram); 5.00 GiB: 15 (ram); 25.00 GiB: 2 (ram) |
| rack:europe-west1-d | 1.00 GiB: 24 (ram); 5.00 GiB: 4 (ram); 25.00 GiB: 0 (ram) |

## Cluster capacity

| Shard size | Capacity | Binding constraint |
| --- | --- | --- |
| 1.00 GiB | 173 | none |
| 5.00 GiB | 31 | none |
| 25.00 GiB | 3 | none |

## Can-create ladder (replicated)

| Target | Shards | Verdict | Reasons |
| --- | --- | --- | --- |
| create:10.00 GiB | 1 | infeasible | rack-awareness: database 5 range 0-16383 shares a rack; optimize may help |
| create:50.00 GiB | 1 | infeasible | rack-awareness: database 5 range 0-16383 shares a rack; optimize may help |
| create:100.00 GiB | 2 | infeasible | rack-awareness: insufficient independent capacity; optimize may help |
| create:200.00 GiB | 4 | infeasible | ram: insufficient free RAM |

## Can-upscale ladder

| Database | Target | Shards | Verdict | Reasons |
| --- | --- | --- | --- | --- |
| 1 | 10.00 GiB | 1 | infeasible | rack-awareness: database 5 range 0-16383 shares a rack |
| 2 | 100.00 GiB | 2 | infeasible | rack-awareness: database 5 range 0-16383 shares a rack |
| 4 | 50.00 GiB | 1 | feasible-in-steps |  |
| 5 | 50.00 GiB | 1 | infeasible | rack-awareness: database 5 range 0-16383 shares a rack |

## Unsupported databases

None.

## Provenance warnings

- Recorded rladmin GB/MB use binary units; displayed fractions rounded to the nearest whole byte.
- Unknown POC license, second rack IDs and shard regexes are represented by null or empty values; unreported feature flags use the POC's RAM-only, rack-aware topology.
- node 3: recorded shard_count 0 replaced by 1 from the recorded shard table.
- node 4: recorded shard_count 0 replaced by 1 from the recorded shard table.
