# Redis Enterprise Capacity Planning

## Intro

The purpose of this material is to offer users of Redis Enterprise an alternative to some actual limitations.

Indeed there are several situations, while the Redis Enterprise Cluster nodes globally have the capacity to host more shards, **it is impossible to directly** make it happen through the UI or the REST API.

Indeed, at a specific moment the shards placements may not be optimal to make happen some operations like:

1. Create a Database with a given capacity
2. Update a Database with a new given capacity

In such situation, it is not trivial for Redis Enterprise users to know:

1. Would be possible after moving some shards between nodes
2. Would be possible in two steps (reshard first then change the memory_limit of the database)

1 and 2 would be possible adding new nodes to the cluster but such can not be the only answer.

There is actually no option/capability permitting to make 1 and 2 happen automatically.

As well there is no utility permitting to guide Redis Enterprise Administrators through a plan of actions to make 1 and 2 possible.

This is the purpose of this material, to be a start for such guidance.

## Concepts / Architecture

The informations and data about a Redis Enterprise Cluster and its nodes, databases, shards, endpoints are stored in an internal Redis database.

Thus the data can be directly accessed with Redis Commands.

Nevertheless, I made the choice for this prototype not to be intrusive and to not touch the existing and will be using a new Redis database to host the data we need.

As well I made the choice for now to offer several ways to populate the database:

- Using **rladmin** commands.
- Using the **Redis Enterprise REST API**

*Limitation: Doing so the state and data of a cluster need to be manually refreshed. Industrialisation would need to be take in consideration.*
## Pre-requisites

- For target Redis database : Redis>=**6.2**
- For the script to execute: **jq** and **curl**
## Initialization

TODO: add option to create database on Redis Enterprise Cluster
TODO: Input parameters for User/password for API

**Any of this script will: Populate the Redis database**

### with rladmin

The script needs to be executed from a node of the Redis Enterprise cluster

```bash
./initcapaplan-rladmin.sh
```

> This script aims to get information from Redis Enterprise Cluster using rladmin utility commands and populate a Redis database in order to perform capacity planning.\
>
> options:\
> -h     Print this Help.\
> -a     Hostname of the Redis Enterprise Cluster which link to its REST API. Default=locahost\
> -r     Hostname of the Redis Database which will host the generated data from this script. Default=locahost\
> -p     Port of the Redis Database which will host the generated data from this script. Default=6379

### with REST API

```bash
./initcapaplan-api.sh [redis-enterprise-api-host]
```

> This script aims to get information from Redis Enterprise Cluster using its REST API and populate a Redis database in order to perform capacity planning.\
>
> options:\
> -h   Print this Help.\
> -a     Hostname of the Redis Enterprise Cluster which link to its REST API. Default=locahost\
> -r     Hostname of the Redis Database which will host the generated data from this script. Default=locahost\
> -p     Port of the Redis Database which will host the generated data from this script. Default=6379

### for local testing

In order te test/validate the usage of the lua script without the need to spin-up a Redis Enterprise Cluster.
Usefull to:

- Debug/enrich with cost control.
- Discover quickly

```bash
./initcapaplan-test.sh 
```

> This script aims to get information from Redis Enterprise Cluster using its REST API and populate a Redis database in order to perform capacity planning.\
>
> options:\
> -h     Print this Help.\
> -r     Hostname of the Redis Database which will host the generated data from this script. Default=locahost\
> -p     Port of the Redis Database which will host the generated data from this script. Default=6379

## How to use it?

### Help

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 HELP
```

> This is the Main help message. This script permits you to execute > several Actions
>
> Usage:
>
> redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 [action] ... [Options]
>
> Arguments:
>
> action - Depending of the choice the script will execute different actions and will need different Arguments.
>
>Possible Values for action:
>
> - Calculate the Cluster CAPACITY => CAPACITY or CAPA
> - Establish Shard CORRESPONDANCE => CORRESPONDANCE or CORR
> - Determine if you CAN CREATE a database/DB => CANCREATE or CDB
> - Determine if you CAN UPSCALE a database/DB => CANUPSCALE or UDB
> - OPTIMIZE the shards placement of the Cluster => OPTIMIZE or O
>
> To get Help for any action:
> ```bash
> redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 [action] Help
> ```
> OR
> ```bash
> redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 [action] -H
> ```

### Capacity

#### Help - Capacity
\
This permits to calculate the capacity of the Cluster to host shards with a given capacity ie. memory size.

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 CAPACITY Help
```

