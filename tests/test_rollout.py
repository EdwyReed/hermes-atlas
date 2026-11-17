"""Real native config/discovery against temporary homes; never live profiles."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('atlas_rollout', ROOT / 'rollout.py')
rollout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rollout)


def run_probe(home, available, invoke=False):
    command = [sys.executable, str(ROOT / 'tests/native_probe.py'), '--package', str(ROOT), '--tools-available', 'yes' if available else 'no']
    if invoke:
        command.append('--invoke')
    env = dict(os.environ, HERMES_HOME=str(home))
    env.pop('HERMES_SAFE_MODE', None)
    env.pop('HERMES_PROFILE', None)
    result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise AssertionError(result.stdout + '\n' + result.stderr)
    return result.stdout


class RolloutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'profile'
        self.home.mkdir()
        self.shared = self.root / 'shared-legacy'
        self.shared.mkdir()
        (self.shared / 'plugin.yaml').write_text('name: atlas-engine-client\nversion: 1.0.0\n')
        (self.shared / '__init__.py').write_text('def register(ctx): pass\n')
        (self.home / 'plugins').mkdir()
        (self.home / 'plugins/atlas-engine-client').symlink_to(self.shared, target_is_directory=True)
        skill = self.home / 'skills/creative/invokeai'
        (skill / 'references').mkdir(parents=True)
        (skill / 'SKILL.md').write_text('---\nname: invokeai\ndescription: Old profile recipe\n---\nPrivate recipe with exact weights .65\n')
        (skill / 'references/recipe.md').write_text('Preserve this exact local composition requirement.\n')
        art = self.home / 'skills/danbooru'
        art.mkdir()
        (art / 'SKILL.md').write_text('---\nname: danbooru\ndescription: Artistic tags\n---\nKeep artistic guidance.\n')
        consumer = self.home / 'skills/image-editor'
        consumer.mkdir()
        (consumer / 'SKILL.md').write_text('---\nname: image-editor\ndescription: Edit images\n---\nLoad `atlas-engine-current`. Keep .35 denoise.\n')
        self.credential = self.home / 'existing.token'
        self.credential.write_text('only-this-profile')
        self.config = {'model': {'model': 'do-not-change'}, 'memory': {'provider': 'unchanged'},
                       'mcp_servers': {'invokeai_shared': {'command': 'existing-readonly-proxy', 'args': []}},
                       'plugins': {'enabled': ['atlas-engine-client'], 'disabled': ['invokeai-native'],
                                   'entries': {'atlas-engine-client': {'settings': {'atlas_engine': {'endpoint': 'http://127.0.0.1:12288', 'token_file': str(self.credential), 'allowed_operations': ['capabilities']}}},
                                               'unrelated': {'enabled': False, 'settings': {'keep': True}}}}}
        self.write_config()
        self.receipt = self.root / 'private/rollout.json'
        self.receipt.parent.mkdir(mode=0o700)

    def write_config(self):
        (self.home / 'config.yaml').write_text(yaml.safe_dump(self.config))

    def plan(self):
        p = rollout.plan(self.home)
        rollout.private_json(self.receipt, p)
        return p

    def test_apply_native_discovery_guidance_credential_isolation_and_rollback(self):
        original = rollout.read_config(self.home)
        original_skill = (self.home / 'skills/creative/invokeai/SKILL.md').read_bytes()
        original_consumer = (self.home / 'skills/image-editor/SKILL.md').read_bytes()
        p = self.plan()
        self.assertEqual(p['mode'], 'existing-native-binding')
        self.assertFalse((self.home / 'plugins/atlas').exists())
        applied = rollout.apply(self.receipt)
        self.assertEqual(applied['state'], 'applied')
        self.assertTrue((self.home / 'plugins/atlas').is_symlink())
        self.assertFalse((self.home / 'plugins/atlas-engine-client').is_symlink())
        self.assertTrue((self.shared / '__init__.py').is_file())
        guidance = self.home / 'plugin-data/atlas/references/profile-guidance/0'
        self.assertEqual((guidance / 'source.md').read_bytes(), original_skill)
        self.assertTrue((guidance / 'references/recipe.md').is_file())
        self.assertIn('atlas:atlas', (self.home / 'skills/image-editor/SKILL.md').read_text())
        self.assertTrue((self.home / 'skills/danbooru/SKILL.md').is_file())
        current = rollout.read_config(self.home)
        self.assertEqual(current['model'], original['model'])
        self.assertEqual(current['memory'], original['memory'])
        self.assertEqual(current['mcp_servers'], original['mcp_servers'])
        self.assertEqual(current['plugins']['entries']['atlas']['settings']['atlas_engine'], self.config['plugins']['entries']['atlas-engine-client']['settings']['atlas_engine'])
        self.assertEqual(self.credential.read_text(), 'only-this-profile')
        self.assertIn('native_discovery', run_probe(self.home, True))
        with self.assertRaises(ValueError):
            rollout.apply(self.receipt)
        restored = rollout.rollback(self.receipt)
        self.assertEqual(restored['state'], 'rolled-back')
        self.assertEqual(rollout.read_config(self.home), original)
        self.assertTrue((self.home / 'plugins/atlas-engine-client').is_symlink())
        self.assertEqual((self.home / 'plugins/atlas-engine-client').resolve(), self.shared)
        self.assertEqual((self.home / 'skills/creative/invokeai/SKILL.md').read_bytes(), original_skill)
        self.assertEqual((self.home / 'skills/image-editor/SKILL.md').read_bytes(), original_consumer)
        self.assertFalse((self.home / 'plugins/atlas').is_symlink())
        self.assertEqual(self.credential.read_text(), 'only-this-profile')

    def test_guidance_only_preserves_readonly_proxy_no_credential_grant(self):
        del self.config['plugins']['entries']['atlas-engine-client']['settings']
        self.write_config()
        self.assertEqual(self.plan()['binding'], {})
        rollout.apply(self.receipt)
        self.assertIn('"tools_available": "no"', run_probe(self.home, False))
        self.assertEqual(rollout.read_config(self.home)['mcp_servers'], self.config['mcp_servers'])
        self.assertEqual(rollout.read_config(self.home)['plugins']['entries']['atlas']['settings']['atlas_engine'], {})
        rollout.rollback(self.receipt)

    def test_plan_guard_and_partial_apply_rollback(self):
        self.plan()
        self.config['plugins']['disabled'].append('atlas-engine-client')
        self.write_config()
        with self.assertRaises(ValueError):
            rollout.apply(self.receipt)
        self.receipt.unlink()
        self.plan()
        with patch.object(rollout, 'configure', side_effect=RuntimeError('injected failure')):
            with self.assertRaises(RuntimeError):
                rollout.apply(self.receipt)
        self.assertEqual(json.loads(self.receipt.read_text())['state'], 'applying')
        rollout.rollback(self.receipt)
        self.assertEqual(rollout.read_config(self.home), self.config)
        self.assertTrue((self.home / 'plugins/atlas-engine-client').is_symlink())

    def test_rollback_refuses_external_config_and_shared_references_untouched(self):
        consumer = self.home / 'skills/image-editor'
        external = self.root / 'shared-skill'
        consumer.rename(external)
        consumer.symlink_to(external, target_is_directory=True)
        old = (external / 'SKILL.md').read_bytes()
        self.assertTrue(self.plan()['references'][0]['blocked_shared'])
        rollout.apply(self.receipt)
        self.assertEqual((external / 'SKILL.md').read_bytes(), old)
        c = rollout.read_config(self.home)
        c['plugins']['entries']['new-unrelated'] = {'enabled': False}
        (self.home / 'config.yaml').write_text(yaml.safe_dump(c))
        with self.assertRaises(ValueError):
            rollout.rollback(self.receipt)
        del c['plugins']['entries']['new-unrelated']
        (self.home / 'config.yaml').write_text(yaml.safe_dump(c))
        rollout.rollback(self.receipt)


if __name__ == '__main__':
    unittest.main()
