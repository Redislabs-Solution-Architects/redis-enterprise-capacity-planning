#!/bin/bash

##Path config
#export PATH="/opt/redislabs/bin:$PATH"

##Utility redis database
#bdbid=1
EXIST=`redis-cli EXISTS PLOptimizerVersion`
if [ "$EXIST" == "1" ]; then
redis-cli flushdb async
fi
redis-cli SET PLOptimizerVersion 0.0000001alpha
##Fetch information on the nodes
#nodes=`rladmin status nodes extra all | awk -F '[/ ]+' '/GB/ {print $1,$14,$15,$22}' | tr -d \*GB`

nodesinfo="CLUSTER NODES:
NODE:ID ROLE   ADDRESS  EXTERNAL_ADDRESS HOSTNAME              MASTERS SLAVES OVERBOOKING_DEPTH SHARDS CORES FREE_RAM        PROVISIONAL_RAM FLASH           AVAILABLE_FLASH VERSION    SHA    RACK-ID        STATUS
*node:1 master 10.1.1.2 35.195.180.152   pierre-lab-dev-node-0 1       1      43.39GB           2/100  8     60.63GB/62.81GB 43.39GB/51.5GB  35.96GB/38.58GB 22.24GB/30.87GB 6.2.10-100 f16907 europe-west1-b OK
node:2  slave  10.1.2.3 35.233.88.74     pierre-lab-dev-node-1 1       1      43.55GB           2/100  8     60.78GB/62.81GB 43.55GB/51.5GB  35.96GB/38.58GB 22.24GB/30.87GB 6.2.10-100 f16907 europe-west1-c OK
node:3  slave  10.1.3.2 34.76.116.188    pierre-lab-dev-node-2 1       0      49.49GB           0/100  8     60.79GB/62.81GB 24.49GB/51.5GB  35.96GB/38.58GB 28.24GB/30.87GB 6.2.10-100 f16907 europe-west1-d OK
node:4  slave  10.1.1.3 34.78.232.123    pierre-lab-dev-node-3 0       1      49.49GB           0/100  8     60.8GB/62.81GB  24.49GB/51.5GB  35.96GB/38.58GB 28.24GB/30.87GB 6.2.10-100 f16907 europe-west1-b OK
node:5  slave  10.1.2.2 34.22.253.38     pierre-lab-dev-node-4 1       1      39.6GB            2/100  8     60.79GB/62.81GB 39.6GB/51.5GB   35.96GB/38.58GB 18.24GB/30.87GB 6.2.10-100 f16907 europe-west1-c OK"
shardsinfo="SHARDS:
DB:ID             NAME            ID            NODE        ROLE        SLOTS         USED_MEMORY          BACKUP_PROGRESS              RAM_FRAG        WATCHDOG_STATUS              STATUS
db:1              capaplan        redis:1       node:1      master      0-16383       14.72MB              N/A                          -6.47MB         OK                           OK
db:1              capaplan        redis:2       node:2      slave       0-16383       14.6MB               N/A                          -6.38MB         OK                           OK
db:2              capaplan        redis:3       node:3      master      0-16383       58.72MB              N/A                          -6.47MB         OK                           OK
db:2              capaplan        redis:4       node:4      slave       0-16383       58.6MB               N/A                          -6.38MB         OK                           OK
db:4              db5G1           redis:5       node:5      master      0-16383       58.01MB              N/A                          -51.33MB        OK                           OK
db:4              db5G1           redis:6       node:1      slave       0-16383       57.97MB              N/A                          -51.35MB        OK                           OK
db:5              db5G2           redis:7       node:2      master      0-16383       58.09MB              N/A                          -51.38MB        OK                           OK
db:5              db5G2           redis:8       node:5      slave       0-16383       58.05MB              N/A                          -51.31MB        OK                           OK"

databasesinfo="DATABASES:
DB:ID NAME     TYPE  STATUS SHARDS PLACEMENT REPLICATION PERSISTENCE ENDPOINT                                                    EXEC_STATE EXEC_STATE_MACHINE BACKUP_PROGRESS MISSING_BACKUP_TIME REDIS_VERSION
db:1  capaplan redis active 1      sparse    enabled     disabled    redis-14836.cluster.dev-pierre-lab.demo.redislabs.com:14836 N/A        N/A                N/A             N/A                 6.2.5
db:2  testscal redis active 1      sparse    enabled     disabled    redis-14837.cluster.dev-pierre-lab.demo.redislabs.com:14837 N/A        N/A                N/A             N/A                 6.2.5
db:4  db5G1    redis active 1      sparse    enabled     disabled    redis-19543.cluster.dev-pierre-lab.demo.redislabs.com:19543 N/A        N/A                N/A             N/A                 6.2.5
db:5  db5G2    redis active 1      sparse    enabled     disabled    redis-10331.cluster.dev-pierre-lab.demo.redislabs.com:10331 N/A        N/A                N/A             N/A                 6.2.5"

