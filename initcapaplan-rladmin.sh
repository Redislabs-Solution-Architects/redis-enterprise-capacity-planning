#!/bin/bash

##Path config
export PATH="/opt/redislabs/bin:$PATH"

# Help                                                     

Help()
{
   # Display Help
   echo "This script aims to get information from Redis Enterprise Cluster using rladmin utility commands and populate a Redis database in order to perform capacity planning."
   echo
   echo "options:"
   echo "-h     Print this Help."
   echo "-a     Hostname of the Redis Enterprise Cluster which link to its REST API. Default=locahost"
   echo "-r     Hostname of the Redis Database which will host the generated data from this script. Default=locahost"
   echo "-p     Port of the Redis Database which will host the generated data from this script. Default=6379"
   echo
}

while getopts a:r:p:h flag
do
    case "${flag}" in
        h) Help
              exit;;
        a) # Hostname of the API
          redis_cluster_api_url=${OPTARG};;
        r) # Hostname of the redis database to host data
          redis_hostname=${OPTARG};;
        p) # Port of the redis database to host data
          redis_port=${OPTARG};;
        \?) # Invalid option
         echo "Error: Invalid option"
         exit;;
    esac
done

#To make sure we deal with float with dots
export LC_NUMERIC="en_US.UTF-8"

#To make Inputs with

if [ -z $redis_cluster_api_url ]
  then
    echo "No arguments supplied for API hostname. Using default "
    redis_cluster_api_url="localhost"
fi

if [ -z $redis_hostname ]
  then
    echo "No arguments supplied for Redis hostname. Using default."
    redis_hostname="localhost"
fi

if [ -z $redis_port ]
  then
    echo "No arguments supplied for Redis Port. Using default. "
    redis_port=6379
fi

redis="redis-cli -h $redis_hostname -p $redis_port"

##Utility redis database
EXIST=`redis-cli -h $redis_hostname -p $redis_port EXISTS PLOptimizerVersion`
if [ "$EXIST" == "1" ]; then
redis-cli -h $redis_hostname -p $redis_port flushdb async
fi
redis-cli -h $redis_hostname -p $redis_port SET PLOptimizerVersion 0.0000001alpha
##Fetch information on the nodes
nodes=`rladmin status nodes extra all | awk -F '[/ ]+' '/GB/ {print $1,$14,$15,$22}' | tr -d \*GB`

nodesinfo=`rladmin status nodes extra all`
shardsinfo=`rladmin status shards extra all`
##Fetch nodes information and store it to Redis database
echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "hset "$1" node-id "$1" rack-id "$22" available_memory "$14" total_available_memory "$15}' | tr -d \*GB | $redis

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "hset "$1" node-id "$1" rack-id "$22" available_memory "$14" total_available_memory "$15}' | tr -d \*GB | awk '/M/ {print $1 " " $2 " " $3 " " $4 " " $5 " " $6 " " $7 " 0.0 " $9 " " $10}' | $redis

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd nodes "$14" "$1}' | tr -d \*GB | $redis

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd nodes "$14" "$1}' | tr -d \*GB | awk '/M/ {print $1 " " $2 " 0.0 " $4}' | $redis

##Fetch Rack-Id information and store it to Redis Database

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd rack:"$22" "$14" "$1}' | tr -d \*GB | $redis

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "zadd rack:"$22" "$14" "$1}' | tr -d \*GB | awk '/M/ {print $1 " " $2 " 0.0 " $4}' | $redis

echo "$nodesinfo" | awk -F '[/ ]+' '/GB/  {print "sadd racks "$22}' | tr -d \*GB | $redis

##Fetch shards information and store it to Redis database

echo "$shardsinfo" | awk -F '[/ ]+' '/redis/  {print "hset "$3" node-id "$4" db-id "$1" shard-id "$3" role "$5" slots "$6" used_memory "$7" status "$12}' | $redis

echo "$shardsinfo" | awk -F '[/ ]+' '/redis/  {print "sadd shards "$3}' | $redis

echo "$shardsinfo" | awk -F '[/ ]+' '/redis/  {print "sadd "$1":shards "$3}' | $redis

##Fetch databases information and store it to Redis database

rladmin status databases extra all | awk -F '[/ ]+' '/redis/  {print "hset "$1" db-id "$1" db-name "$2" number-shards "$5" shard_placement "$6" replication "$7}' | tr -d \*GB | $redis

response=$(curl -k -L -X GET -u "admin@admin.com:admin" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/bdbs?fields=uid,memory_size)

redis-cli -h $redis_hostname -p $redis_port unlink db

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
    redis-cli -h $redis_hostname -p $redis_port hset $dbid memory_limit $memory_size_gb
    redis-cli -h $redis_hostname -p $redis_port zadd db $memory_size_gb $dbid
done

##Fetch endpoints information and store it to Redis database
##Not used yet but may be usefull to migrate endpoints if required

rladmin status endpoints extra all | awk -F '[/ ]+' '/endpoint/  {print "hset "$3" endpoint-id "$3" db-id "$1" node-id "$4" role "$5" status "$7}' | tr -d \*GB | $redis

##Check if the cluster is rack-aware
isRackAware=true
redis-cli -h $redis_hostname -p $redis_port SET isRackAware $isRackAware
NodeRack=`redis-cli -h $redis_hostname -p $redis_port hget node:1 rack-id`
if [ "$NodeRack" = "-" ]; then
    isRackAware=false
    redis-cli -h $redis_hostname -p $redis_port SET isRackAware $isRackAware
fi

redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 1
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 5
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 25
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CORR