"""Bounded file transfer and job collection. Inference remains in Atlas Engine."""
import base64
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from .client import AtlasError, CHUNK

MAX_FILE = 64 * 1024 * 1024
MAX_ARTIFACT = 256 * 1024 * 1024
GETTERS = {'generation': 'generation.get', 'batch': 'batch.get', 'dream': 'dream.get',
           'mask': 'mask.get', 'censor': 'censor.get', 'admin': 'admin.get'}
PENDING = {'queued', 'running', 'pending', 'submitting', 'active', 'accepted'}


def local_path(value, write=False):
    from agent.file_safety import raise_if_read_blocked, get_write_denied_error
    p = Path(value).expanduser()
    if not p.is_absolute():
        raise AtlasError('CLIENT_PATH', 'An explicit absolute local path is required.')
    if write:
        error = get_write_denied_error(str(p))
        if error:
            raise AtlasError('CLIENT_PATH', 'Hermes denied this output path.')
    else:
        raise_if_read_blocked(str(p))
    return p


def save(path, raw, overwrite=False):
    p = local_path(str(path), write=True)
    if p.is_symlink():
        raise AtlasError('CLIENT_PATH', 'Refusing an output symlink.')
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name('.atlas-' + uuid.uuid4().hex + '.part')
    try:
        with temp.open('xb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        if overwrite:
            os.replace(temp, p)
        else:
            os.link(temp, p)
        # Delivery claims are based on the actual saved bytes.
        with p.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != hashlib.sha256(raw).hexdigest():
                raise AtlasError('CLIENT_CHECKSUM', 'Saved file checksum mismatch.')
    finally:
        temp.unlink(missing_ok=True)
    return str(p)


class Files:
    def __init__(self, client):
        self.client = client

    def upload_bytes(self, raw, request_id, namespace='media', role='image', finalize=True):
        limit = MAX_FILE if namespace == 'media' else 32 * 1024 * 1024
        if namespace not in ('media', 'native') or not 0 < len(raw) <= limit:
            raise AtlasError('CLIENT_ARGUMENT', 'Invalid upload namespace or file byte budget.')
        prefix = 'media.upload' if namespace == 'media' else 'upload'
        sha = hashlib.sha256(raw).hexdigest()
        result = self.client.result(prefix + '.begin', {'request_id': request_id, 'size': len(raw), 'sha256': sha, 'role': role})
        uid = result['upload_id']
        for offset in range(0, len(raw), CHUNK):
            self.client.result(prefix + '.chunk', {'upload_id': uid, 'offset': offset,
                                                  'base64': base64.b64encode(raw[offset:offset + CHUNK]).decode()})
        if finalize:
            result = self.client.result(prefix + '.finalize', {'upload_id': uid})
        # Engine's finalize verifies hash/pixels. Preserve the exact remote receipt, no native import.
        return {'ok': True, 'upload_id': uid, 'size': len(raw), 'sha256': sha, 'receipt': result}

    def upload(self, path, request_id, namespace='media', role='image'):
        p = local_path(path)
        if not p.is_file() or not 0 < p.stat().st_size <= MAX_FILE:
            raise AtlasError('CLIENT_ARGUMENT', 'Input must be a nonempty file within 64 MiB.')
        with p.open('rb') as f:
            raw = f.read(MAX_FILE + 1)
        return self.upload_bytes(raw, request_id, namespace, role)

    def download_bytes(self, artifact):
        size = artifact['size']
        if type(size) is not int or not 0 <= size <= MAX_ARTIFACT:
            raise AtlasError('CLIENT_ARGUMENT', 'Artifact exceeds the 256 MiB file budget.')
        raw = bytearray()
        while len(raw) < size:
            row = self.client.result('artifact.read', {'artifact_id': artifact['artifact_id'], 'offset': len(raw),
                                                      'size': min(CHUNK, size - len(raw))})
            chunk = base64.b64decode(row['base64'], validate=True)
            if not chunk or len(chunk) > min(CHUNK, size - len(raw)):
                raise AtlasError('CLIENT_PROTOCOL', 'Empty or oversized artifact chunk.')
            raw.extend(chunk)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != artifact['sha256']:
            raise AtlasError('CLIENT_CHECKSUM', 'Artifact size/SHA-256 mismatch; no file delivered.')
        return bytes(raw)

    def collect(self, kind, job_id, output_dir, wait_seconds=0, overwrite=False):
        try:
            return self._collect(kind, job_id, output_dir, wait_seconds, overwrite)
        except AtlasError as exc:
            return {**exc.body, 'job_id': job_id, 'output_dir': output_dir, 'recovery': 'Collect this exact job; do not submit again.'}
        except (OSError, ValueError, KeyError, TypeError):
            return {'ok': False, 'job_id': job_id, 'output_dir': output_dir,
                    'error': {'code': 'CLIENT_COLLECTION', 'message': 'Artifact retrieval or local save failed. Collect this exact job; no new submission was made.'}}

    def _collect(self, kind, job_id, output_dir, wait_seconds=0, overwrite=False):
        if kind not in GETTERS or type(wait_seconds) not in (int, float) or not 0 <= wait_seconds <= 30:
            raise AtlasError('CLIENT_ARGUMENT', 'Select a supported job kind and wait_seconds within 0..30.')
        out = local_path(output_dir, write=True)
        deadline = time.monotonic() + wait_seconds
        while True:
            job = self.client.result(GETTERS[kind], {'job_id': job_id})
            if job.get('id') != job_id:
                raise AtlasError('CLIENT_PROTOCOL', 'Readback job identity mismatch.')
            state = job['state']
            if state not in PENDING or time.monotonic() >= deadline:
                break
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))
        base = {'job_id': job_id, 'state': state, 'output_dir': str(out)}
        if state in PENDING:
            return {'ok': True, 'accepted': True, 'pending': True, **base}
        if state != 'succeeded':
            return {'ok': False, 'pending': False, **base, 'error': job.get('error') or {'code': 'JOB_NOT_SUCCEEDED', 'message': 'Inspect the exact job; no new submission made.'}}
        artifacts = self.client.result('artifact.list', {'job_id': job_id})
        if not isinstance(artifacts, list):
            raise AtlasError('CLIENT_PROTOCOL', 'Artifact list must be an array.')
        if not artifacts:
            return {'ok': True, 'pending': False, 'delivery_pending': kind in ('generation', 'mask', 'censor'),
                    'delivered': False, **base, 'files': [], 'result': job.get('result')}
        # Validate the whole output set before touching any file.
        names = set()
        for a in artifacts:
            name = a['image_name']
            if (not isinstance(name, str) or not name or name in ('.', '..') or '/' in name or '\\' in name
                    or name == '.atlas-receipt.json' or name in names or a.get('job_id') != job_id):
                raise AtlasError('CLIENT_PATH', 'Unsafe, duplicate or foreign-job artifact descriptor.')
            names.add(name)
            dest = local_path(str(out / name), write=True)
            if dest.is_symlink() or (dest.exists() and not overwrite):
                # Exact already-delivered bytes make collection safely resumable, not a new write.
                if dest.is_file() and not dest.is_symlink():
                    with dest.open('rb') as f:
                        if dest.stat().st_size == a['size'] and hashlib.file_digest(f, 'sha256').hexdigest() == a['sha256']:
                            continue
                raise AtlasError('CLIENT_EXISTS', 'Output exists with different bytes; explicit overwrite required.')
        delivered = []
        for a in artifacts:
            raw = self.download_bytes(a)
            dest = out / a['image_name']
            if not dest.exists() or overwrite:
                save(dest, raw, overwrite)
            delivered.append({'path': str(dest), **a})
        # Keep source manifests byte-exact. A separate local receipt enables prior refinement.
        receipt = {'engine_job_id': job_id, 'kind': kind, 'artifacts': artifacts}
        receipt_path = out / '.atlas-receipt.json'
        save(receipt_path, (json.dumps(receipt, indent=2) + '\n').encode(), overwrite=True)
        result = {'ok': True, 'accepted': True, 'pending': False, **base, 'files': delivered,
                  'receipt_path': str(receipt_path), 'result': job.get('result')}
        if 'manifest.json' in names:
            result['manifest_path'] = str(out / 'manifest.json')
        return result

    def prior(self, prior, request_id):
        idx = prior['candidate']
        if type(idx) is not int or not 0 <= idx <= 2:
            raise AtlasError('CLIENT_ARGUMENT', 'Select an explicit prior candidate within 0..2.')
        mp = local_path(prior['manifest_path'])
        if mp.stat().st_size > 131072:
            raise AtlasError('CLIENT_ARGUMENT', 'Prior manifest too large.')
        manifest = json.loads(mp.read_text())
        receipt = mp.parent / '.atlas-receipt.json'
        if receipt.is_file():
            local_path(str(receipt))
            if receipt.stat().st_size > 131072:
                raise AtlasError('CLIENT_ARGUMENT', 'Prior receipt too large.')
            manifest = json.loads(receipt.read_text())
        if manifest.get('engine_job_id'):
            return {'job_id': manifest['engine_job_id'], 'candidate': idx}
        lp = local_path(str(mp.parent / f'candidate-{idx}.npy'))
        if lp.stat().st_size > 300000:
            raise AtlasError('CLIENT_ARGUMENT', 'Prior logits too large.')
        # Historic logits ingress is deliberately not pixel-finalized, matching Engine contract.
        m = self.upload_bytes(mp.read_bytes(), request_id + ':manifest', finalize=False)
        l = self.upload_bytes(lp.read_bytes(), request_id + ':logits', finalize=False)
        return {'manifest_upload_id': m['upload_id'], 'logits_upload_id': l['upload_id'], 'candidate': idx}

    def admit(self, operation, payload):
        try:
            return self.client.result(operation, payload)
        except AtlasError as exc:
            exc.body['request_id'] = payload.get('request_id')
            raise

    def mask(self, args):
        action = args['action']
        p = {k: v for k, v in args.items() if k != 'action'}
        if action == 'setup':
            rid = p.pop('request_id', str(uuid.uuid4()))
            uid = self.upload(p.pop('image_path'), rid)['upload_id']
            return self.client.call('mask.setup', {'upload_id': uid})
        if action == 'segment':
            out = local_path(p.pop('output_dir'), write=True) / ('atlas-mask-' + uuid.uuid4().hex)
            wait = p.pop('wait_seconds', 0)
            p.setdefault('request_id', str(uuid.uuid4()))
            if p.get('prior'):
                p['prior'] = self.prior(p['prior'], p['request_id'])
            job = self.admit('mask.segment', p)
            return self.collect('mask', job['id'], str(out), wait)
        if action == 'get':
            return self.collect('mask', p['job_id'], p['output_dir'], p.get('wait_seconds', 0))
        return self.client.call('mask.' + action, p)

    def censor(self, args):
        action = args['action']
        if action == 'health':
            return self.client.call('censor.health', {})
        if action == 'get':
            return self.collect('censor', args['job_id'], args['output_dir'], args.get('wait_seconds', 0), args.get('overwrite', False))
        src = local_path(args['input_dir']).resolve()
        out = local_path(args['output_dir'], write=True).resolve()
        if not src.is_dir() or src == out:
            raise AtlasError('CLIENT_PATH', 'Existing input and separate explicit output directory required.')
        files = sorted((p for p in src.iterdir() if p.is_file() and p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')), key=lambda p: p.name)
        if not 1 <= len(files) <= 200:
            raise AtlasError('CLIENT_ARGUMENT', 'Censor batch requires 1..200 images.')
        preview = args.get('preview')
        if preview is not None:
            if type(preview) is not int or not 1 <= preview <= 100:
                raise AtlasError('CLIENT_ARGUMENT', 'preview must be within 1..100.')
            files = files[:preview]
        overwrite = args.get('overwrite', False)
        if not overwrite and any((out / name).exists() for name in [p.name for p in files] + ['manifest.json']):
            raise AtlasError('CLIENT_EXISTS', 'Existing outputs require explicit overwrite before submission.')
        rid = args.get('request_id') or str(uuid.uuid4())
        images = [{'name': p.name, 'upload_id': self.upload(str(p), rid + ':' + str(i))['upload_id']} for i, p in enumerate(files)]
        options = {k: v for k, v in args.items() if k not in ('action', 'input_dir', 'output_dir', 'request_id', 'overwrite', 'wait_seconds', 'preview')}
        job = self.admit('censor.process', {'request_id': rid, 'images': images, **options})
        return self.collect('censor', job['id'], str(out), args.get('wait_seconds', 0), overwrite)

    def handle(self, args):
        action = args['action']
        if action == 'schema':
            return self.client.schema(args.get('operation'))
        if action == 'upload':
            return self.upload(args['path'], args['request_id'], args.get('namespace', 'media'), args.get('role', 'image'))
        if action == 'collect':
            return self.collect(args['kind'], args['job_id'], args['output_dir'], args.get('wait_seconds', 0), args.get('overwrite', False))
        if action == 'download':
            # Descriptor is obtained from the exact job, never trusted from a model-supplied hash.
            a = self.client.result('artifact.fetch', {'job_id': args['job_id'], 'image_name': args['image_name']})
            if a.get('job_id') != args['job_id'] or a.get('image_name') != args['image_name']:
                raise AtlasError('CLIENT_PROTOCOL', 'Artifact fetch identity mismatch.')
            raw = self.download_bytes(a)
            path = save(args['path'], raw, args.get('overwrite', False))
            return {'ok': True, 'path': path, 'size': len(raw), 'sha256': a['sha256'], 'artifact_id': a['artifact_id']}
        raise AtlasError('CLIENT_ARGUMENT', 'Unknown file action.')
