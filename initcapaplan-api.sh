#!/bin/bash


# Help                                                     

Help()
{
   # Display Help
   echo "This script aims to get information from Redis Enterprise Cluster using its REST API and populate a Redis database in order to perform capacity planning."
   echo
   echo "options:"
   echo "-h     Print this Help."
   echo "-a     Hostname of the Redis Enterprise Cluster which link to its REST API. Default=locahost"
   echo "-r     Hostname of the Redis Database which will host the generated data from this script. Default=locahost"
   echo "-p     Port of the Redis Database which will host the generated data from this script. Default=6379"
   echo "-u     Username for the Redis Enterprise Cluster API. Default=admin@admin.com"
   echo "-s     Password for the Redis Enterprise Cluster API. Default=admin"
   echo
}

while getopts a:r:p:u:s:h flag
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
        u) # username for API
          api_username=${OPTARG};;
        s) # Password for API
          api_password=${OPTARG};;
        \?) # Invalid option
         echo "Error: Invalid option"
         Help
         exit;;
    esac
done

#echo "$redis_cluster_api_url"
##Path config
#export PATH="/opt/redislabs/bin:$PATH"

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
if [ -z $api_username ]
  then
    echo "No arguments supplied for API Username. Using default. "
    api_username="admin@admin.com"
fi

if [ -z $api_password ]
  then
    echo "No arguments supplied for API Password. Using default. "
    api_password="admin"
fi

redis="redis-cli -h $redis_hostname -p $redis_port"

##Utility redis database
EXIST=`redis-cli -h $redis_hostname -p $redis_port EXISTS PLOptimizerVersion`
if [ "$EXIST" == "1" ]; then
redis-cli -h $redis_hostname -p $redis_port flushdb async
fi
redis-cli -h $redis_hostname -p $redis_port SET PLOptimizerVersion 0.0000001alpha

# Json Parsing functions
parse_bdbs_json_objects() {
  local json_object=$1
  local memory_size=$(jq -r '.memory_size' <<< "${json_object}")
  local uid=$(jq -r '.uid' <<< "${json_object}")
  local db_name=$(jq -r '.name' <<< "${json_object}")
  local shards_count=$(jq -r '.shards_count' <<< "${json_object}")
  local shards_placement=$(jq -r '.shards_placement' <<< "${json_object}")
  local replication=$(jq -r '.replication' <<< "${json_object}")
  local dbid="db:${uid}"
  local memory_size_gb=$(awk "BEGIN {print int($memory_size/1024/1024/1024)}")
  echo $($redis hset $dbid db-id $dbid db-name $db_name number-shards $shards_count shard_placement $shards_placement replication $replication memory_limit $memory_size_gb)
  echo $($redis zadd db $memory_size_gb $dbid)
  local bdbsstatsjson=$(curl -s -k -L -X GET -u "${api_username}:${api_password}" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/bdbs/stats/last/$uid)
  local responsetoget=$(echo "${bdbsstatsjson}" | jq -c '.')
    while read -r rows; do
      local memory_used=$(jq -r '.used_memory' <<< "${rows}")
      local memory_used_gb=$(awk "BEGIN {printf \"%.2f\", $memory_used/1024/1024/1024}")
      echo $($redis hset $dbid memory_used $memory_used_gb)
    done <<< "$(echo "${responsetoget}" | jq -c '.[]')"
  #endpoints
  #local endpoint_uid =$(jq -r '.endpoints[].uid' <<< "${json_object}")
  #local policy =$(jq -r '.endpoints[].proxy_policy' <<< "${json_object}")
}

parse_nodes_json_objects() {
  local json_object=$1
  local uid=$(jq -r '.uid' <<< "${json_object}")
  local rack_id=$(jq -r '.rack_id' <<< "${json_object}")
  local shards_count=$(jq -r '.shard_count' <<< "${json_object}")
  local total_memory=$(jq -r '.total_memory' <<< "${json_object}")
  local node_id="node:${uid}"
  local total_available_memory=$(awk "BEGIN {printf \"%.2f\", 0.82*$total_memory/1024/1024/1024}")
  echo $($redis hset $node_id node-id $node_id rack-id $rack_id number-shards $shards_count total_available_memory $total_available_memory)
  echo $($redis sadd racks $rack_id)
  local nodestatsjson=$(curl -s -k -L -X GET -u "${api_username}:${api_password}" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/nodes/stats/last/$uid)
  local responsetoget=$(echo "${nodestatsjson}" | jq -c '.')
    while read -r rows; do
      local available_memory=$(jq -r '.provisional_memory' <<< "${rows}")
      local available_memory_gb=$(awk "BEGIN {printf \"%.2f\", $available_memory/1024/1024/1024}")
      echo $($redis hset $node_id available_memory $available_memory_gb)
      echo $($redis zadd nodes $available_memory_gb $node_id)
    done <<< "$(echo "${responsetoget}" | jq -c '.[]')"
}

