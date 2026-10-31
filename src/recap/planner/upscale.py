"""REQ-07 fixed existing placements, optional migrations and conditional RS calls."""
from argparse import Namespace
from collections import Counter
from copy import deepcopy
from urllib.parse import urlsplit
from recap.constraints import violations
from recap.model import shard_size, free_ram
from recap.planner.create import plan as create_plan
from recap.planner.optimize import plan as optimize_plan
from recap.render import render
from recap.units import parse

DEFAULT_LADDER='10GiB:1,50GiB:1,100GiB:2,200GiB:4'


class UnsupportedError(ValueError):
    pass


def target_state(snapshot,db,target):
    state=deepcopy(snapshot)
    current=next(d for d in state['bdbs'] if d['uid']==db['uid'])
    copies=[s for s in state['shards'] if s['bdb_uid']==db['uid']]
    nodes={n['uid']:n for n in state['nodes']}
    license=state['cluster']['license']

    def allocate(s,size,sign):
        n=nodes[s['node_uid']]
        n['provisional_ram']-=sign*size;n['shard_count']+=sign
        if license:license['ram_shards_in_use']+=sign

    for s in copies:allocate(s,shard_size(db),-1)
    current.update(target)
    slots=sorted({s['slots'] for s in copies},key=lambda slot:int(slot.split('-')[0]))
    for s in copies:
        index=slots.index(s['slots'])
        s['slots']=f"{index*16384//target['shards_count']}-{(index+1)*16384//target['shards_count']-1}"
        allocate(s,shard_size(target),1)
    errors=violations(state)
    if errors:return None,list(map(str,errors))
    extra=target['shards_count']-db['shards_count']
    if extra:
        result=create_plan(state,shard_size(target)*extra*(2 if db['replication'] else 1),extra,db['replication'],db['rack_aware'],db['shards_placement'])
        if result['verdict']!='feasible':return None,result['reasons']
        extra_slots=sorted({step['shard']['slots'] for step in result['plan']},key=lambda slot:int(slot.split('-')[0]))
        for step in result['plan']:
            shard=deepcopy(step['shard']);index=db['shards_count']+extra_slots.index(shard['slots'])
            shard['bdb_uid']=db['uid']
            shard['slots']=f"{index*16384//target['shards_count']}-{(index+1)*16384//target['shards_count']-1}"
            state['shards'].append(shard);allocate(shard,shard_size(target),1)
    errors=violations(state)
    return (None,list(map(str,errors))) if errors else (state,[])


