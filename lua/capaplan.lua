--capapaplan.lus
local action = ARGV[1]
local isRackAware = (redis.call("GET", "isRackAware") == "true")
local message =""

-- Clean

local function Clean()
    redis.call("UNLINK","temp:optimise:task")
    redis.call("UNLINK","temp:optimise:fail")
    redis.call("UNLINK","temp:candidates:nodes")
    redis.call("UNLINK","temp:replicas:size")
    redis.call("UNLINK","temp:replicas:used")
    redis.call("UNLINK","temp:replicas")
    redis.call("UNLINK","temp:nodes")
    redis.call("UNLINK","temp:nodes:candidates")
end
Clean()

------------ACTIONS--------------------
---- Calculate Cluster Capacity 
--TODO: Help
----- Variable(s)
local size = tonumber(ARGV[2])

local calcusage = [[Calculate the actual capacity of the Cluster, Nodes & Racks
Arguments:

    size - The size of shard capacity we want to make the calculation for]]
----- Function
local function capacity(size)

    -- init variables
    local capacityClusterkey = "capacity:cluster:" .. size .. "G"
    local nodescapacity = "nodes:" .. size .. "G"
    local nodescandidates = "nodes:candidates:" .. size .. "G"
    local rackcapacity = "racks:" .. size .. "G"
    local capacityfield = "capacity" .. size .. "G"
    -- clean existing keys
    redis.call("SET", capacityClusterkey, 0)
    redis.call("SET", "capacity:cluster:ram", 0)
    redis.call("UNLINK", rackcapacity)
    local nodesSet = redis.call("ZREVRANGE", "nodes", 0, -1)
    local rackSet = redis.call("SMEMBERS", "racks")
    for i, item in ipairs(rackSet) do
        local zerorackkey = "capacity:" .. item .. ":" .. size .. "G"
        redis.call("SET", "capacity:" .. item .. ":ram", 0)
        redis.call("SET", zerorackkey, 0)
    end
    -- define capacity
    for i, item in ipairs(nodesSet) do
        local nodememory = tonumber(redis.call("HGET", item, "available_memory"))
        local rack = redis.call("HGET", item, "rack-id")
        local capacity = math.floor(nodememory / size)
        local capacityRackkey = "capacity:" .. rack .. ":" .. size .. "G"
        local scorecandidate = math.fmod(nodememory, size)
        redis.call("HSET", item, capacityfield, capacity)
        redis.call("INCRBY", "capacity:cluster:ram", math.floor(nodememory))
        redis.call("INCRBY", "capacity:" .. rack .. ":ram", math.floor(nodememory))
        redis.call("INCRBY", capacityClusterkey, capacity)
        redis.call("INCRBY", capacityRackkey, capacity)
        redis.call("ZADD", nodescapacity, capacity, item)
        redis.call("ZADD", nodescandidates, scorecandidate, item)
        redis.call("ZINCRBY", rackcapacity, capacity, rack)
        redis.call("ZADD", "racks:" .. rack .. ":nodes:" .. size .. "G", capacity, item)
        redis.call("ZADD", "racks:" .. rack .. ":" .. nodescandidates, scorecandidate, item)
        if capacity > 0 then
            redis.call("ZADD", "nodes:ok:" .. size .. "G", capacity, item)
            redis.call("ZADD", "racks:" .. rack .. ":nodes:ok:" .. size .. "G", capacity, item)
        end
    end
    local nb_nodes_capacity = tonumber(redis.call("ZCOUNT", nodescapacity, 1, "+inf"))
    redis.call("SET", "nodes:nb:ok:" .. size .. "G", nb_nodes_capacity)
    local nb_rack_capacity = tonumber(redis.call("ZCOUNT", rackcapacity, 1, "+inf"))
    redis.call("SET", "racks:nb:ok:" .. size .. "G", nb_rack_capacity)
    message = redis.call("GET", capacityClusterkey)
    return message
end

----Shard Correspondance Function
--TODO Help 
local corrHelp=[[Create correspondance between master and replica shards and populate Sets and Sorted sets permitting to make Capacity calculation & Optimisations.
As well as determining the consumption of shards for the cluster by type 1G , 5G , 25G
Arguments:

    None ]]
