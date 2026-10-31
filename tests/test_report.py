"""REQ-11 shareable summary acceptance and golden output."""
from pathlib import Path
import json
from recap.cli import main

ROOT=Path(__file__).resolve().parents[1]


def test_req11_markdown_report(capsys):
    """Given: the fixture
    When: `recap report --snapshot tests/fixtures/poc-5-nodes.json --format markdown`
    Then: exit 0; the output contains one row per node, one row per rack, and one can-create row per ladder rung.
    """
    assert main(['report','--snapshot',str(ROOT/'tests/fixtures/poc-5-nodes.json'),'--format','markdown'])==0
    text=capsys.readouterr().out
    for uid in range(1,6):assert text.count(f'| node:{uid} |')==1
    for rack in ('europe-west1-b','europe-west1-c','europe-west1-d'):
        assert text.count(f'| rack:{rack} |')==1
    assert text.count('| create:')==4
    assert text==(ROOT/'tests/golden/report-poc.md').read_text()


def test_req11_json_envelope_and_warnings(capsys,tmp_path):
    from jsonschema import Draft202012Validator
    s=json.loads((ROOT/'tests/fixtures/no-rack.json').read_text())
    s['nodes'][0]['second_rack_id']='zone-a'
    s['bdbs'][0]['unsupported_reason']='flex'
    path=tmp_path/'s.json';path.write_text(json.dumps(s))
    assert main(['report','--snapshot',str(path),'--format','json'])==0
    output=json.loads(capsys.readouterr().out)
    schema=json.loads((ROOT/'src/recap/schemas/output.v1.json').read_text())
    Draft202012Validator(schema).validate(output)
    assert len(output['unsupported'])==1
    assert '2d-rack-rule-unverified' in output['warnings']
    assert not output['can_upscale']
