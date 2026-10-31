"""Render exported plans; never execute them."""


def render(steps,url=None):
    commands=[]
    for step in steps:
        if step['action']=='migrate':
            commands.append(f"rladmin migrate shard {step['shard_uid']} preserve_roles target_node {step['to_node']}")
        elif step['action']=='failover':
            commands.append(f"rladmin failover shard {step['shard_uid']}")
        elif step['action']=='rs-update':
            import json
            import shlex
            endpoint=(url or '{url}').rstrip('/')+f"/v1/bdbs/{step['bdb_uid']}"
            commands.append('curl --user "$RECAP_USER:$RECAP_PASSWORD" -X PUT '+shlex.quote(endpoint)+
                            " -H 'Content-Type: application/json' --data "+shlex.quote(json.dumps(step['changes'])))
            if step.get('conditional'):
                commands.append('# conditional: rs-placement; re-collect and re-run before step 2')
    return commands