local function correspondanceShards()

    -- Create correspondance between master and replica shards and populate Sets and Sorted sets permitting to make Capacity calculation & Optimisations.
    -- As well as determining the consumption of shards for the cluster by type 1G , 5G , 25G
    local dbSet = redis.call("ZREVRANGE", "db", 0, -1)
    redis.call("UNLINK", "nodes:host")
    redis.call("UNLINK", "cluster:shards")
    redis.call("UNLINK", "cluster:conso:1G")
    redis.call("UNLINK", "cluster:conso:5G")
    redis.call("UNLINK", "cluster:conso:25G")
    redis.call("UNLINK", "cluster:conso:12G")
    for i, item in ipairs(dbSet) do
        redis.call("UNLINK", item .. ":nodes")
        local shardsSet = redis.call("SMEMBERS", item .. ":shards")
        local mem_limit = tonumber(redis.call("HGET", item, "memory_limit"))
        local nb_shards = tonumber(redis.call("HGET", item, "number-shards"))
        local replication = (redis.call("HGET", item, "replication") == "enabled")
        if replication then
            nb_shards = nb_shards * 2
        end
        local shard_size = math.floor(mem_limit / nb_shards)
        for j, shard in ipairs(shardsSet) do
            local shard_role = redis.call("HGET", shard, "role")
            local shard_node = redis.call("HGET", shard, "node-id")
            local rack_node = redis.call("HGET", shard_node, "rack-id")
            local used_s = redis.call("HGET", shard, "used_memory")
            local used = 0
            if string.find(used_s, "G") then
                used = tonumber(string.sub(used_s, 1, -2))
            else
                used = tonumber(string.sub(used_s, 1, -3)) / 1000
            end
            redis.call("ZINCRBY", "cluster:shards", 1, shard_size .. "G")
            redis.call("INCRBY", "cluster:conso:" .. shard_size .. "G", 1)
            redis.call("ZINCRBY", "nodes:host", 1, shard_node)
            redis.call("ZINCRBY", item .. ":nodes", 1, shard_node)
            redis.call("ZADD", "cluster:shards:used", used, shard)
            redis.call("ZADD", "cluster:shards:size", shard_size, shard)
            redis.call("HSET", shard, "rack-id", rack_node)
            redis.call("HSET", shard, "shard-size", shard_size)
            redis.call("SADD", shard_node .. ":shards", shard)
            redis.call("SADD", rack_node .. ":shards", shard)
            redis.call("ZADD", shard_node .. ":shards:used", used, shard)
            redis.call("ZADD", rack_node .. ":shards:used", used, shard)
            redis.call("ZADD", shard_node .. ":shards:size", shard_size, shard)
            redis.call("ZADD", rack_node .. ":shards:size", shard_size, shard)
            redis.call("SADD", shard_node .. ":shards:" .. shard_size .. "G", shard)
            redis.call("SADD", rack_node .. ":shards:" .. shard_size .. "G", shard)
            redis.call("ZADD", shard_node .. ":shards:used:" .. shard_size .. "G", used, shard)
            redis.call("ZADD", rack_node .. ":shards:used:" .. shard_size .. "G", used, shard)
            if shard_role == "master" then
                redis.call("ZADD", "cluster:masters:used", used, shard)
                redis.call("ZADD", "cluster:masters:size", shard_size, shard)
                redis.call("SADD", item .. ":masters", shard)
                redis.call("SADD", shard_node .. ":masters", shard)
                redis.call("SADD", rack_node .. ":masters", shard)
                redis.call("ZADD", shard_node .. ":masters:used", used, shard)
                redis.call("ZADD", rack_node .. ":masters:used", used, shard)
                redis.call("ZADD", shard_node .. ":masters:size", shard_size, shard)
                redis.call("ZADD", rack_node .. ":masters:size", shard_size, shard)
                redis.call("SADD", shard_node .. ":masters:" .. shard_size .. "G", shard)
                redis.call("SADD", rack_node .. ":masters:" .. shard_size .. "G", shard)
                redis.call("ZADD", shard_node .. ":masters:used:" .. shard_size .. "G", used, shard)
                redis.call("ZADD", rack_node .. ":masters:used:" .. shard_size .. "G", used, shard)
            else
                redis.call("ZADD", "cluster:replicas:used", used, shard)
                redis.call("ZADD", "cluster:replicas:size", shard_size, shard)
                redis.call("SADD", item .. ":replicas", shard)
                redis.call("SADD", shard_node .. ":replicas", shard)
                redis.call("SADD", rack_node .. ":replicas", shard)
                redis.call("ZADD", shard_node .. ":replicas:used", used, shard)
                redis.call("ZADD", rack_node .. ":replicas:used", used, shard)
                redis.call("ZADD", shard_node .. ":replicas:size", shard_size, shard)
                redis.call("ZADD", rack_node .. ":replicas:size", shard_size, shard)
                redis.call("SADD", shard_node .. ":replicas:" .. shard_size .. "G", shard)
                redis.call("SADD", rack_node .. ":replicas:" .. shard_size .. "G", shard)
                redis.call("ZADD", shard_node .. ":replicas:used:" .. shard_size .. "G", used, shard)
                redis.call("ZADD", rack_node .. ":replicas:used:" .. shard_size .. "G", used, shard)
            end
        end
        local masterSet = redis.call("SMEMBERS", item .. ":masters")
        local replicaSet = redis.call("SMEMBERS", item .. ":replicas")
        for m, master in ipairs(masterSet) do
            local master_slots = redis.call("HGET", master, "slots")
            for r, replica in ipairs(replicaSet) do
                local replica_slots = redis.call("HGET", replica, "slots")
                if master_slots == replica_slots then
                    redis.call("SET", master .. ":linkedto", replica)
                    redis.call("SET", replica .. ":linkedto", master)
                end
            end
        end
    end
    message = "OK"
    return message
end

--- Can Create 
----- Variables 
local createusage = [[Permits to determine if in the actual state of the Cluster whether you will be able or not to create a given database.
Arguments:

    memory_size - Size of the dataset you want to be able to host in your database (Number)

    nb_of_shards - Number of primary shards (Number)

    replication - If we need to make the calculation considering High-Availability & Rack-Awareness constraints (Boolean)]]

-----Functions

