"""Atlas HTTP transport only. No Engine implementation or native backend imports."""
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

CHUNK = 32768
JSON_LIMIT = 8 * 1024 * 1024


class AtlasError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.body = {"ok": False, "error": {"code": code, "message": message}, **details}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, config):
        if not isinstance(config, dict) or not config.get('endpoint'):
            raise AtlasError('CLIENT_CONFIG', 'Configure this profile’s Atlas endpoint and credential; no inherited credentials.')
        self.config = dict(config)
        self.base = config['endpoint'].rstrip('/')
        u = urlsplit(self.base)
        if (u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password
                or u.query or u.fragment or u.path not in ('', '/')
                or (u.scheme == 'http' and u.hostname not in ('127.0.0.1', 'localhost', '::1'))):
            raise AtlasError('CLIENT_CONFIG', 'Use HTTPS or loopback HTTP without userinfo, path, query or fragment.')
        timeout = config.get('timeout_seconds', 45)
        if type(timeout) not in (int, float) or not 1 <= timeout <= 60:
            raise AtlasError('CLIENT_CONFIG', 'timeout_seconds must be within 1..60.')
        self.timeout = timeout
        # Explicit credential bindings only; never search another profile or environment default.
        try:
            if config.get('token_file'):
                p = Path(config['token_file']).expanduser()
                if not p.is_absolute() or p.stat().st_size > 16384:
                    raise ValueError()
                self.token = p.read_text().strip()
            elif config.get('token_env'):
                self.token = os.environ.get(config['token_env'], '')
            else:
                raise ValueError()
            if not self.token or '\n' in self.token or '\r' in self.token:
                raise ValueError()
        except (OSError, ValueError, TypeError):
            raise AtlasError('CLIENT_CREDENTIAL', 'The explicitly configured profile credential is missing or invalid.') from None
        # Do not send loopback credentials through environment proxies; never follow redirects.
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def clean(self, value):
        if isinstance(value, str):
            return value.replace(self.token, '[REDACTED]')
        if isinstance(value, list):
            return [self.clean(v) for v in value]
        if isinstance(value, dict):
            return {self.clean(k): self.clean(v) for k, v in value.items()}
        return value

    def request(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        req = Request(self.base + path, data=body, method=method,
                      headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json',
                               'User-Agent': 'hermes-atlas/1.0'})
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(JSON_LIMIT + 1)
                if len(raw) > JSON_LIMIT:
                    raise AtlasError('CLIENT_PROTOCOL', 'JSON response exceeds the bounded transport budget.')
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError()
                return self.clean(result)
        except HTTPError as exc:
            exc.close()
            # Do not echo response bodies, URLs, private headers or exception messages.
            code = 'REDIRECT_REFUSED' if 300 <= exc.code < 400 else ('ACK_UNKNOWN' if exc.code >= 500 and method == 'POST' else 'HTTP_ERROR')
            raise AtlasError(code, 'Atlas HTTP request did not complete successfully; do not blindly replay writes.', http_status=exc.code) from None
        except (URLError, OSError, TimeoutError):
            raise AtlasError('ACK_UNKNOWN' if method == 'POST' else 'CLIENT_UNAVAILABLE',
                             'Transport interrupted. Inspect the exact existing job/request; no automatic retry was made.') from None
        except (ValueError, UnicodeError):
            raise AtlasError('ACK_UNKNOWN' if method == 'POST' else 'CLIENT_PROTOCOL',
                             'Invalid Atlas JSON response; no automatic retry was made.') from None

    def call(self, operation, arguments):
        if not isinstance(operation, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.]{0,127}', operation):
            raise AtlasError('CLIENT_ARGUMENT', 'Invalid literal operation name.')
        if not isinstance(arguments, dict):
            raise AtlasError('CLIENT_ARGUMENT', 'arguments must be an object.')
        allowed = self.config.get('allowed_operations')
        if allowed is not None and operation not in allowed:
            raise AtlasError('CLIENT_SCOPE', 'Operation is outside this profile’s explicit allowlist.')
        return self.request('POST', '/v1/ops/' + operation, arguments)

    def result(self, operation, arguments):
        response = self.call(operation, arguments)
        if response.get('ok') is not True:
            raise EngineError(response)
        if 'result' not in response:
            raise AtlasError('CLIENT_PROTOCOL', 'Atlas result envelope is missing.')
        return response['result']

    def schema(self, operation=None):
        schema = self.request('GET', '/v1/schema')
        if operation is None:
            return {'ok': True, 'operations': sorted(schema)}
        if operation not in schema:
            raise AtlasError('CLIENT_ARGUMENT', 'Operation is absent from the live schema.')
        return {'ok': True, 'operation': operation, 'schema': schema[operation]}


class EngineError(AtlasError):
    def __init__(self, response):
        self.body = response
        Exception.__init__(self, 'Atlas operation failed')
