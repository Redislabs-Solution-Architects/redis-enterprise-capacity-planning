#!/bin/bash

##Path config
#export PATH="/opt/redislabs/bin:$PATH"

#To make sure we deal with float with dots
export LC_NUMERIC="en_US.UTF-8"

#To make Inputs with

if [[ "$1" == "" ]]
  then
    echo "No arguments supplied"
    redis_cluster_api_url="cluster.dev-pierre-lab.demo.redislabs.com"
else redis_cluster_api_url=$1
fi

##Utility redis database
EXIST=`redis-cli EXISTS PLOptimizerVersion`
if [ "$EXIST" == "1" ]; then
redis-cli flushdb async
fi
redis-cli SET PLOptimizerVersion 0.0000001alpha

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
  redis-cli hset $dbid db-id $dbid db-name $db_name number-shards $shards_count shard_placement $shards_placement replication $replication memory_limit $memory_size_gb
  redis-cli zadd db $memory_size_gb $dbid
  local bdbsstatsjson=$(curl -s -k -L -X GET -u "admin@admin.com:admin" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/bdbs/stats/last/$uid)
  local responsetoget=$(echo "${bdbsstatsjson}" | jq -c '.')
    while read -r rows; do
      local memory_used=$(jq -r '.used_memory' <<< "${rows}")
      local memory_used_gb=$(awk "BEGIN {printf \"%.2f\", $memory_used/1024/1024/1024}")
      redis-cli hset $dbid memory_used $memory_used_gb
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
  redis-cli hset $node_id node-id $node_id rack-id $rack_id number-shards $shards_count total_available_memory $total_available_memory
  redis-cli sadd racks $rack_id
  local nodestatsjson=$(curl -s -k -L -X GET -u "admin@admin.com:admin" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/nodes/stats/last/$uid)
  local responsetoget=$(echo "${nodestatsjson}" | jq -c '.')
    while read -r rows; do
      local available_memory=$(jq -r '.provisional_memory' <<< "${rows}")
      local available_memory_gb=$(awk "BEGIN {printf \"%.2f\", $available_memory/1024/1024/1024}")
      redis-cli hset $node_id available_memory $available_memory_gb
      redis-cli zadd nodes $available_memory_gb $node_id
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
  redis-cli hset $shard_id shard-id $shard_id node-id $node_id db-id $db_id role $role slots $slots status $status
  redis-cli sadd shards $shard_id
  redis-cli sadd $zdbsh $shard_id
  local shardstatsjson=$(curl -s -k -L -X GET -u "admin@admin.com:admin" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/shards/stats/last/$uid)
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
      redis-cli hset $shard_id used_memory $used_final
    done <<< "$(echo "${responsetoget}" | jq -c '.[]')"

}
#BDBS
bdbsjson=$(curl -s -k -L -X GET -u "admin@admin.com:admin" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/bdbs)


  responsebdbs=$(echo "${bdbsjson}" | jq -c '.')
  while read -r row; do
    parse_bdbs_json_objects "${row}"
  done <<< "$(echo "${responsebdbs}" | jq -c '.[]')"

#NODES

nodesjson=$(curl -s -k -L -X GET -u "admin@admin.com:admin" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/nodes)

  responsenodes=$(echo "${nodesjson}" | jq -c '.')
  while read -r row; do
    parse_nodes_json_objects "${row}"
  done <<< "$(echo "${responsenodes}" | jq -c '.[]')"

#SHARDS
shardsjson=$(curl -s -k -L -X GET -u "admin@admin.com:admin" -H "Content-type:application/json" https://${redis_cluster_api_url}:9443/v1/shards)

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
redis-cli  SET isRackAware $isRackAware
NodeRack=`redis-cli  hget node:1 rack-id`
if [ "$NodeRack" = "-" ]; then
    isRackAware=false
    redis-cli  SET isRackAware $isRackAware
fi

# LUA TO FINALIZE POPULATION
redis-cli --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 1
redis-cli --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 5
redis-cli --raw EVAL "$(cat lua/capaplan.lua)" 0 CAPA 25
redis-cli --raw EVAL "$(cat lua/capaplan.lua)" 0 CORR