local function canCreate(memory_size,nb_of_shards,replication)

    local shard_size = 0
    local nb_of_shards_t = 0
    local isRackAware = (redis.call("GET", "isRackAware") == "true")
    local status = true
    if replication then
        nb_of_shards_t = nb_of_shards * 2
        shard_size = math.floor(memory_size / nb_of_shards_t)
        nb_of_shards = nb_of_shards_t * 1
    else
        shard_size = math.floor(memory_size / nb_of_shards)
    end
    local capacityClusterfield = "capacity:cluster:" .. shard_size .. "G"
    local clusterRam = tonumber(redis.call("GET", "capacity:cluster:ram"))
    -- Get Capacity Summary for this shard size
    local capacityC = tonumber(redis.call("GET", capacityClusterfield))
    local clusterTheoricalCapacity = math.floor(clusterRam / shard_size) - capacityC
    local nb_nodes_with_capacity = tonumber(redis.call("GET", "nodes:nb:ok:" .. shard_size .. "G"))
    --local nb_racks_with_capacity = tonumber(redis.call("GET","racks:nb:ok:" .. shard_size .. "G" ))

    -- To be cleaned ot all used at that stage
    local v_master_ok = math.floor(nb_of_shards / 2)
    local v_replica_ok = math.floor(nb_of_shards / 2)
    local nodesSet = redis.call("ZREVRANGE", "nodes:" .. shard_size .. "G", 0, -1)
    local master_ok = false
    local replica_ok = false
    local remaining = 0
    local list_nodes_to_optimise = ""
    local list_rack_to_optimise = ""
    local rank_node_rest = 0
    -- Cluster Level
    if capacityC < nb_of_shards then
        message = message ..
            "Not enough shard capacity in the Cluster to create this database " ..
            capacityC .. " < " .. nb_of_shards .. "."
        status = false
        if not (clusterTheoricalCapacity < nb_of_shards - capacityC) then
            message = message ..
                "\n But there is theorically enough RAM to host " .. clusterTheoricalCapacity .. " additional shards."
        end
    else
        message = message ..
            "Globally the Cluster has enough capacity: it can host " ..
            capacityC ..
            " shards with " .. shard_size .. "G and the database you wish to create requires " .. nb_of_shards .. "."
    end
    -- No replication => No Rack-zone Awareness
    if not replication then
        message = message ..
            "\n There are " .. nb_nodes_with_capacity .. " Nodes which can host shards with " .. shard_size .. "G."
        isRackAware = not isRackAware
    end
    -- Rack-Zone Awareness
    if isRackAware then
        local racksSet = redis.call("ZREVRANGE", "racks:" .. shard_size .. "G", 0, -1)
        local first = redis.call("ZREVRANGE", "racks:" .. shard_size .. "G", 0, 0)
        local second = redis.call("ZREVRANGE", "racks:" .. shard_size .. "G", 1, 1)
        local third = redis.call("ZREVRANGE", "racks:" .. shard_size .. "G", 2, 2)
        local fscore = tonumber(redis.call("ZSCORE", "racks:" .. shard_size .. "G", first[1]))
        local sscore = tonumber(redis.call("ZSCORE", "racks:" .. shard_size .. "G", second[1]))
        local tscore = tonumber(redis.call("ZSCORE", "racks:" .. shard_size .. "G", third[1]))
        local nb_rack_ok = tonumber(redis.call("GET", "racks:nb:ok:" .. shard_size .. "G"))
        if (nb_rack_ok == 1) then
            message = message .. string.format("\n Only one rack (" .. first[1] .. ") has the capacity: there are not enough resources to meet Rack-Zone awareness constraints.\n You may want to oppitmise the shards placement.")
            status = false
        end
        if (nb_rack_ok == 2) then
            if (fscore >= math.floor(nb_of_shards / 2) and sscore >= math.floor(nb_of_shards / 2)) then
                message = message .. string.format("\n Rack-Zone awareness constraints are met: OK")
            else
                message = message .. string.format("\n Rack-Zone awareness constraints are not met! Racks " .. second[1] .. " and " .. third[1] .. " do not have enough capacity.")
                status = false
            end
        end
        if (nb_rack_ok == 3) then
            if ((fscore >= math.floor(nb_of_shards / 2) and sscore + tscore >= math.floor(nb_of_shards / 2)) or (sscore + tscore > math.floor(nb_of_shards / 2))) then
                message = message .. string.format(" \n Rack-Zone awareness constraints are met: OK")
            else
                message = message .. string.format("\n Rack-Zone awareness constraints are not met! Racks " .. second[1] .. " and " .. third[1] .. " do not have enough capacity.")
                status = false
            end
        end
    end
    if status then
        message = message .. string.format('\n')
        message = message .. string.format("If you can create this database you can upscale a existing one to this capacity.")
        redis.call("SET", "cancreate:" .. memory_size .. "G", "true")
    else
        redis.call("SET", "cancreate:" .. memory_size .. "G", "false")
    end
    return message
end

--- Can Upscale Variables & Functions

local upscaleusage = [[Permits to determine if in the actual state of the Cluster whether you will be able or not to upscale a given database. To a certain amount of memory and shards.
Arguments:

    db - The database (format db:id)

    memory_size - Size of the dataset you want to be able to host in your database (Number)

    nb_of_shards - Number of primary shards (Number)

    replication - If we need to make the calculation considering High-Availability & Rack-Awareness constraints (Boolean)

    showPlan - To show the plan to scale-up the database if not possible in one step (Boolean)]]
local db = ARGV[2]
local memory_size = tonumber(ARGV[3])
local nb_of_shards = tonumber(ARGV[4])
local replication = (ARGV[5] == "true")
local showPlan = (ARGV[6] == "true")
local internal = (ARGV[7] == "true")

