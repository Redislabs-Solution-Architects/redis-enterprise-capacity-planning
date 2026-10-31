"""REQ-08 POC heuristics with live state updates and level-2 failovers."""
from copy import deepcopy
from recap.constraints import violations
from recap.model import node_capacity, shard_size

GIB=2**30


def plan(snapshot,args,*,reserved_ram=None,stop_when=None):
    """Plan moves, optionally preserving per-node growth RAM for an upscale.

    Standalone optimize uses the spec's default filters and score unchanged.
    The upscale caller supplies its final-placement predicate to stop early.
    """
    state=deepcopy(snapshot)
    reserved_ram=reserved_ram or {}
    dbs={d['uid']:d for d in state['bdbs']}
    sizes={uid:shard_size(db) for uid,db in dbs.items()}
    largest=max(sizes.values(),default=0)
    reserve=args.reserve_shard_size if args.reserve_shard_size is not None else largest
    if reserve<=0:
        return dict(verdict='no-plan',reasons=['no positive reserve shard size'],plan=[])
    scope=args.scope
    own_uid=None
    if scope=='db':
        own=next((d for d in dbs.values() if str(d['uid'])==str(args.db) or d['name']==args.db),None)
        if own is None: raise ValueError('unknown database')
        own_uid=own['uid']
        scope_nodes={s['node_uid'] for s in state['shards'] if s['bdb_uid']==own_uid}
    elif scope=='node':
        scope_nodes={int(args.node)}
        if not any(n['uid'] in scope_nodes for n in state['nodes']): raise ValueError('unknown node')
    elif scope=='rack':
        scope_nodes={n['uid'] for n in state['nodes'] if n['rack_id']==args.rack}
        if not scope_nodes: raise ValueError('unknown rack')
    else:
        scope_nodes={n['uid'] for n in state['nodes']}
    densify_target=None
    if scope=='cluster':
        targets=[n for n in state['nodes'] if n['shard_count'] and node_capacity(state,n,reserve)['capacity']==0
                 and n['accept_servers'] and n['status']=='active' and (args.rack is None or n['rack_id']==args.rack)]
        if not targets: return dict(verdict='no-plan',reasons=['no densify target'],plan=[])
        densify_target=min(targets,key=lambda n:(n['shard_count']+(n['provisional_ram']%reserve)/GIB,n['uid']))['uid']
    minimum=args.shard_size_min if args.shard_size_min is not None else GIB if scope=='db' else 0
    maximum=args.shard_size_max if args.shard_size_max is not None else 5*GIB if scope=='db' else largest
    used=args.shard_used_max
    if used is False or used=='policy': used=5*GIB if scope=='db' else None
    if minimum>maximum: raise ValueError('minimum shard size exceeds maximum')
    candidates=[s for s in state['shards'] if s['node_uid'] in scope_nodes and s['node_uid']!=densify_target
                and s['bdb_uid'] in dbs and s['bdb_uid']!=own_uid and not dbs[s['bdb_uid']]['unsupported_reason']
                and minimum<=sizes[s['bdb_uid']]<=maximum and (used is None or s['used_memory']<=used)]
    def order(shard):
        score=sizes[shard['bdb_uid']]+shard['used_memory']
        return (-score if scope=='cluster' else score,shard['uid'])
    replicas=sorted([s for s in candidates if s['role']=='replica'],key=order)
    masters=sorted([s for s in candidates if s['role']=='master'],key=order) if args.level==2 else []
    ids=[s['uid'] for s in replicas+masters]
    steps=[];rejected=[]
    initial=sum(n['provisional_ram'] for n in snapshot['nodes'] if n['uid'] in scope_nodes)

    def freed(current):
        return sum(n['provisional_ram'] for n in current['nodes'] if n['uid'] in scope_nodes)-initial

    for shard_uid in ids:
        if stop_when is not None and stop_when(state): break
        if args.need is not None and freed(state)>=args.need: break
        shard=next(s for s in state['shards'] if s['uid']==shard_uid)
        trial_base=deepcopy(state)
        failover=shard['role']=='master'
        if failover:
            trial_shard=next(s for s in trial_base['shards'] if s['uid']==shard_uid)
            partner=next((s for s in trial_base['shards'] if s['bdb_uid']==shard['bdb_uid'] and s['slots']==shard['slots'] and s['role']=='replica'),None)
            if partner is None: continue
            trial_shard['role'],partner['role']='replica','master'
            errors=violations(trial_base)
            if errors:
                rejected.append(dict(shard_uid=shard_uid,action='failover',reasons=list(map(str,errors))))
                continue
        size=sizes[shard['bdb_uid']]
        targets=[]
        for n in trial_base['nodes']:
            if n['uid']==shard['node_uid'] or (scope=='rack' and n['uid'] in scope_nodes): continue
            if densify_target is not None and n['uid']!=densify_target: continue
            if node_capacity(trial_base,n,size)['capacity']<1: continue
            if n['provisional_ram']-size<reserved_ram.get(n['uid'],0): continue
            if scope=='db' and n['uid'] in scope_nodes and n['provisional_ram']-size<reserve: continue
            trial=deepcopy(trial_base)
            source=next(x for x in trial['nodes'] if x['uid']==shard['node_uid'])
            target=next(x for x in trial['nodes'] if x['uid']==n['uid'])
            moved=next(x for x in trial['shards'] if x['uid']==shard_uid)
            source['provisional_ram']+=size;source['shard_count']-=1
            target['provisional_ram']-=size;target['shard_count']+=1
            moved['node_uid']=n['uid']
            errors=violations(trial)
            if errors:
                rejected.append(dict(shard_uid=shard_uid,to_node=n['uid'],reasons=list(map(str,errors))))
                continue
            score=node_capacity(trial_base,n,size)['capacity']+(n['provisional_ram']%reserve)/GIB
            targets.append((score,n['uid'],trial))
        if not targets: continue
        _,target_uid,state=max(targets,key=lambda x:(x[0],x[1]))
        if failover:
            steps.append(dict(step=len(steps)+1,action='failover',shard_uid=shard_uid,
                              from_node=shard['node_uid'],to_node=partner['node_uid'],freed_bytes=0,
                              state_after_summary=[dict(uid=n['uid'],free_ram=n['provisional_ram'],free_slots=n['max_redis_servers']-n['shard_count']) for n in trial_base['nodes']]))
        steps.append(dict(step=len(steps)+1,action='migrate',shard_uid=shard_uid,from_node=shard['node_uid'],to_node=target_uid,
                          freed_bytes=size*(int(shard['node_uid'] in scope_nodes)-int(target_uid in scope_nodes)),
                          state_after_summary=[dict(uid=n['uid'],free_ram=n['provisional_ram'],free_slots=n['max_redis_servers']-n['shard_count']) for n in state['nodes']]))
    met=freed(state)>=args.need if args.need is not None else bool(steps)
    verdict='goal-met' if met else 'goal-not-met' if args.need is not None else 'no-plan'
    from recap.render import render
    details={'freed_bytes':freed(state),'rendered':render(steps)}
    if args.explain: details['rejected_candidates']=rejected
    goal=dict(kind='freed',nodes=sorted(scope_nodes),bytes=args.need) if args.need is not None else dict(kind='beneficial')
    return dict(verdict=verdict,reasons=[] if met else ['no moves satisfy the goal'],plan=steps,goal=goal,details=details)
