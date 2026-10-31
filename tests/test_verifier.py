"""REQ-09 independent replay in the output path."""
import json
from pathlib import Path
import pytest


def test_req09_faulty_planner_rejected(monkeypatch,capsys):
    """Given: a planner patched in a test to emit a move that over-fills its target
    When: `recap optimize cluster` runs with that planner
    Then: exit 5, with `plan failed verification at step 1`.
    """
    import recap.cli as cli
    monkeypatch.setattr(cli,'optimize_plan',lambda s,a: dict(verdict='goal-met',reasons=[],plan=[dict(action='migrate',shard_uid=2,from_node=1,to_node=3)],goal={'kind':'beneficial'}),raising=False)
    path=Path(__file__).parent/'fixtures/no-rack.json'
    # Target has exactly 1 GiB initially; make it smaller than the 1 GiB shard.
    s=json.loads(path.read_text())
    s['nodes'][2]['provisional_ram']=0
    monkeypatch.setattr('sys.stdin',__import__('io').StringIO(json.dumps(s)))
    assert cli.main(['optimize','cluster','--snapshot','-'])==5
    captured=capsys.readouterr()
    assert 'plan failed verification at step 1' in captured.err
    assert captured.out==''


def test_req09_replay_and_goal_are_independent():
    from recap.verifier import verify, VerificationError
    s=json.loads((Path(__file__).parent/'fixtures/no-rack.json').read_text())
    steps=[dict(action='migrate',shard_uid=2,from_node=1,to_node=2)]
    final=verify(s,steps,{'kind':'freed','nodes':[1],'bytes':2**30})
    assert s['shards'][1]['node_uid']==1
    assert final['shards'][1]['node_uid']==2
    with pytest.raises(VerificationError,match='goal'):
        verify(s,steps,{'kind':'freed','nodes':[1],'bytes':2*2**30})