----- Function
local function canUpscale(db,memory_size,nb_of_shards,replication,showPlan,internal)
    local db_id = string.sub(db,4)
    local shard_size = 0
    local nb_of_shards_t = 0
    local isRackAware = (redis.call("GET", "isRackAware") == "true")
    local direct = true
    local indirect = true
    --Re-initialise temp data
    redis.call("UNLINK", "temp:need:nodes")
    redis.call("UNLINK", "temp:need:racks")

    -- Gather the necessary information of the database
    local db_memory = tonumber(redis.call("HGET", db , "memory_limit"))
    local db_nb_shards = tonumber(redis.call("HGET", db , "number-shards"))
    local db_shard_size = math.floor(db_memory/db_nb_shards)

    if replication then
        nb_of_shards_t = nb_of_shards * 2
        shard_size = math.floor(memory_size / nb_of_shards_t)
        nb_of_shards = nb_of_shards_t
        db_shard_size = db_shard_size/2
        db_nb_shards = db_nb_shards * 2
    else
        shard_size = math.floor(memory_size / nb_of_shards)
    end
    local capacityClusterfield = "capacity:cluster:" .. shard_size .. "G"
    local clusterRam = tonumber(redis.call("GET", "capacity:cluster:ram"))
    -- Get Capacity Summary for this shard size
    local capacityC = tonumber(redis.call("GET", capacityClusterfield))
    local clusterTheoricalCapacity = math.floor(clusterRam / shard_size) - capacityC
    local nb_nodes_with_capacity = tonumber(redis.call("GET","nodes:nb:ok:" .. shard_size .. "G" ))

    -- What we need for this db

    local db_memory_need = memory_size - db_memory
    local shard_memory_need = shard_size - db_shard_size
    local nb_shards_need = nb_of_shards - db_nb_shards
    local shardSet = redis.call("SMEMBERS", db ..":shards")

    --case 1 / No additional shard just more memory
    if nb_shards_need == 0 then

        for i,item in ipairs(shardSet) do
            local node = redis.call("HGET", item, "node-id")
            local node_memory = tonumber(redis.call("HGET", node, "available_memory"))
            if node_memory < shard_memory_need then
                local miss = shard_memory_need - node_memory
                message = message .. "\n The node " .. node .. " is missing " .. miss .. "G. You may want to optimise this node."
                direct = false
                if internal then
                    redis.call("ZADD", "db:canUpscale", 0 , db)
                end
            end
        end
        if direct then
            if internal then
                redis.call("ZADD", "db:canUpscale", 2,db )
            end
            return "OK"
        else return message
        end

    end

    --case 2 other

    --- First can we upscale directly ?
    if nb_shards_need > 0 then
        for i, item in ipairs(shardSet) do
            local node = redis.call("HGET", item, "node-id")
            local rack = redis.call("HGET", item, "rack-id")
            redis.call("ZINCRBY", "temp:need:nodes", 1, node)
            redis.call("ZINCRBY", "temp:need:racks", 1, rack)
        end

        for i, item in ipairs(shardSet) do
            local node = redis.call("HGET", item, "node-id")
            local node_capacity = tonumber(redis.call("HGET", node, "capacity" .. shard_size .. "G"))
            local node_need = tonumber(redis.call("ZSCORE", "temp:need:nodes", node))
            if node_capacity < node_need then
                local miss = (node_need * shard_size) - tonumber(redis.call("HGET", node, "available_memory"))
                message = message .."\n The node " ..node .." is missing " .. miss .. "G. You may want to optimise this node. Or use the utility to Optimise the DB"
                direct = false
            end
            if direct then
                if internal then
                    redis.call("ZADD", "db:canUpscale", 2 , db)
                end
                return "OK"
            end
        end

        if isRackAware then
            local racksSet = redis.call("ZREVRANGE", "racks:" .. shard_size .. "G", 0, -1)
            local first = redis.call("ZREVRANGE", "racks:" .. shard_size .. "G", 0, 0)
            local second = redis.call("ZREVRANGE", "racks:" .. shard_size .. "G", 1, 1)
            local third = redis.call("ZREVRANGE", "racks:" .. shard_size .. "G", 2, 2)
            local fscore = tonumber(redis.call("ZSCORE", "racks:" .. shard_size .. "G", first[1]))
            local sscore = tonumber(redis.call("ZSCORE", "racks:" .. shard_size .. "G", second[1]))
            local tscore = tonumber(redis.call("ZSCORE", "racks:" .. shard_size .. "G", third[1]))
            local nb_rack_ok = tonumber(redis.call("GET", "racks:nb:ok:" .. shard_size .. "G"))
            if (nb_rack_ok == 1) then
                message = message ..string.format("\n Only one rack (" ..first[1] ..") has the capacity: there are not enough resources to meet Rack-Zone awareness constraints.\n You may want to optimise the shards placement.")
                indirect = false
                if internal then
                    redis.call("ZADD", "db:canUpscale", 0 , db)
                end
            end
            if (nb_rack_ok == 2) then
                if (fscore >= math.floor(nb_shards_need / 2) and sscore >= math.floor(nb_shards_need / 2)) then
                    message = message .. string.format("\n Rack-Zone awareness constraints are met: OK")
                    if internal then
                        redis.call("ZADD", "db:canUpscale", 1, db )
                    end
                else
                    message = message ..
                        string.format("\n Rack-Zone awareness constraints are not met! Racks " ..second[1] .. " and " .. third[1] .. " do not have enough capacity.")
                    indirect = false
                    if internal then
                        redis.call("ZADD", "db:canUpscale", 0 , db)
                    end
                end
            end
            if (nb_rack_ok == 3) then
                if (fscore >= math.floor(nb_shards_need / 2) and sscore + tscore >= math.floor(nb_shards_need / 2)) then
                    message = message .. string.format(" \n Rack-Zone awareness constraints are met: OK")
                    if internal then
                        redis.call("ZADD", "db:canUpscale", 1, db )
                    end
                else
                    message = message ..string.format("\n Rack-Zone awareness constraints are not met! Racks " ..second[1] .. " and " .. third[1] .. " do not have enough capacity.")
                    indirect = false
                    if internal then
                        redis.call("ZADD", "db:canUpscale", 0, db )
                    end
                end
            end
        end

        if showPlan then
            -- If not direct can we upscale indirectly? If yes propose the action plan
            local canCreate = (redis.call("GET", "cancreate:" .. memory_size .. "G") == "true")
            if not direct and (canCreate or indirect) then
                local username = "admin@admin.com"
                local cluster_url = "https://cluster.dev-pierre-lab.demo.redislabs.com"
                local memorymb = memory_size * 1024 * 1024 * 1024
                local stepone = "curl -k -L -u \"" ..username ..":password\" -H \"Content-type:application/json\" -X PUT " ..cluster_url ..":9443/v1/bdbs/" ..db_id .." -d '{\"sharding\": true,\"shards_count\": " ..math.floor(nb_of_shards / 2) ..", \"shard_key_regex\":[{\"regex\":\".*\\\\{(?<tag>.*)\\\\}.*\"}, {\"regex\":\"(?<tag>.*)\"}]}'"
                local steptwo = "curl -k -L -u \"" ..username ..":password\" -H \"Content-type:application/json\" -X PUT " ..cluster_url .. ":9443/v1/bdbs/" .. db_id .. " -d '{\"memory_size\": " .. memorymb .. " }'"
                message ="It is actually not possible to upscale the database in only one step. \n The plan to upscale the database in two steps is the following: \n" ..stepone .. "\n" .. steptwo
            end
        end
    end

    return message
