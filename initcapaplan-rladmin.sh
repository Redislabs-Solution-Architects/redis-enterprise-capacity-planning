#!/bin/bash

##Path config
export PATH="/opt/redislabs/bin:$PATH"

##Utility redis database
bdbid=1
bdb-cli $bdbid flushdb async
##Fetch information on the nodes
nodes=`rladmin status nodes extra all | awk -F '[/ ]+' '/GB/ {print $1,$14,$15,$22}' | tr -d \*GB`

nodesinfo=`rladmin status nodes extra all`
shardsinfo=`rladmin status shards extra all`
##Fetch nodes innformation and store it to Redis database
echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "hset "$1" node-id "$1" rack-id "$22" available_memory "$14" total_available_memory "$15}' | tr -d \*GB | bdb-cli $bdbid
#to be double validated
echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "hset "$1" node-id "$1" rack-id "$22" available_memory "$14" total_available_memory "$15}' | tr -d \*GB | awk '/M/ {print $1 " " $2 " " $3 " " $4 " " $5 " " $6 " " $7 " 0.0 " $9 " " $10}' | bdb-cli $bdbid

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd nodes "$14" "$1}' | tr -d \*GB | bdb-cli $bdbid

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd nodes "$14" "$1}' | tr -d \*GB | awk '/M/ {print $1 " " $2 " 0.0 " $4}' | bdb-cli $bdbid

##Fetch Rack-Id information and store it to Redis Database

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd rack:"$22" "$14" "$1}' | tr -d \*GB | bdb-cli $bdbid

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd rack:"$22" "$14" "$1}' | tr -d \*GB | awk '/M/ {print $1 " " $2 " 0.0 " $4}' | bdb-cli $bdbid

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "sadd racks "$22}' | tr -d \*GB | bdb-cli $bdbid


##Fetch shards information and store it to Redis database

echo "$shardsinfo" | awk -F '[/ ]+' '/redis/  {print "hset "$3" node-id "$4" db-id "$1" shard-id "$3" role "$5" slots "$6" used_memory "$7" status "$12}' | bdb-cli $bdbid

echo "$shardsinfo" | awk -F '[/ ]+' '/redis/  {print "sadd shards "$3}' | bdb-cli $bdbid

echo "$shardsinfo" | awk -F '[/ ]+' '/redis/  {print "sadd "$1":shards "$3}' | bdb-cli $bdbid
##Fetch databases information and store it to Redis database

rladmin status databases extra all | awk -F '[/ ]+' '/redis/  {print "hset "$1" db-id "$1" db-name "$2" number-shards "$5" shard_placement "$6" replication "$7}' | tr -d \*GB | bdb-cli $bdbid

response=$(curl -k -L -X GET -u "admin@admin.com:admin" -H "Content-type:application/json" https://localhost:9443/v1/bdbs?fields=uid,memory_size)

bdb-cli $bdbid unlink db
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
    bdb-cli $bdbid hset $dbid memory_limit $memory_size_gb
    bdb-cli $bdbid zadd db $memory_size_gb $dbid
done

##Fetch endpoints information and store it to Redis database

rladmin status endpoints extra all | awk -F '[/ ]+' '/endpoint/  {print "hset "$3" endpoint-id "$3" db-id "$1" node-id "$4" role "$5" status "$7}' | tr -d \*GB | bdb-cli $bdbid

##Check if the cluster is rack-aware
isRackAware=true
bdb-cli $bdbid SET isRackAware $isRackAware
NodeRack=`bdb-cli $bdbid hget node:1 rack-id`
if [ "$NodeRack" = "-" ]; then
    isRackAware=false
    bdb-cli $bdbid SET isRackAware $isRackAware
fi

bdb-cli $bdbid EVAL "$(cat lua/capaplan.lua)" 0 CAPA 1
bdb-cli $bdbid EVAL "$(cat lua/capaplan.lua)" 0 CAPA 5
bdb-cli $bdbid EVAL "$(cat lua/capaplan.lua)" 0 CAPA 25
bdb-cli $bdbid EVAL "$(cat lua/capaplan.lua)" 0 CORR