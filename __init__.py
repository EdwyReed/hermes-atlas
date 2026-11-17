"""One native Hermes plugin. Registration performs no network/file transfer."""
import json
from pathlib import Path
from .client import Client, AtlasError
from .media import Files
from .schemas import SCHEMAS


def invoke(name, args, config):
    client = None
    try:
        if not isinstance(args, dict):
            raise AtlasError('CLIENT_ARGUMENT', 'Tool arguments must be an object.')
        # Host validates schemas; retain validation for direct handler callers too.
        from jsonschema import validate, ValidationError
        try:
            validate(args, SCHEMAS[name]['parameters'])
        except ValidationError:
            raise AtlasError('CLIENT_ARGUMENT', 'Tool arguments do not match the public schema.') from None
        client = Client(config)
        if name == 'atlas_engine':
            result = client.call(args['operation'], args.get('arguments', {}))
        elif name == 'atlas_files':
            result = Files(client).handle(args)
        elif name == 'atlas_mask':
            result = Files(client).mask(args)
        else:
            result = Files(client).censor(args)
        return client.clean(result)
    except AtlasError as exc:
        result = dict(exc.body)
        if isinstance(args, dict):
            rid = args.get('request_id') or (args.get('arguments') or {}).get('request_id')
            if rid:
                result['request_id'] = rid
        return client.clean(result) if client else result
    except (OSError, ValueError, KeyError, TypeError):
        # Never echo local credential paths, source data, signed URLs or raw exception text.
        return {'ok': False, 'error': {'code': 'CLIENT_ARGUMENT_OR_IO', 'message': 'Invalid file/arguments or local IO failure. Inspect existing receipts before retrying.'}}


def register(ctx):
    ctx.register_skill('atlas', Path(__file__).parent / 'skills/atlas/SKILL.md',
                       description='Use for Atlas images, workflows, models, dream and masks.')
    for name, schema in SCHEMAS.items():
        def handler(args, _name=name, **_metadata):
            return json.dumps(invoke(_name, args, ctx.get_config('atlas_engine', {})), ensure_ascii=False, allow_nan=False)
        def available():
            c = ctx.get_config('atlas_engine', {})
            return bool(isinstance(c, dict) and c.get('endpoint') and (c.get('token_file') or c.get('token_env')))
        ctx.register_tool(name=name, toolset=('atlas_engine' if name == 'atlas_files' else name), schema=schema, handler=handler,
                          check_fn=available, description=schema['description'])