end
----Optimizations Variables & Functions
-- Variables for Optimisations actions
local Ousage =[[Optimize shard placement
You can enter the following arguments in the order:

Arguments:

    scope - Argument permits to define the scope of the optimization between Db, Node (N), Rack (R) or Cluster (C)
        - When you choose Db it means you try to make space on the nodes hosting the shards of the given database.
        - When you choose Node it means you want to free some space on a given node
        - When you choose Rack it means you want to free some space on a given rack
        - When you choose Cluster it means you want to gather 1G and 5G together on nodes which can not handle any further 25G shards.

    id - Is the identifier of the node or the rack.

    shard_size_min - To filter the minimum capacity size (GB) of the shards which can be moved (1,5 or 25)

    shard_size max - To filter the minimum capacity size (GB) of the shards which can be moved (1,5 or 25)

    shard_used_max - To filter the maximum memory used (GB) of the shards which can be moved (-1 for not limit).

    WIP - need - The amount of memory you need to free on the given scope & id.

    WIP - level - Is the level of deepness the optimization will Globally
        - level 1 will only migrate replica shards
        - level 2 will trigger failovers if required
        - level 3 will empty a Node as much as possible

]]
local scope = ARGV[2]
local id = ARGV[3]
local shard_size_min = ARGV[4]
local shard_size_max = ARGV[5]
local shard_used_max = ARGV[6]
local level = 1

if shard_used_max == -1 then
    shard_used_max = 25
end

--Temp data to make sure we dont overplan

local tempnodes = redis.call("zunionstore", "temp:nodes", 1 , "nodes")
--TODO  All Replica shards from a Node to another with for instance migrate node 2 all_slave_shards target_node 5 ?

---Functions

--Show Task Results

local function ShowSteps()

    -- Get the Redis list containing the elements
    local list_key = "temp:optimise:task"
    local list = redis.call('LRANGE', list_key, 0, -1)

    -- Initialize the output string
    local output = "The plan to execute would be the following:  \n\n"

    -- Loop through the elements in the list and append them to the output string
    for i, element in ipairs(list) do
        output = output .. element .. "\n"
    end

    -- Return the output string to Redis
    return output

end

local function optimizeNode(nodeid, levelo ,min, max, usedmax, exclude)
    -- level 1 ok
    -- level 2 todo
    local saved = 0
    --redis.call("UNLINK","temp:optimise:task")
    --redis.call("UNLINK","temp:optimise:fail")
    redis.call("zrangestore","temp:replicas:size", nodeid .. ":replicas:size", min , max, "BYSCORE")
    --for the case we want to optimise nodes hosting a specific database. we do not want to move that specific database.
    if exclude ~= nil then
        local excludeSet = redis.call("SMEMBERS", exclude ..":replicas")
        for i,excl in ipairs(excludeSet) do
            redis.call("ZREM", "temp:replicas:size", excl)
        end
    end
    redis.call("zrangestore","temp:replicas:used", nodeid .. ":replicas:used", 0 , usedmax, "BYSCORE")
    redis.call("ZINTERSTORE","temp:replicaset", 2, "temp:replicas:size", "temp:replicas:used")
    if (tonumber(redis.call("ZCARD", "temp:replicaset")) > 0) then
        local replicaSet = redis.call("ZINTER", 2, "temp:replicas:size", "temp:replicas:used")
        if isRackAware then
            for i,item in ipairs(replicaSet) do
                local master_shard = redis.call("GET",item .. ":linkedto")
                local master_rack = redis.call("HGET",master_shard,"rack-id")
                local shard_size = tonumber(redis.call("HGET",master_shard,"shard-size"))
                local shard_id = string.sub(item, 7)
                local status_shard = false
                local rank = 0
                redis.call("ZDIFFSTORE", "temp:nodes:candidates", 2, "nodes:ok:" .. shard_size .. "G", "racks:" .. master_rack .. ":nodes:ok:" .. shard_size .."G")
                redis.call("ZREM", "temp:nodes:candidates", nodeid)
                --for the case we want to exclude nodes to be considered candidates as when we try to make space for a database, we do not want to use space on node hosting the replica.
                -- a part if it would remain more than 25G after the move
                if exclude ~= nil then
                    local nodestoexclude = redis.call("ZREVRANGE", exclude .. ":nodes", 0 , -1)
                    for j,excl in ipairs(nodestoexclude)do
                        if (tonumber(redis.call("ZSCORE", "temp:nodes", excl )) - shard_size < 25) then
                        redis.call("ZREM", "temp:nodes:candidates", excl)
                        end
                    end
                end
                redis.call("ZINTERSTORE", "temp:nodes:candidates", 2, "temp:nodes:candidates" ,"nodes:candidates:25G" )
                local max = tonumber(redis.call("ZCARD", "temp:nodes:candidates"))
                while not status_shard and max > rank do
                    local candidates_node=redis.call("ZREVRANGE", "temp:nodes:candidates", rank, rank )
                    local node = candidates_node[1]
                    local capa_node = tonumber(redis.call("ZSCORE", "temp:nodes", node ))
                    if capa_node > shard_size then
                        local node_id = string.sub(node,6)
                        redis.call("rpush","temp:optimise:task","rladmin migrate shard ".. shard_id .." preserve_roles target_node " .. node_id )
                        redis.call("ZINCRBY", "temp:nodes", - shard_size ,nodeid )
                        redis.call("ZINCRBY", "temp:nodes", shard_size , node )
                        saved = saved + shard_size
                        status_shard = true
                    else
                        redis.call("rpush","temp:optimise:fail","No action possible on ".. shard_id .." with target node " .. node )
                        rank = rank+1
                    end
                end
            end
        end
        if saved > 0 then
        message = message .. "\n Plan for node ".. nodeid .. " is done. It would permit to make " .. saved .."G available.\n"
        message = message .. ShowSteps()
        else 
            message = message .. "\n No Plan for node ".. nodeid .. " done. There is no Shard meeting conditions."
        end
    else
        message = message .. "\n No Plan for node ".. nodeid .. " done. There is no Shard meeting conditions."
    end
    return message