def plan(snapshot,db_uid,memory,shards=None,url=None):
    db=next((d for d in snapshot['bdbs'] if str(d['uid'])==str(db_uid) or d['name']==db_uid),None)
    if db is None:raise ValueError('unknown database')
    if db['unsupported_reason']:raise UnsupportedError('unsupported: '+db['unsupported_reason'])
    copies=[s for s in snapshot['shards'] if s['bdb_uid']==db['uid']]
    if snapshot['provenance']['partial']:
        ranges={s['slots'] for s in copies}
        roles={slot:Counter(s['role'] for s in copies if s['slots']==slot) for slot in ranges}
        expected={'master':1,'replica':1} if db['replication'] else {'master':1}
        complete=len(ranges)==db['shards_count'] and all(counts==expected for counts in roles.values())
        if not complete:
            return dict(verdict='infeasible',reasons=['partial: target database shard placement incomplete'],plan=[])
    target=deepcopy(db)
    target['memory_size']=parse(memory,current=db['memory_size']) if isinstance(memory,str) else memory
    target['shards_count']=shards if shards is not None else db['shards_count']
    if target['memory_size']<db['memory_size'] or target['shards_count']<db['shards_count']:
        raise ValueError('upscale cannot reduce memory or shards')
    shard_size(target)
    if url and (urlsplit(url).username or urlsplit(url).password):raise ValueError('URL must not contain credentials')
    for s in snapshot['shards']:
        if s['bdb_uid']==db['uid']:
            n=next(n for n in snapshot['nodes'] if n['uid']==s['node_uid'])
            if free_ram(snapshot,n)=='unknown':
                return dict(verdict='infeasible',reasons=['ram-unknown-pre-8.0'],plan=[])
    final,reasons=target_state(snapshot,db,target)
    moves=[]
    if final is None:
        growth={}
        for shard in copies:
            uid=shard['node_uid']
            growth[uid]=growth.get(uid,0)+max(0,shard_size(target)-shard_size(db))
        options=Namespace(scope='db',db=str(db['uid']),node=None,rack=None,shard_size_min=None,shard_size_max=None,
                          shard_used_max=False,reserve_shard_size=None,need=None,level=2,explain=False)
        optimized=optimize_plan(snapshot,options,reserved_ram=growth,
                                stop_when=lambda state: target_state(state,db,target)[0] is not None)
        if optimized['plan']:
            # Apply only the independently planned migrations; existing target DB shards stay in place.
            moved=deepcopy(snapshot)
            for step in optimized['plan']:
                s=next(s for s in moved['shards'] if s['uid']==step['shard_uid'])
                if step['action']=='failover':
                    partner=next(p for p in moved['shards'] if p['bdb_uid']==s['bdb_uid'] and p['slots']==s['slots'] and p['role']=='replica')
                    s['role'],partner['role']='replica','master'
                else:
                    size=shard_size(next(d for d in moved['bdbs'] if d['uid']==s['bdb_uid']))
                    source=next(n for n in moved['nodes'] if n['uid']==s['node_uid'])
                    dest=next(n for n in moved['nodes'] if n['uid']==step['to_node'])
                    source['provisional_ram']+=size;source['shard_count']-=1
                    dest['provisional_ram']-=size;dest['shard_count']+=1;s['node_uid']=dest['uid']
            final,new_reasons=target_state(moved,db,target)
            if final is not None:moves=optimized['plan']
    if final is None:return dict(verdict='infeasible',reasons=reasons,plan=[])
    steps=deepcopy(moves)
    if target['shards_count']!=db['shards_count']:
        changes={'shards_count':target['shards_count']}
        if not db['sharding']:
            changes.update(sharding=True,shard_key_regex=['.*\\{(?<tag>.*)\\}.*','(?<tag>.*)'])
            target.update(sharding=True,shard_key_regex=changes['shard_key_regex'])
        steps.append(dict(action='rs-update',bdb_uid=db['uid'],changes=changes,conditional='rs-placement',
                          assumed_placement=[s for s in final['shards'] if s['bdb_uid']==db['uid']],
                          instruction='Re-collect and re-run before setting memory_size.'))
    steps.append(dict(action='rs-update',bdb_uid=db['uid'],changes={'memory_size':target['memory_size']}))
    for index,step in enumerate(steps,1):step['step']=index
    return dict(verdict='feasible-in-steps' if moves else 'feasible',reasons=[],plan=steps,
                goal=dict(kind='upscale',database=target),details={'rendered':render(steps,url=url)})


def all_databases(snapshot,ladder=None):
    rungs=[]
    for rung in (ladder or DEFAULT_LADDER).split(','):
        size,count=rung.rsplit(':',1)
        if int(count)<1:raise ValueError('ladder shards must be positive')
        rungs.append((parse(size),int(count)))
    rows=[];results=[]
    for db in snapshot['bdbs']:
        if not db['replication'] or db['unsupported_reason']:continue
        rung=next((r for r in rungs if r[0]>db['memory_size']),None)
        if rung is None:continue
        size,count=rung;count=max(count,db['shards_count'])
        result=plan(snapshot,str(db['uid']),size,count)
        results.append(result)
        rows.append(dict(db_uid=db['uid'],target_memory=size,target_shards=count,verdict=result['verdict'],reasons=result['reasons'],plan=result['plan']))
    return dict(rows=rows,results=results)
