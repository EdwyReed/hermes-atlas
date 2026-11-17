#!/usr/bin/env python3
"""Explicit per-profile plan/apply/rollback. Default action is read-only inventory.

Receipts and legacy guidance are private, never part of the plugin repository.
The operator selects each home; no credential lookup across homes occurs.
"""
import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

LEGACY_PLUGINS = ('atlas-engine-client', 'atlas-mask', 'atlas-censor', 'anime-mosaic')
ABSORB = ('invokeai', 'invokeai-workflow-operations', 'invokeai-image-generation',
          'atlas-engine-current', 'anime-mosaic-operations', 'atlas-catalog-lookup')
ROOT = Path(__file__).resolve().parent


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_config(home):
    import yaml
    return yaml.safe_load((home / 'config.yaml').read_text()) or {}


def fingerprint(p):
    if p.is_symlink():
        return {'link': os.readlink(p)}
    if p.is_file():
        return {'sha256': digest(p.read_bytes())}
    if p.is_dir():
        # Runtime media plugins can contain model/venv trees. Never inspect/copy those bytes.
        if (p / 'SKILL.md').is_file():
            return {'skill_files': {str(f.relative_to(p)): digest(f.read_bytes())
                                    for f in sorted(p.rglob('*')) if f.is_file()}}
        return {'directory': True, 'identity': [p.stat().st_dev, p.stat().st_ino],
                'entrypoints': {n: digest((p / n).read_bytes()) for n in ('__init__.py', 'plugin.yaml', 'engine-binding.json') if (p / n).is_file()}}
    return None


def skills(home):
    # rglob does not descend directory symlinks on supported Python. Include those explicitly.
    found = []
    base = home / 'skills'
    if not base.is_dir():
        return found
    for directory, dirs, files in os.walk(base, followlinks=False):
        for name in list(dirs):
            p = Path(directory) / name
            if p.is_symlink() and (p / 'SKILL.md').is_file():
                found.append(p)
        if 'SKILL.md' in files:
            found.append(Path(directory))
    return sorted(set(found))


def plan(home):
    home = Path(home).absolute()
    if home.is_symlink() or not (home / 'config.yaml').is_file():
        raise ValueError('Select an existing real profile home with config.yaml.')
    config = read_config(home)
    plugins = config.get('plugins') or {}
    entries = plugins.get('entries') or {}
    previous = entries.get('atlas-engine-client') or {}
    settings = (previous.get('settings') or previous.get('config') or {}).get('atlas_engine') or {}
    enabled = plugins.get('enabled', [])
    disabled = plugins.get('disabled', [])
    old_active = ('atlas-engine-client' in enabled and 'atlas-engine-client' not in disabled
                  and previous.get('enabled', True) is not False)
    # Only carry an existing native-client binding, never infer a credential from adapters/proxies.
    binding = copy.deepcopy(settings) if settings and old_active else {}
    mode = 'existing-native-binding' if binding else 'guidance-only-existing-access-unchanged'
    paths = []
    for name in LEGACY_PLUGINS:
        p = home / 'plugins' / name
        if p.exists() or p.is_symlink():
            paths.append(p)
    retired = [p for p in skills(home) if p.name in ABSORB]
    for p in retired:
        paths.append(p)
    # Exact stale skill references only. Never rewrite commands, recipes or unrelated prose.
    replacements = []
    for p in skills(home):
        if p in retired:
            continue
        f = p / 'SKILL.md'
        raw = f.read_text()
        changed = raw
        for name in ABSORB:
            changed = changed.replace('`' + name + '`', '`atlas:atlas`')
        if changed != raw:
            # A symlinked specialist is shared ownership: leave it intact and report it.
            replacements.append({'path': str(f), 'sha256': digest(f.read_bytes()),
                                 'new_text': changed, 'blocked_shared': p.is_symlink() or f.is_symlink()})
    target = home / 'plugins/atlas'
    guidance = home / 'plugin-data/atlas/references/profile-guidance'
    if target.exists() or target.is_symlink() or guidance.exists():
        raise ValueError('Unified Atlas target/guidance already exists; do not overwrite an installation.')
    return {'version': 1, 'home': str(home), 'package': str(ROOT), 'mode': mode,
            'config_sha256': digest((home / 'config.yaml').read_bytes()),
            'before_plugins': plugins, 'plugins_was_absent': 'plugins' not in config,
            'binding': binding, 'paths': [{'path': str(p), 'fingerprint': fingerprint(p)} for p in paths],
            'retired_skills': [str(p) for p in retired], 'references': replacements,
            'adapters': [{'name': n, 'binding_present': (home / 'plugins' / n / 'engine-binding.json').is_file()} for n in LEGACY_PLUGINS[1:]],
            'mcp_servers_untouched': sorted((config.get('mcp_servers') or {}).keys()),
            'state': 'planned'}