end

local function optimizeRack(rackid, levelo ,min, max, usedmax)
    redis.call("UNLINK","temp:optimise:task")
    redis.call("UNLINK","temp:optimise:fail")
    local saved = 0
    redis.call("zrangestore","temp:replicas:size", rackid .. ":replicas:size", min , max, "BYSCORE")
    redis.call("zrangestore","temp:replicas:used", rackid .. ":replicas:used", 0 , usedmax, "BYSCORE")
    redis.call("ZINTERSTORE","temp:replicaset", 2, "temp:replicas:size", "temp:replicas:used")
    if (tonumber(redis.call("ZCARD", "temp:replicaset")) > 0) then
        local replicaSet = redis.call("ZINTER", 2, "temp:replicas:size", "temp:replicas:used")
        for i, item in ipairs(replicaSet) do
            local master_shard = redis.call("GET", item .. ":linkedto")
            local master_rack = redis.call("HGET", master_shard, "rack-id")
            local shard_size = tonumber(redis.call("HGET", master_shard, "shard-size"))
            local node_source = redis.call("HGET", item, "node-id")
            local shard_id = string.sub(item, 7)
            local status_shard = false
            local rank = 0
            redis.call("ZDIFFSTORE", "temp:nodes:candidates", 2, "nodes:ok:" .. shard_size .. "G",
                "racks:" .. master_rack .. ":nodes:ok:" .. shard_size .. "G")
            redis.call("ZDIFFSTORE", "temp:nodes:candidates", 2, "temp:nodes:candidates",
                "racks:" .. rackid .. ":nodes:ok:" .. shard_size .. "G")
            redis.call("ZINTERSTORE", "temp:nodes:candidates", 2, "temp:nodes:candidates", "nodes:candidates:25G")
            local max = tonumber(redis.call("ZCARD", "temp:nodes:candidates"))
            while not status_shard and max > rank do
                local candidate_node = redis.call("ZREVRANGE", "temp:nodes:candidates", rank, rank)
                local node = candidate_node[1]
                local capa_node = tonumber(redis.call("ZSCORE", "temp:nodes", node))
                if capa_node > shard_size then
                    local node_id = string.sub(redis.call("HGET", item, "node-id"), 6)
                    redis.call("rpush", "temp:optimise:task","rladmin migrate shard " .. shard_id .. " preserve_roles target_node " .. node_id)
                    redis.call("ZINCRBY", "temp:nodes", -shard_size, node_source)
                    redis.call("ZINCRBY", "temp:nodes", shard_size, node)
                    saved = saved + shard_size
                    status_shard = true
                else
                    redis.call("rpush", "temp:optimise:fail","No action possible on " .. shard_id .. " with target node " .. node)
                    rank = rank + 1
                end
            end
        end
        if saved > 0 then
            message = message .."\n Plan for Rack " .. rackid .. " done. It would permit to make " .. saved .. "G available. \n"
            message = message .. ShowSteps()
        else
            message = message .. "\n No Plan for Rack " .. rackid .. " done. There is no Shard meeting conditions."
        end
    else
        message = message .. "\n No Plan for Rack ".. rackid .. " done. There is no Shard meeting conditions."
    end
    
    return message
end

local function densifyNode(nodeid, min , max, usedmax)
    -- capacity of the node start with 5G
    -- then 1G
    -- no linked shard to that node & rack
    local memory_target = tonumber(redis.call("HGET", nodeid, "available_memory"))
    local memory_target_end = 0
    local added = 0
    local node_id = string.sub(redis.call("HGET",nodeid, "node-id"),6)
    --redis.call("UNLINK","temp:optimise:task")
    --redis.call("UNLINK","temp:optimise:fail")
    redis.call("zrangestore","temp:replicas:size", "cluster:replicas:size", min , max, "BYSCORE")
    redis.call("zrangestore","temp:replicas:used", "cluster:replicas:used", 0 , usedmax, "BYSCORE")
    redis.call("zinterstore","temp:replicas", 2, "temp:replicas:size","temp:replicas:used")
    redis.call("zdiffstore","temp:replicas", 2,"temp:replicas",nodeid .. ":replicas")
    local replicaSet = redis.call("ZREVRANGE", "temp:replicas", 0 , -1)
    if isRackAware then
        for i,item in ipairs(replicaSet) do
            local target_rack = redis.call("HGET", nodeid, "rack-id")
            local master_shard = redis.call("GET",item .. ":linkedto")
            local master_rack = redis.call("HGET",master_shard,"rack-id")
            local shard_size = tonumber(redis.call("HGET",master_shard,"shard-size"))
            local shard_id = string.sub(item, 7)
            if master_rack ~= target_rack and memory_target > shard_size and memory_target > 1 then
                redis.call("rpush","temp:optimise:task","rladmin migrate shard ".. shard_id .." preserve_roles target_node " .. node_id )
                added = added + shard_size
                
            else
                redis.call("rpush","temp:optimise:fail","No action possible on shard".. shard_id .." with target node " .. node_id )

            end
        end
    end
    memory_target_end = memory_target - added
    if added > 0 then
        message = message .. "We can add " .. added .."G to the node " .. nodeid ..". " .. memory_target_end .."G would be remaining after change. \n" 
        message = message .. ShowSteps()
        else
            message = message .. "\n No Plan actually for the Cluster, " .. nodeid .. " can not be densified. There is no Shard meeting conditions."
    end
    

