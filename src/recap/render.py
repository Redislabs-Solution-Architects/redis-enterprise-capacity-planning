"""Render exported plans; never execute them."""


def render(steps):
    commands=[]
    for step in steps:
        if step['action']=='migrate':
            commands.append(f"rladmin migrate shard {step['shard_uid']} preserve_roles target_node {step['to_node']}")
        elif step['action']=='failover':
            commands.append(f"rladmin failover shard {step['shard_uid']}")
    return commands