Calculate the actual capacity of the Cluster, Nodes & Racks
Arguments:

- size - The size of shard capacity we want to make the calculation for

#### Example of Usage - Capacity

To determine if your Cluster can host 25G shards and how many of them on the Cluster, on each Node, on each Rack:

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 CAPACITY 25
```

### Correspondance

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 CORRESPONDANCE Help
```

> Create correspondance between master and replica shards and populate Sets and Sorted sets permitting to make Capacity calculation & Optimisations.\
> As well as determining the consumption of shards for the cluster by type 1G , 5G , 25G
>
> No Arguments.

### Can Create ?

#### Help Create

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 CANCREATE Help
```
>
> Permits to determine if in the actual state of the Cluster whether you will be able or not to create a given database.
>
> Arguments:
>
> - memory_size - Size of the dataset you want to be able to host in your database (Number)
> - nb_of_shards - Number of primary shards (Number)
> - replication - If we need to make the calculation considering High-Availability & Rack-Awareness constraints (Boolean)

#### Example of Usage - Can Create?

Can I create a database with 50G of memory_limit, 1 master shard with replication?

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 CANCREATE 50 1 true
```

**Example of response:**

> Globally the Cluster has enough capacity: it can host 3 shards with 25G and the database you wish to create requires 2.\
> Rack-Zone awareness constraints are met: OK\
> If you can create this database you can upscale a existing one to this capacity.

### Can Upscale ?

#### Help Upscale

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 CANUPSCALE Help
```

> Permits to determine if in the actual state of the Cluster whether you will be able or not to upscale a given database. To a certain amount of memory and shards.
>
> Arguments:
>
> - db: The database (format db:id)
> - memory_size: Size of the dataset you want to be able to host in your database (Number)
> - nb_of_shards: Number of primary shards (Number)
> - replication: If we need to make the calculation considering High-Availability & Rack-Awareness constraints (Boolean)
> - showPlan: To show the plan to scale-up the database if not possible in one step (Boolean)

#### Example of Usage - Can Upscale?

Can I upscale the database db:2 up to 100G of memory_limit, 2 master shards with replication?\
In the case it is not possible directly I want to see the action plan to make it happen.

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 CANUPSCALE db:2 100 2 true true
```

**Examples of response:**

> It is actually not possible to upscale the database in only one step.\
> The plan to upscale the database in two steps is the following:
> ```bash
> curl -k -L -u "admin@admin.com:password" -H "Content-type:application/json" -X PUT https://cluster.dev-pierre-lab.demo.redislabs.com:9443/v1/bdbs/2 -d '{"sharding": true,"shards_count": 2, "shard_key_regex":[{"regex":".*\\{(?<tag>.*)\\}.*"}, {"regex":"(?<tag>.*)"}]}'
> curl -k -L -u "admin@admin.com:password" -H "Content-type:application/json" -X PUT https://cluster.dev-pierre-lab.demo.redislabs.com:9443/v1/bdbs/2 -d '{"memory_size": 107374182400 }'
> ```

**OR**

> The node node:4 is missing 0.51G. You may want to optimise this node. Or use the utility to Optimise the DB.\
> The node node:3 is missing 0.51G. You may want to optimise this node. Or use the utility to Optimise the DB.\
> Rack-Zone awareness constraints are met: OK

--TODO propose the commands to execute directly.

### Optimize