end

local function optimizeCluster(min , max,usedmax)
    -- First let's define the target node
    -- It is a Node which cannot accept anymore 25G shards and is far to be able.
    --redis.call("UNLINK","temp:optimise:task")
    --redis.call("UNLINK","temp:optimise:fail")
    redis.call("ZINTERSTORE", "temp:candidates:nodes", 2, "nodes:host", "nodes:candidates:25G")
    redis.call("ZDIFFSTORE", "temp:candidates:nodes",2,"temp:candidates:nodes","nodes:ok:25G")
    local candidate_node = redis.call("ZRANGE", "temp:candidates:nodes", 0, 0 )
    densifyNode(candidate_node[1],min,max,usedmax)
end



local function optimizeDB(dbid,ramtofree)
    -- try to free an amount of ram on master node and shard node in order to be able to scale
    -- the amount of memory should be the necessary to host an additional 25G
    local exist = (tonumber(redis.call("zrank", "db", dbid)) ~= nil)
    if exist then
        local nodesSet = redis.call("ZRANGE", dbid ..":nodes", 0 , -1)
        for i,item in ipairs(nodesSet) do
            
            optimizeNode(item,1,1,5,5,dbid)
            
        end
    else 
        message = message .. "The database with id " .. dbid .. " does not exist."
    end
    return message
end

local function capaUpDB()

    local dbSet = redis.call("ZREVRANGE", "db" , 0 , -1)
    local internal = true
    local showPlan = false
    for i,db in ipairs(dbSet) do
        local dbscore = tonumber(redis.call("ZSCORE", "db", db))
        local replication = (redis.call("HGET", db, "replication") == "enabled")
        if replication then
            if dbscore == 2 then
                canUpscale(db,10,1,true,showPlan,internal)
            elseif dbscore == 10 then
                canUpscale(db,50,1,true,showPlan,internal)
            elseif dbscore == 50 then
                canUpscale(db,100,2,true,showPlan,internal)
            elseif dbscore == 100 then
                canUpscale(db,200,4,true,showPlan,internal)
            end
        end
    end
    message = message .. "OK"
    return message
end


--Help
-- Function to display help information for the script
local function Help()
    local help = [[This is the Main help message. This script permits you to execute several Actions
Usage:

redis-cli --raw EVAL capaplan.lua 0 [action] ... [Options]

Arguments:

action - Depending of the choice the script will execute different actions and will need different Arguments.

Possible Values for action:

- Calculate the Cluster CAPACITY => CAPACITY or CAPA
- Establish Shard CORRESPONDANCE => CORRESPONDANCE or CORR
- Determine if you CAN CREATE a database/DB => CANCREATE or CDB
- Determine if you CAN UPSCALE a database/DB => CANUPSCALE or UDB
- OPTIMIZE the shards placement of the Cluster => OPTIMIZE or O

To get Help for any action:
redis-cli --raw EVAL capaplan.lua 0 [action] Help
OR
redis-cli --raw EVAL capaplan.lua 0 [action] -H
 ]]

    message = message .. help
    return message
end

local function OshowHelp()
    print("Optimize shard placement script")
    print("Usage: ")
    print("   redis-cli --eval optimize_shard.lua [scope] [id] [shard_size_min] [shard_size_max] [shard_used_max] [level] [exclude]\n")
    print("Arguments:")
    print("   scope - Argument permits to define the scope of the optimization between Db, Node (N), Rack (R) or Cluster (C).")
    print("          When you choose Db it means you try to make space on the nodes hosting its shards in order to scale.")
    print("          When you choose Node it means you want to free some space on a given node.")
    print("          When you choose Rack it means you want to free some space on a given rack.")
    print("          When you choose Cluster it means you want to gather 1G and 5G together on nodes which can not handle any further 25G shards.")
    print("   id - Is the identifier of the node or the rack.")
    print("   shard_size_min - To filter the minimum capacity size (GB) of the shards which can be moved (1, 5 or 25).")
    print("   shard_size_max - To filter the maximum capacity size (GB) of the shards which can be moved (1, 5 or 25).")
    print("   shard_used_max - To filter the maximum memory used (GB) of the shards which can be moved (-1 for not limit).")
    print("   level - Is the level of deepness the optimization will apply:")
    print("           - level 1 will only migrate replica shards.")
    print("           - level 2 will trigger failovers if required.")
    print("           - level 3 will empty a Node as much as possible.")

end



-- Main


if #ARGV == 1 and (string.upper(ARGV[1]) == "-H" or string.upper(ARGV[1]) == "HELP") then
    Help()
end

