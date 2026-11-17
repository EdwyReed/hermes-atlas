#!/usr/bin/env python3
"""Fresh-process real Hermes discovery/skill-reference probe, no model chat."""
import argparse
import json
import socket
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True)
    parser.add_argument('--tools-available', choices=['yes', 'no'], required=True)
    parser.add_argument('--invoke', action='store_true')
    args = parser.parse_args()
    from hermes_cli.plugins import get_plugin_manager
    from tools.registry import registry
    manager = get_plugin_manager()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Registration must not open sockets')):
        manager.discover_and_load()
    assert manager.list_plugin_skills('atlas') == ['atlas']
    skill_path = manager.find_plugin_skill('atlas:atlas')
    assert skill_path.resolve() == (Path(args.package) / 'skills/atlas/SKILL.md').resolve()
    from tools.skills_tool import skill_view, skills_list
    listing = json.loads(skills_list())
    assert listing['success'], listing
    hits = [s for s in listing['skills'] if s['name'] == 'atlas:atlas']
    assert len(hits) == 1, hits
    view = json.loads(skill_view('atlas:atlas'))
    assert view['success'], view
    refs = sorted((skill_path.parent / 'references').glob('*.md'))
    assert len(refs) >= 5
    for reference in refs:
        viewed = json.loads(skill_view('atlas:atlas', file_path='references/' + reference.name))
        assert viewed['success'], viewed
        assert reference.read_text().strip() in viewed['content'], reference.name
    names = ['atlas_engine', 'atlas_files', 'atlas_mask', 'atlas_censor', 'anime_mosaic']
    for name in names:
        entry = registry.get_entry(name, scope=manager.scope_key)
        assert entry is not None, name
        assert bool(entry.check_fn()) == (args.tools_available == 'yes'), name
    if args.invoke:
        engine = registry.get_entry('atlas_engine', scope=manager.scope_key)
        response = json.loads(engine.handler({'operation': 'capabilities', 'arguments': {'literal_probe': 'unchanged'}}))
        assert response['ok'], response
        assert response['result']['echo'] == {'literal_probe': 'unchanged'}
        files = registry.get_entry('atlas_files', scope=manager.scope_key)
        schema = json.loads(files.handler({'action': 'schema', 'operation': 'mask.segment'}))
        assert schema['ok'], schema
    print(json.dumps({'native_discovery': True, 'tools': names, 'tools_available': args.tools_available,
                      'skill': 'atlas:atlas', 'refs_opened': [p.name for p in refs], 'handler_invoked': args.invoke}))


if __name__ == '__main__':
    main()