parse_shards_json_objects() {
  local json_object=$1
  local uid=$(jq -r '.uid' <<< "${json_object}")
  local node_uid=$(jq -r '.node_uid' <<< "${json_object}")
  local bdb_uid=$(jq -r '.bdb_uid' <<< "${json_object}")
  local role=$(jq -r '.role' <<< "${json_object}")
  local slots=$(jq -r '.assigned_slots' <<< "${json_object}")
  local status=$(jq -r '.detailed_status' <<< "${json_object}")
  local shard_id="redis:${uid}"
  local node_id="node:${node_uid}"
  local db_id="db:${bdb_uid}"
  local zdbsh="${db_id}:shards"
  echo $($redis hset $shard_id shard-id $shard_id node-id $node_id db-id $db_id role $role slots $slots status $status)
  echo $($redis sadd shards $shard_id)
  echo $($redis sadd $zdbsh $shard_id)
  local shardstatsjson=$(curl -s -k -L -X GET -u "${api_username}:${api_password}" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/shards/stats/last/$uid)
  local responsetoget=$(echo "${shardstatsjson}" | jq -c '.')
    while read -r rows; do
      local used_memory=$(jq -r '.used_memory' <<< "${rows}")
      local used_memory_int=$(awk "BEGIN {print int($used_memory)}")
        if [ $((used_memory_int)) -lt $((1024*1024*1024)) ];then
            local used_memory_nb_final=$(awk "BEGIN {printf \"%.2f\", $used_memory_int/1024/1024}")
            local used_final="${used_memory_nb_final}MB"
        else
            local used_memory_nb_final=$(awk "BEGIN {printf \"%.2f\", $used_memory_int/1024/1024/1024}")
            local used_final="${used_memory_nb_final}G"
        fi
      echo $($redis hset $shard_id used_memory $used_final)
    done <<< "$(echo "${responsetoget}" | jq -c '.[]')"

}
#BDBS
bdbsjson=$(curl -s -k -L -X GET -u "${api_username}:${api_password}" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/bdbs)


  responsebdbs=$(echo "${bdbsjson}" | jq -c '.')
  while read -r row; do
    parse_bdbs_json_objects "${row}"
  done <<< "$(echo "${responsebdbs}" | jq -c '.[]')"

#NODES

nodesjson=$(curl -s -k -L -X GET -u "${api_username}:${api_password}" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/nodes)

  responsenodes=$(echo "${nodesjson}" | jq -c '.')
  while read -r row; do
    parse_nodes_json_objects "${row}"
  done <<< "$(echo "${responsenodes}" | jq -c '.[]')"

#SHARDS
shardsjson=$(curl -s -k -L -X GET -u "${api_username}:${api_password}" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/shards)

  responseshards=$(echo "${shardsjson}" | jq -c '.')
  while read -r row; do
    parse_shards_json_objects "${row}"
  done <<< "$(echo "${responseshards}" | jq -c '.[]')"



##Fetch endpoints information and store it to Redis database
##Not used yet but may be usefull to migrate endpoints if required
## Data not used => not ported in rest/jsonn approach
#echo "$endpointsinfo" | awk -F '[/ ]+' '/endpoint/  {print "hset "$3" endpoint-id "$3" db-id "$1" node-id "$4" role "$5" status "$7}' | tr -d \*GB | redis-cli 

##Check if the cluster is rack-aware
isRackAware=true
redis-cli -h $redis_hostname -p $redis_port  SET isRackAware $isRackAware
NodeRack=`redis-cli -h $redis_hostname -p $redis_port  hget node:1 rack-id`
if [ "$NodeRack" = "-" ]; then
    isRackAware=false
    redis-cli -h $redis_hostname -p $redis_port  SET isRackAware $isRackAware
fi

# LUA TO FINALIZE POPULATION
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 1
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 5
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 25
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CORR
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CANCREATE 10 1 true
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CANCREATE 50 1 true
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CANCREATE 100 2 true
redis-cli -h $redis_hostname -p $redis_port --raw EVAL "$(cat lua/capaplan.lua)" 0 CANCREATE 200 4 true