def private_json(path, value):
    path = Path(path)
    raw = (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()
    tmp = path.with_name('.' + path.name + '.part')
    with tmp.open('xb') as f:
        os.chmod(tmp, 0o600)
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def configure(home, plugins):
    # Use the supported Hermes configuration command, not YAML editing.
    env = dict(os.environ, HERMES_HOME=str(home))
    result = subprocess.run(['hermes', 'config', 'set', '--force', 'plugins', json.dumps(plugins)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Hermes config set failed; private preimage retained (output suppressed).')
    if read_config(home).get('plugins') != plugins:
        raise RuntimeError('Exact plugin configuration readback failed.')


def verify_plan(p):
    home = Path(p['home'])
    if digest((home / 'config.yaml').read_bytes()) != p['config_sha256']:
        raise ValueError('Profile config changed since plan; make a fresh plan.')
    for row in p['paths']:
        if fingerprint(Path(row['path'])) != row['fingerprint']:
            raise ValueError('Legacy entry changed since plan.')
    for row in p['references']:
        if digest(Path(row['path']).read_bytes()) != row['sha256']:
            raise ValueError('Skill reference changed since plan.')


def apply(receipt):
    receipt = Path(receipt).absolute()
    p = json.loads(receipt.read_text())
    if p['state'] != 'planned' or p['package'] != str(ROOT):
        raise ValueError('Receipt must be a fresh plan for this shared package.')
    verify_plan(p)
    home = Path(p['home'])
    target = home / 'plugins/atlas'
    guidance = home / 'plugin-data/atlas/references/profile-guidance'
    if target.exists() or target.is_symlink() or guidance.exists():
        raise ValueError('Atlas target already exists.')
    backup = receipt.parent / (receipt.stem + '-backup')
    backup.mkdir(mode=0o700)
    p.update(state='applying', backup=str(backup), moved=[], edited=[], target=str(target), guidance=str(guidance))
    private_json(receipt, p)
    # Persist each step before the next. Rollback also accepts interrupted partial apply.
    try:
        guidance.mkdir(parents=True, mode=0o700)
        index = ['# Profile-specific preserved Atlas guidance', '',
                 'Private source material; original authors/profile context retained. Never publish this directory.',
                 'Atlas bundled skill and live schema override retired execution routes below.', '']
        for i, path in enumerate(p['retired_skills']):
            source = Path(path)
            dest = guidance / str(i)
            shutil.copytree(source, dest, symlinks=True)
            # No second discoverable SKILL.md; retain original instructions as a reference.
            (dest / 'SKILL.md').rename(dest / 'source.md')
            index += [f'- {i}/source.md — original profile source: {path}']
        (guidance / 'INDEX.md').write_text('\n'.join(index) + '\n')
        for i, row in enumerate(p['paths']):
            source = Path(row['path'])
            dest = backup / ('entry-' + str(i))
            p['moved'].append({'source': str(source), 'backup': str(dest)})
            private_json(receipt, p)
            source.rename(dest)  # Rename the link itself; never delete its shared target.
        for i, row in enumerate(p['references']):
            if row['blocked_shared']:
                continue
            source = Path(row['path'])
            dest = backup / ('reference-' + str(i))
            shutil.copy2(source, dest)
            p['edited'].append({'source': str(source), 'backup': str(dest), 'new_sha256': digest(row['new_text'].encode())})
            private_json(receipt, p)
            source.write_text(row['new_text'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(ROOT, target_is_directory=True)
        updated = copy.deepcopy(p['before_plugins'])
        entries = updated.setdefault('entries', {})
        for n in LEGACY_PLUGINS:
            if n in entries:
                entries[n]['enabled'] = False  # Settings retained for rollback.
        entries['atlas'] = {'enabled': True, 'settings': {'atlas_engine': p['binding']}}
        updated['enabled'] = [n for n in updated.get('enabled', []) if n not in LEGACY_PLUGINS] + ['atlas']
        updated['disabled'] = list(dict.fromkeys([n for n in updated.get('disabled', []) if n != 'atlas'] + list(LEGACY_PLUGINS)))
        p['after_plugins'] = updated
        private_json(receipt, p)
        configure(home, updated)
        p['state'] = 'applied'
        private_json(receipt, p)
        assert target.is_symlink() and target.resolve() == ROOT
        assert all(not Path(r['source']).exists() and not Path(r['source']).is_symlink() for r in p['moved'])
        return p
    except BaseException:
        # No blind auto-rollback that could mask a partial state; exact journal is usable by rollback.
        raise


def rollback(receipt):
    receipt = Path(receipt).absolute()
    p = json.loads(receipt.read_text())
    if p['state'] not in ('applying', 'applied', 'rolling-back'):
        raise ValueError('Receipt is not an applied/partial rollout.')
    home = Path(p['home'])
    current = read_config(home).get('plugins', {})
    if current not in (p['before_plugins'], p.get('after_plugins', p['before_plugins'])):
        raise ValueError('Plugin configuration changed externally; refusing to clobber it.')
    target = Path(p['target'])
    if target.is_symlink() and target.resolve() != ROOT:
        raise ValueError('Atlas link changed externally; refusing rollback.')
    if target.exists() and not target.is_symlink():
        raise ValueError('Atlas target is no longer our link.')
    for row in p['edited']:
        f = Path(row['source'])
        if f.exists() and digest(f.read_bytes()) not in (row['new_sha256'], digest(Path(row['backup']).read_bytes())):
            raise ValueError('Edited reference changed externally; refusing rollback.')
    for row in p['moved']:
        source, backup = Path(row['source']), Path(row['backup'])
        if (backup.exists() or backup.is_symlink()) and (source.exists() or source.is_symlink()):
            raise ValueError('Retired path was recreated; refusing rollback.')
    p['state'] = 'rolling-back'
    private_json(receipt, p)
    configure(home, p['before_plugins'])
    if target.is_symlink():
        target.unlink()
    for row in reversed(p['edited']):
        shutil.copy2(row['backup'], row['source'])
    for row in reversed(p['moved']):
        source, backup = Path(row['source']), Path(row['backup'])
        if backup.exists() or backup.is_symlink():
            backup.rename(source)
    # Guidance remains private evidence but is moved out of the profile’s active plugin data.
    guidance = Path(p['guidance'])
    if guidance.exists():
        guidance.rename(Path(p['backup']) / 'preserved-guidance')
    p['state'] = 'rolled-back'
    private_json(receipt, p)
    return p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    scan = sub.add_parser('plan')
    scan.add_argument('--home', required=True)
    scan.add_argument('--receipt', required=True)
    for action in ('apply', 'rollback'):
        s = sub.add_parser(action)
        s.add_argument('--receipt', required=True)
    args = parser.parse_args()
    if args.action == 'plan':
        receipt = Path(args.receipt).absolute()
        if receipt.exists():
            raise ValueError('Refusing to overwrite an existing receipt.')
        if receipt.is_relative_to(ROOT):
            raise ValueError('Private receipt must be outside the source repository.')
        receipt.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        p = plan(args.home)
        private_json(receipt, p)
    else:
        p = (apply if args.action == 'apply' else rollback)(args.receipt)
    print(json.dumps({'state': p['state'], 'home': p['home'], 'mode': p['mode'],
                      'retired_entries': len(p['paths']), 'reference_updates': len(p['references']),
                      'shared_references_left_unchanged': sum(r['blocked_shared'] for r in p['references'])}))


if __name__ == '__main__':
    main()
