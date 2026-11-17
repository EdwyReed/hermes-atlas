"""Offline integration checks against a real loopback HTTP fixture, not an Engine."""
import base64
import hashlib
import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('atlas_under_test', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
atlas = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = atlas
spec.loader.exec_module(atlas)
from atlas_under_test.client import Client, AtlasError
from atlas_under_test.media import Files


class State:
    def __init__(self):
        self.calls = []
        self.uploads = {}
        self.phase = 'queued'
        self.corrupt = False
        self.mode = 'normal'
        self.name = 'image.png'
        self.raw = bytes(range(256)) * 257
        self.get_failure = False
        self.artifacts = True

    def descriptor(self):
        return {'artifact_id': 'artifact-1', 'job_id': 'job-1', 'image_name': self.name,
                'size': len(self.raw), 'sha256': hashlib.sha256(self.raw).hexdigest()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, value, status=200):
        raw = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.send({'capabilities': {'type': 'object'}, 'mask.segment': {'type': 'object'}})

    def do_POST(self):
        s = self.server.state
        op = self.path.rsplit('/', 1)[-1]
        p = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        s.calls.append((op, p, self.headers.get('Authorization')))
        if s.mode == 'redirect':
            self.send_response(307)
            self.send_header('Location', self.server.other_url)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if s.mode == 'drop':
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        if s.mode == 'malformed':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'not-json')
            return
        if s.mode == 'forbidden':
            self.send({'token': 'fixture-secret'}, 403)
            return
        if s.mode == 'error':
            self.send({'token': 'fixture-secret'}, 503)
            return
        r = {'echo': p, 'secret': 'fixture-secret'}
        if op.endswith('.begin'):
            uid = str(len(s.uploads))
            s.uploads[uid] = {'raw': bytearray(), 'expected': p}
            r = {'upload_id': uid}
        elif op.endswith('.chunk'):
            u = s.uploads[p['upload_id']]
            assert p['offset'] == len(u['raw'])
            u['raw'].extend(base64.b64decode(p['base64']))
            r = {'received': len(u['raw'])}
        elif op.endswith('.finalize'):
            u = s.uploads[p['upload_id']]
            assert hashlib.sha256(u['raw']).hexdigest() == u['expected']['sha256']
            assert len(u['raw']) == u['expected']['size']
            r = {'upload_id': p['upload_id'], 'state': 'ready'}
        elif op in ('censor.process', 'mask.segment'):
            r = {'id': 'job-1', 'state': 'queued'}
        elif op in ('censor.get', 'mask.get', 'generation.get', 'dream.get'):
            if s.get_failure:
                self.send({}, 503)
                return
            r = {'id': p['job_id'], 'state': s.phase, 'result': {'detections': 0},
                 'error': {'code': 'INTERRUPTED'} if s.phase == 'interrupted' else None}
        elif op == 'artifact.list':
            r = [s.descriptor()] if s.artifacts else []
        elif op == 'artifact.fetch':
            r = s.descriptor()
        elif op == 'artifact.read':
            chunk = s.raw[p['offset']:p['offset'] + p['size']]
            if s.corrupt:
                chunk = b'X' * len(chunk)
            r = {'base64': base64.b64encode(chunk).decode(), 'eof': p['offset'] + len(chunk) == len(s.raw)}
        self.send({'ok': True, 'operation': op, 'result': r})


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.other_url = 'http://127.0.0.1:1/stolen'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.token = self.home / 'token'
        self.token.write_text('fixture-secret')
        self.config = {'endpoint': f'http://127.0.0.1:{self.server.server_port}', 'token_file': str(self.token)}
        self.s = self.server.state = State()

    def invoke(self, name, args):
        return atlas.invoke(name, args, self.config)

    def test_full_passthrough_literal_arguments_and_redaction(self):
        args = {'request_id': 'unchanged:ID', 'unexpected_future_field': ['literal', 0.65]}
        r = self.invoke('atlas_engine', {'operation': 'future.operation', 'arguments': args})
        self.assertTrue(r['ok'])
        self.assertEqual(self.s.calls[0][:2], ('future.operation', args))
        self.assertNotIn('fixture-secret', json.dumps(r))
        self.assertEqual(self.s.calls[0][2], 'Bearer fixture-secret')

    def test_schema_and_invalid_operation_and_scope(self):
        self.assertEqual(self.invoke('atlas_files', {'action': 'schema'})['operations'], ['capabilities', 'mask.segment'])
        self.assertEqual(self.invoke('atlas_files', {'action': 'schema', 'operation': 'mask.segment'})['schema']['type'], 'object')
        for name in ('../native', ' mask.segment', 'mask/segment'):
            self.assertFalse(self.invoke('atlas_engine', {'operation': name})['ok'])
        self.assertEqual(len(self.s.calls), 0)
        self.config['allowed_operations'] = ['capabilities']
        self.assertEqual(self.invoke('atlas_engine', {'operation': 'generation.submit'})['error']['code'], 'CLIENT_SCOPE')

    def test_credentials_isolated_no_fallback(self):
        other = self.home / 'other'
        other.write_text('other-secret')
        with patch.dict(os.environ, {'ATLAS_ENGINE_TOKEN': 'fixture-secret'}):
            self.assertFalse(atlas.invoke('atlas_engine', {'operation': 'capabilities'}, {})['ok'])
            missing = dict(self.config, token_file=str(self.home / 'missing'))
            self.assertFalse(atlas.invoke('atlas_engine', {'operation': 'capabilities'}, missing)['ok'])
        c = dict(self.config, token_file=str(other))
        atlas.invoke('atlas_engine', {'operation': 'capabilities'}, c)
        self.assertEqual(self.s.calls[-1][2], 'Bearer other-secret')
        self.assertEqual(other.read_text(), 'other-secret')

    def test_redirect_errors_and_unknown_ack_never_retry(self):
        for mode, code in [('redirect', 'REDIRECT_REFUSED'), ('drop', 'ACK_UNKNOWN'), ('malformed', 'ACK_UNKNOWN'), ('forbidden', 'HTTP_ERROR'), ('error', 'ACK_UNKNOWN')]:
            with self.subTest(mode=mode):
                self.s.mode = mode
                before = len(self.s.calls)
                r = self.invoke('atlas_engine', {'operation': 'generation.submit', 'arguments': {'request_id': 'stable-1'}})
                self.assertEqual(r['error']['code'], code)
                self.assertEqual(r['request_id'], 'stable-1')
                self.assertEqual(len(self.s.calls), before + 1)
                self.assertNotIn('fixture-secret', json.dumps(r))

    def test_upload_bytes_native_and_media(self):
        source = self.home / 'source.png'
        source.write_bytes(self.s.raw)
        for namespace in ('native', 'media'):
            r = self.invoke('atlas_files', {'action': 'upload', 'namespace': namespace, 'path': str(source), 'request_id': namespace})
            self.assertTrue(r['ok'])
            self.assertEqual(self.s.uploads[r['upload_id']]['raw'], self.s.raw)
            self.assertEqual(r['sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(len([x for x in self.s.calls if x[0].endswith('.chunk')]), 6)

    def test_queued_censor_alias_then_exact_get_collects_bytes(self):
        src = self.home / 'in'
        src.mkdir()
        (src / 'image.png').write_bytes(b'fixture-input')
        out = self.home / 'out'
        r = self.invoke('anime_mosaic', {'action': 'process', 'input_dir': str(src), 'output_dir': str(out), 'request_id': 'censor-1'})
        self.assertTrue(r['ok'])
        self.assertTrue(r['pending'])
        self.assertEqual(r['job_id'], 'job-1')
        self.assertFalse(out.exists())
        self.s.phase = 'succeeded'
        r = self.invoke('atlas_censor', {'action': 'get', 'job_id': r['job_id'], 'output_dir': str(out)})
        self.assertTrue(r['ok'])
        self.assertFalse(r['pending'])
        self.assertEqual((out / 'image.png').read_bytes(), self.s.raw)
        self.assertEqual(sum(c[0] == 'censor.process' for c in self.s.calls), 1)
        self.assertTrue((out / '.atlas-receipt.json').is_file())
        # Recollection resumes exact bytes without requiring overwrite or another submit.
        self.assertTrue(self.invoke('atlas_censor', {'action': 'get', 'job_id': 'job-1', 'output_dir': str(out)})['ok'])

    def test_known_job_survives_read_failure_and_terminal_failure(self):
        self.s.get_failure = True
        r = self.invoke('atlas_files', {'action': 'collect', 'kind': 'censor', 'job_id': 'job-1', 'output_dir': str(self.home / 'out')})
        self.assertFalse(r['ok'])
        self.assertEqual(r['job_id'], 'job-1')
        self.s.get_failure = False
        self.s.phase = 'interrupted'
        r = self.invoke('atlas_censor', {'action': 'get', 'job_id': 'job-1', 'output_dir': str(self.home / 'out')})
        self.assertFalse(r['ok'])
        self.assertEqual(r['error']['code'], 'INTERRUPTED')
        self.assertFalse(any(x[0] == 'censor.process' for x in self.s.calls))

    def test_corrupt_unsafe_existing_and_empty_artifacts(self):
        self.s.phase = 'succeeded'
        args = {'action': 'collect', 'kind': 'mask', 'job_id': 'job-1', 'output_dir': str(self.home / 'out')}
        self.s.corrupt = True
        self.assertEqual(self.invoke('atlas_files', args)['error']['code'], 'CLIENT_CHECKSUM')
        self.assertFalse((self.home / 'out/image.png').exists())
        self.s.corrupt = False
        self.s.name = '../escape.png'
        self.assertEqual(self.invoke('atlas_files', args)['error']['code'], 'CLIENT_PATH')
        self.s.name = 'image.png'
        (self.home / 'out').mkdir()
        (self.home / 'out/image.png').write_bytes(b'original')
        self.assertEqual(self.invoke('atlas_files', args)['error']['code'], 'CLIENT_EXISTS')
        self.assertEqual((self.home / 'out/image.png').read_bytes(), b'original')
        self.s.artifacts = False
        r = self.invoke('atlas_files', args)
        self.assertTrue(r['delivery_pending'])
        self.assertFalse(r['delivered'])

    def test_mask_prior_keeps_original_manifest(self):
        self.s.phase = 'succeeded'
        out = self.home / 'old'
        out.mkdir()
        manifest = out / 'manifest.json'
        raw = b'{"engine_job_id":"job-prior"}'
        manifest.write_bytes(raw)
        r = self.invoke('atlas_mask', {'action': 'segment', 'cache_id': 'cache-1', 'output_dir': str(self.home / 'masks'), 'request_id': 'mask-v2', 'prior': {'manifest_path': str(manifest), 'candidate': 2}, 'points': [{'x': 2, 'y': 3, 'label': 1}]})
        self.assertTrue(r['ok'])
        submitted = next(p for op, p, _ in self.s.calls if op == 'mask.segment')
        self.assertEqual(submitted['prior'], {'job_id': 'job-prior', 'candidate': 2})
        self.assertEqual(manifest.read_bytes(), raw)

    def test_file_denial_and_invalid_tool_arguments_before_network(self):
        self.assertFalse(self.invoke('atlas_files', {'action': 'upload', 'path': 'relative.png', 'request_id': 'x'})['ok'])
        self.assertFalse(self.invoke('atlas_censor', {'action': 'process', 'unknown': True})['ok'])
        self.assertEqual(self.s.calls, [])


if __name__ == '__main__':
    unittest.main()