endpointsinfo="ENDPOINTS:
DB:ID             NAME                        ID                                      NODE                 ROLE                 SSL              WATCHDOG_STATUS
db:1              capaplan                    endpoint:1:1                            node:1               single               No               OK
db:2              capaplan                    endpoint:2:1                            node:3               single               No               OK
db:4              db5G1                       endpoint:4:1                            node:5               single               No               OK
db:5              db5G2                       endpoint:5:1                            node:2               single               No               OK"

##Fetch nodes information and store it to Redis database
echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "hset "$1" node-id "$1" rack-id "$22" available_memory "$14" total_available_memory "$15}' | tr -d \*GB | redis-cli
#to be double validated
echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "hset "$1" node-id "$1" rack-id "$22" available_memory "$14" total_available_memory "$15}' | tr -d \*GB | awk '/M/ {print $1 " " $2 " " $3 " " $4 " " $5 " " $6 " " $7 " 0.0 " $9 " " $10}' | redis-cli

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd nodes "$14" "$1}' | tr -d \*GB | redis-cli 

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd nodes "$14" "$1}' | tr -d \*GB | awk '/M/ {print $1 " " $2 " 0.0 " $4}' | redis-cli 

##Fetch Rack-Id information and store it to Redis Database

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd rack:"$22" "$14" "$1}' | tr -d \*GB | redis-cli 

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd rack:"$22" "$14" "$1}' | tr -d \*GB | awk '/M/ {print $1 " " $2 " 0.0 " $4}' | redis-cli 

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "sadd racks "$22}' | tr -d \*GB | redis-cli 


##Fetch shards information and store it to Redis database

echo "$shardsinfo" | awk -F '[/ ]+' '/redis/  {print "hset "$3" node-id "$4" db-id "$1" shard-id "$3" role "$5" slots "$6" used_memory "$7" status "$12}' | redis-cli 

echo "$shardsinfo" | awk -F '[/ ]+' '/redis/  {print "sadd shards "$3}' | redis-cli 

echo "$shardsinfo" | awk -F '[/ ]+' '/redis/  {print "sadd "$1":shards "$3}' | redis-cli 
##Fetch databases information and store it to Redis database

echo "$databasesinfo" | awk -F '[/ ]+' '/redis/  {print "hset "$1" db-id "$1" db-name "$2" number-shards "$5" shard_placement "$6" replication "$7}' | tr -d \*GB | redis-cli 

#response=$(curl -k -L -X GET -u "admin@admin.com:admin" -H "Content-type:application/json" https://localhost:9443/v1/bdbs?fields=uid,memory_size)
response="[{\"uid\":1, \"memory_size\": 2147483648},{\"uid\":2, \"memory_size\": 53687091200},{\"uid\":4, \"memory_size\": 10737418240},{\"uid\":5, \"memory_size\": 10737418240}]"
redis-cli  unlink db
# Iterate over each object in the json response
for row in $(echo "${response}" | jq -r '.[] | @base64'); do
    _jq() {
     echo ${row} | base64 --decode | jq -r ${1}
    }

    # Extract values from json object
    memory_size=$(_jq '.memory_size')
    uid=$(_jq '.uid')
    dbid="db:$uid"
    memory_size_gb=$(awk "BEGIN {print int($memory_size/1024/1024/1024)}")
    # Do something with the values
    redis-cli  hset $dbid memory_limit $memory_size_gb
    redis-cli  zadd db $memory_size_gb $dbid
done

##Fetch endpoints information and store it to Redis database

echo "$endpointsinfo" | awk -F '[/ ]+' '/endpoint/  {print "hset "$3" endpoint-id "$3" db-id "$1" node-id "$4" role "$5" status "$7}' | tr -d \*GB | redis-cli 

##Check if the cluster is rack-aware
isRackAware=true
redis-cli  SET isRackAware $isRackAware
NodeRack=`redis-cli  hget node:1 rack-id`
if [ "$NodeRack" = "-" ]; then
    isRackAware=false
    redis-cli  SET isRackAware $isRackAware
fi

redis-cli --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 1
redis-cli --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 5
redis-cli --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 25
redis-cli --raw EVAL "$(cat lua/capaplan.lua)" 0 CORR