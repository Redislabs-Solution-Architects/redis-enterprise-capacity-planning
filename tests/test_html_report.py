"""Standalone visual report behavior and CLI integration."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path

import pytest

from recap.cli import main
from recap.report import build

FIXTURES=Path(__file__).parent/'fixtures'


def snapshot(name='upscale-steps'):
    return json.loads((FIXTURES/f'{name}.json').read_text())


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags=[];self.text=[];self.attributes=[]

    def handle_starttag(self,tag,attrs):
        self.tags.append(tag);self.attributes.append((tag,dict(attrs)))

    def handle_data(self,data):
        self.text.append(data)


def test_html_visuals_preserve_report_values_and_plan_details():
    from recap.html_report import render
    s=snapshot();data=build(s,'6GiB:1');original=deepcopy(data)
    html=render(s,data)
    parser=ReportParser();parser.feed(html)
    text=' '.join(parser.text)
    assert html.lstrip().lower().startswith('<!doctype html>')
    assert parser.tags.count('svg')>=3
    assert parser.tags.count('table')>=3
    assert 'details' in parser.tags
    for title in ('Free planning RAM','Free shard slots','Capacity by rack','Can-create','Can-upscale','Provenance'):
        assert title in text
    for row in data['can_create']:
        assert row['verdict'] in text
    assert 'feasible-in-steps' in text
    assert 'rladmin migrate shard' in text
    assert '$RECAP_USER:$RECAP_PASSWORD' in text
    assert s['collected_at'] in text
    assert data==original
    assert 'script' not in parser.tags
    assert not any(tag in ('img','link','iframe') for tag in parser.tags)
    assert all(not attrs.get('href','').startswith(('http:','https:')) for _,attrs in parser.attributes)
    assert 'prefers-color-scheme: dark' in html
    assert '@media print' in html


def test_html_escapes_snapshot_text_and_attributes():
    from recap.html_report import render
    s=snapshot()
    payload='<script>alert("x")</script><img src=x onerror="alert(1)">'
    s['cluster']['name']=payload
    s['nodes'][0]['rack_id']=payload
    s['provenance']['warnings']=[payload]
    s['bdbs'][0]['name']=payload
    s['bdbs'][0]['unsupported_reason']=payload
    html=render(s,build(s))
    parser=ReportParser();parser.feed(html)
    assert payload in ''.join(parser.text)
    assert 'script' not in parser.tags and 'img' not in parser.tags
    assert not any(key.lower().startswith('on') for _,attrs in parser.attributes for key in attrs)
    assert '&lt;script&gt;' in html


def test_html_partial_unknown_and_empty_states_are_explicit():
    from recap.html_report import render
    s=snapshot('no-rack')
    s['provenance'].update(partial=True,partial_reasons=['Scoped account: incomplete visibility'])
    s['provenance']['rs_semantics']['provisional_ram']='pre-8.0'
    s['nodes'][0].update(provisional_ram=0,max_redis_servers=s['nodes'][0]['shard_count'],second_rack_id='zone-a')
    s['cluster']['mixed_versions']=True
    html=render(s,build(s))
    assert 'PARTIAL' in html
    assert 'Scoped account: incomplete visibility' in html
    assert 'unknown' in html.lower()
    assert '2d-rack-rule-unverified' in html
    assert 'Mixed versions' in html
    empty=deepcopy(s);empty.update(nodes=[],bdbs=[],shards=[])
    html=render(empty,build(empty))
    assert 'No nodes' in html and 'No database' in html
    assert 'width="nan"' not in html.lower() and 'height="nan"' not in html.lower()


def test_html_cli_writes_and_opens_file(tmp_path,monkeypatch,capsys):
    import webbrowser
    opened=[]
    monkeypatch.setattr(webbrowser,'open',lambda url:opened.append(url) or True)
    target=tmp_path/'capacity report.html'
    assert main(['report','--snapshot',str(FIXTURES/'upscale-steps.json'),'--format','html','--out',str(target),'--open'])==0
    assert target.read_text().startswith('<!doctype html>')
    assert opened==[target.resolve().as_uri()]
    assert not capsys.readouterr().out


def test_html_stdout_and_no_implicit_browser(monkeypatch,capsys):
    import webbrowser
    def unexpected(*args,**kwargs):
        pytest.fail('browser must only open with --open')
    monkeypatch.setattr(webbrowser,'open',unexpected)
    assert main(['report','--snapshot',str(FIXTURES/'no-rack.json'),'--format','html'])==0
    assert capsys.readouterr().out.startswith('<!doctype html>')


@pytest.mark.parametrize('flags',[
    ['--open'], ['--format','html','--open'], ['--format','json','--out','unused.json'],
])
def test_html_invalid_output_flags_are_usage_errors(flags,capsys):
    assert main(['report','--snapshot',str(FIXTURES/'no-rack.json'),*flags])==2
    assert capsys.readouterr().err


def test_html_refuses_overwriting_snapshot(tmp_path,capsys):
    target=tmp_path/'s.json';content=json.dumps(snapshot())
    target.write_text(content)
    assert main(['report','--snapshot',str(target),'--format','html','--out',str(target)])==2
    assert target.read_text()==content


def test_html_refuses_hard_link_to_snapshot(tmp_path,capsys):
    source=tmp_path/'s.json';content=json.dumps(snapshot())
    source.write_text(content)
    target=tmp_path/'report.html'
    target.hardlink_to(source)
    assert main(['report','--snapshot',str(source),'--format','html','--out',str(target)])==2
    assert source.read_text()==content
    assert target.read_text()==content


def test_html_failed_verification_never_writes_or_opens(tmp_path,monkeypatch,capsys):
    import recap.report
    import webbrowser
    from recap.verifier import VerificationError
    def faulty(*args,**kwargs):
        raise VerificationError('internal-error: plan failed verification at step 1')
    monkeypatch.setattr(recap.report,'build',faulty)
    monkeypatch.setattr(webbrowser,'open',lambda *args:pytest.fail('invalid plan must not open'))
    target=tmp_path/'invalid.html'
    assert main(['report','--snapshot',str(FIXTURES/'no-rack.json'),'--format','html','--out',str(target),'--open'])==5
    assert not target.exists()


def test_html_file_failure_is_usage_error(tmp_path,capsys):
    target=tmp_path/'missing'/'report.html'
    assert main(['report','--snapshot',str(FIXTURES/'no-rack.json'),'--format','html','--out',str(target)])==2
    assert not target.exists()


def test_html_browser_failure_keeps_generated_file(tmp_path,monkeypatch,capsys):
    import webbrowser
    monkeypatch.setattr(webbrowser,'open',lambda url:False)
    target=tmp_path/'report.html'
    assert main(['report','--snapshot',str(FIXTURES/'no-rack.json'),'--format','html','--out',str(target),'--open'])==0
    assert target.is_file()
    assert 'browser' in capsys.readouterr().err.lower()
