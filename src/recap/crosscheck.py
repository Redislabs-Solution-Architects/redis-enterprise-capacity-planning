"""REQ-10 optional RS dry-runs, treated only as a divergence signal.

Blueprint shape: redis.io/docs/latest/operate/rs/references/rest-api/requests/bdbs/actions/rebalance/
"""
from argparse import Namespace
from datetime import datetime,timezone
import httpx
from recap.collect import credentials,version
from recap.planner.create import plan as create
from recap.planner.upscale import plan as upscale
from recap.planner.optimize import plan as optimize
from recap.units import parse
from recap.verifier import verify


def normalize_blueprint(blueprint):
    return sorted((str(row['slot_range']),int(node['node_uid']),
                   'replica' if node['role']=='slave' else node['role']) for row in blueprint for node in row['nodes'])


def compare(snapshot,args):
    collected=datetime.fromisoformat(snapshot['collected_at'].upper().replace('Z','+00:00'))
    if args.max_age<0 or (datetime.now(timezone.utc)-collected).total_seconds()>args.max_age:
        raise ValueError('stale snapshot: exceeds --max-age')
    check=args.check
    db=None
    if check=='can-create':
        result=create(snapshot,args.memory,args.shards,args.replication,args.rack_aware,args.placement)
        method,path='POST','/v1/bdbs?dry_run'
        payload=dict(memory_size=args.memory,shards_count=args.shards,replication=args.replication,
                     rack_aware=snapshot['cluster']['rack_aware'] if args.rack_aware is None else args.rack_aware,
                     shards_placement=args.placement or snapshot['cluster']['default_shards_placement'])
    else:
        db=next((d for d in snapshot['bdbs'] if str(d['uid'])==str(args.db) or d['name']==args.db),None)
        if db is None:raise ValueError('unknown database')
        if check=='can-upscale':
            if args.memory is None:raise ValueError('--memory is required')
            result=upscale(snapshot,args.db,args.memory,args.shards)
            method,path='PUT',f"/v1/bdbs/{db['uid']}/actions/revamp?dry_run=true"
            payload={'memory_size':parse(args.memory,current=db['memory_size'])}
            if args.shards is not None:payload['shards_count']=args.shards
        else:
            options=Namespace(scope='db',db=str(db['uid']),node=None,rack=None,shard_size_min=None,shard_size_max=None,
                              shard_used_max=False,reserve_shard_size=None,need=None,level=1,explain=False)
            result=optimize(snapshot,options)
            method,path='PUT',f"/v1/bdbs/{db['uid']}/actions/rebalance?dry_run=true"
            payload={}
    own_accept=result['verdict'] in ('feasible','feasible-in-steps','goal-met','ok')
    final=verify(snapshot,result['plan'],result.get('goal') if own_accept else None)
    comparison=dict(recap=result['verdict'],rs='skipped',classification='skipped')
    minimum=(7,22) if check=='can-upscale' else (7,8) if check=='rebalance' else None
    if minimum and version(snapshot['cluster']['rs_version'])<minimum:
        comparison['reason']='requires RS >= '+'.'.join(map(str,minimum))
    else:
        try:
            with httpx.Client(base_url=args.url,auth=credentials(args.url),verify=True,timeout=30) as client:
                response=client.request(method,path,json=payload)
            if response.status_code in (401,403):
                comparison['reason']='permission-denied'
            else:
                accepted=response.is_success
                comparison.update(rs='accepts' if accepted else 'refuses',classification='agree' if accepted==own_accept else 'rs-refuses-recap-accepts' if own_accept else 'rs-accepts-recap-refuses')
                if check=='rebalance' and accepted:
                    blueprint=response.json()
                    own=sorted((s['slots'],s['node_uid'],s['role']) for s in final['shards'] if s['bdb_uid']==db['uid'])
                    if normalize_blueprint(blueprint)!=own:comparison['classification']='placement-differs'
        except httpx.HTTPError:
            comparison['reason']='request-failed'
    result.setdefault('details',{})['comparison']=[comparison]
    return result