#### Help Optimize

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 OPTIMIZE Help
```

> Optimize shard placement
> You can enter the following arguments in the order:
>
> Arguments:
>
> - scope: Argument permits to define the scope of the optimization between Db, Node (N), Rack (R) or Cluster (C)
>    - When you choose Db it means you try to make space on the nodes hosting the shards of the given database.
>    - When you choose Node it means you want to free some space on a given node
>    - When you choose Rack it means you want to free some space on a given rack
>    - When you choose Cluster it means you want to gather 1G and 5G together on nodes which can not handle any further 25G shards.
> - id: Is the identifier of the node or the rack.
> - shard_size_min: To filter the minimum capacity size (GB) of the shards which can be moved (1,5 or 25)
> - shard_size max: To filter the minimum capacity size (GB) of the shards which can be moved (1,5 or 25)
> - shard_used_max: To filter the maximum memory used (GB) of the shards which can be moved (-1 for not limit).
> - WIP: need - The amount of memory you need to free on the given scope & id.
> - WIP: level - Is the level of deepness the optimization will Globally
>      - level 1 will only migrate replica shards
>      - level 2 will trigger failovers if required
>      - level 3 will empty a Node as much as possible

#### Example of Usage - OPTIMIZE

##### Cluster

To ask for an optimization plan with Cluster scope to migrate replica shards with a minimal memory_limit of 1G, a maximal memory_limit of 5G and a maximum memory_used of 1G.\
It would migrate the shards to nodes in respect of High-Availability and Rack-Awareness constraints.\
It would migrate the shards to the best candidate node.

The best candidate is a Node which can not accept anymore 25G shards and is far to be able.

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 OPTIMIZE C 1 5 1
```

**Examples of response:**

>We can add 11G to the node node:3. 6.76G would be remaining after change.
>The plan to execute would be the following:
>
> ```bash
> rladmin migrate shard 22 preserve_roles target_node 3
> rladmin migrate shard 24 preserve_roles target_node 3
> rladmin migrate shard 28 preserve_roles target_node 3

##### Node

To ask for an optimization plan with Node scope to migrate replica shards with a minimal memory_limit of 1G, a maximal memory_limit of 5G and a maximum memory_used of 1G.\
It would migrate the shards to nodes in respect of High-Availability and Rack-Awareness constraints.

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 OPTIMIZE N node:4 1 5 1
```

**Examples of response:**

> Plan for node node:4 is done. It would permit to make 6G available.\
> The plan to execute would be the following:
>
> ```bash
> rladmin migrate shard 28 preserve_roles target_node 1
> rladmin migrate shard 22 preserve_roles target_node 1
> ```

##### Rack / AZ

To ask for an optimization plan with Rack/AZ scope to migrate replica shards with a minimal memory_limit of 1G, a maximal memory_limit of 5G and a maximum memory_used of 1G.\
It would migrate the shards to nodes in respect of High-Availability and Rack-Awareness constraints.

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 OPTIMIZE R europe-west1-c 1 5 1
```

**Examples of responses:**

> No Plan for Rack europe-west1-c done. There is no Shard meeting conditions.

**OR**

> Plan for Rack europe-west1-b done. It would permit to make 11G available.\
> The plan to execute would be the following:
>
> ```bash
> rladmin migrate shard 28 preserve_roles target_node 4
> rladmin migrate shard 24 preserve_roles target_node 1
> rladmin migrate shard 22 preserve_roles target_node 4
> ```

##### Database

To ask for an optimization plan with Database scope to migrate replica shards with (not configurable) a minimal memory_limit of 1G, a maximal memory_limit of 5G and a maximum memory_used of 1G which are hosted on the same nodes as the database shards.
It would migrate the shards to nodes in respect of High-Availability and Rack-Awareness constraints.

```bash
redis-cli --raw EVAL "$(cat lua/capaplan.lua )" 0 OPTIMIZE D db:4
```

**Examples of response:**

> No Plan for node node:1 done. There is no Shard meeting conditions.\
> No Plan for node node:2 done. There is no Shard meeting conditions.\
> No Plan for node node:3 done. There is no Shard meeting conditions.\
> No Plan for node node:4 done. There is no Shard meeting conditions.

**OR**

> Plan for node node:1 is done. It would permit to make 5G available.\
> The plan to execute would be the following:
>
> ```bash
> rladmin migrate shard 24 preserve_roles target_node 4
> ```
> No Plan for node node:2 done. There is no Shard meeting conditions.