-- Capacity
if (string.upper(action) == "CAPACITY" or string.upper(action) == "CAPA") then
    -----Usage/Help
    if #ARGV == 2 and (string.upper(ARGV[2]) == "-H" or string.upper(ARGV[2]) == "HELP") then
        message = calcusage
        
    elseif #ARGV == 2 and (string.upper(ARGV[2]) ~= "-H" or string.upper(ARGV[2]) ~= "HELP") then 
        capacity(size)
    else 
        message = "Wrong number of Arguments for the ".. action .. " function: \n"
        message = message .. calcusage
    end
end

-- Correspondance
if (string.upper(action) == "CORRESPONDANCE" or string.upper(action) == "CORR") then
    -----Usage/Help
    if #ARGV == 2 and (string.upper(ARGV[2]) == "-H" or string.upper(ARGV[2]) == "HELP") then
        message = corrHelp
        
    elseif #ARGV == 1 then 
        correspondanceShards()
        capaUpDB()
    else 
        message = "Wrong number of Arguments for the ".. action .. " function: \n"
        message = message .. corrHelp
    end
end

-- Can Create
if (string.upper(action) == "CREATE" or string.upper(action) == "CDB" or string.upper(action) == "CANCREATE") then
    -----Usage/Help
    if #ARGV == 2 and (string.upper(ARGV[2]) == "-H" or string.upper(ARGV[2]) == "HELP") then
        message = createusage
        
    elseif #ARGV == 4 then 
        local memory_size = tonumber(ARGV[2])
        local nb_of_shards = tonumber(ARGV[3])
        local replication = (ARGV[4] == "true")
        canCreate(memory_size,nb_of_shards,replication)
    else 
        message = "Wrong number of Arguments for the ".. action .. " function: \n"
        message = message .. createusage
    end
end
-- Can Upscale
if (string.upper(action) == "UPSCALE" or string.upper(action) == "UDB" or string.upper(action) == "CANUPSCALE") then
    -----Usage/Help

    if #ARGV == 2 and (string.upper(ARGV[2]) == "-H" or string.upper(ARGV[2]) == "HELP") then
        message = upscaleusage
        
    elseif #ARGV == 6 then 
        canUpscale(db,memory_size,nb_of_shards,replication,showPlan,false)
    else 
        message = "Wrong number of Arguments for the ".. action .. " function: \n"
        message = message .. upscaleusage
    end
end

--Optimize
if (string.upper(action) == "OPTIMIZE" or string.upper(action) == "O") then

    ----- Usage/Help
    if #ARGV == 2 and (string.upper(ARGV[2]) == "-H" or string.upper(ARGV[2]) == "HELP") then

        message = Ousage
        
    end

    ----- Optimise a given Database Nodes

    if string.upper(scope) == "DB" or string.upper(scope) == "D"  then
        if #ARGV == 3 then
            if level == 1 then
                optimizeDB(id)
                
            end
        else
            message = "Wrong number of Arguments for the ".. action .. " function: \n"
            message = message .. Ousage
        end
    end

    ----- Optimise a given Node

    if string.upper(scope) == "NODE" or string.upper(scope) == "N" then
        if #ARGV == 6 then
            if level == 1 then
                optimizeNode(id,1,shard_size_min,shard_size_max,shard_used_max)
                
                
            end
        else
            message = "Wrong number of Arguments for the ".. action .. " function: \n"
            message = message .. Ousage
        end
    end

    ----- Optimise a given Rack
    if string.upper(scope) == "RACK" or string.upper(scope) == "R" or string.upper(scope) == "AZ" then
        if #ARGV == 6 then
            if level == 1 then
            optimizeRack(id,1,shard_size_min,shard_size_max,shard_used_max)
            end
        else
            message = "Wrong number of Arguments for the ".. action .. " function: \n"
            message = message .. Ousage
        end
    end

    -- Optimise Cluster
    if string.upper(scope) == "CLUSTER" or string.upper(scope) == "C" then
        if #ARGV == 5 then
            if level == 1 then
                shard_size_min = ARGV[3]
                shard_size_max = ARGV[4]
                shard_used_max = ARGV[5]
                optimizeCluster(shard_size_min,shard_size_max,shard_used_max)
                message = message .. ShowSteps()
                
            end
        else 
            message = "Wrong number of Arguments for the ".. action .. " function: \n"
            message = message .. Ousage
        end
    end

    if #ARGV == 2 and (string.upper(ARGV[2]) ~= "-H" or string.upper(ARGV[2]) ~= "HELP") then
        message = "Wrong number of Arguments for the ".. action .. " function: \n"
        message = message .. Ousage
        
    end

end

if message == "" or message == nil then
    redis.call("INCRBY", "loser", 1)
    local lose = tonumber(redis.call("GET", "loser"))
    if lose == 1 then
        message = "Wrong set of options. Did you enter action, scope and all the needed options?"
    elseif lose == 2 then
        message = "Again: Wrong set of options. Are you sure you entered action, scope and all the needed options?"
    elseif lose == 3 then
        message = "Maybe you should read the Help section or the documentation ..."
    elseif lose == 4 then
        message = "Unfortunately Google or ChatGPT can not help you here ..."
    elseif lose == 5 then
        message = "Just use the command : \n redis-cli -h <host> -p <port> EVAL \"$(cat lua/capaplan.lua )\" 0 Help \n OR \n redis-cli --raw -h <host> -p <port> EVAL \"$(cat lua/capaplan.lua )\" 0 [ACTION] Help"
    elseif lose == 6 then
        message = "I will make it for you:\n"
        Help()
    elseif  6 < lose and lose < 10  then
        local pourcentage=100*(lose-6)
        message = "Again: Wrong set of options. Are you " .. pourcentage .."% sure you entered action, scope and all the needed options?"
    elseif lose == 10 then
        message = "10 in a row!!!! Maybe you should take a break..."
        redis.call("SET", "loser", 1)
    end
else
    redis.call("SET", "loser", 0)
end
return message