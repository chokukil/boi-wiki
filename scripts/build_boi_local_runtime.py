"""Build the shipped local runtime from exact canonical source bytes.

The archive is a release artifact, not another implementation of validation.
No server application, storage, network client or model runner is included.
Run --check in qualification to reject drift between release and source.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    'agent_kit/python/boi_source_inventory.py',
    'agent_kit/python/boi_local_knowledge_draft.py',
    'agent_kit/python/boi_local_review.py',
    'agent_kit/python/boi_local_bundle_archive.py',
    'agent_kit/python/boi_profile_intake_host.py',
    'agent_kit/python/boi_ontology_query_host.py',
)


def release_files(root=ROOT):
    """Walk explicit Python imports without importing product code at build time."""
    root = Path(root)
    pending, files, external = list(ENTRYPOINTS), {}, set()
    while pending:
        name = pending.pop()
        if name in files:
            continue
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('LOCAL_RUNTIME_SOURCE_MISSING:' + name)
        raw = path.read_bytes()
        files[name] = raw
        package = name.removesuffix('.py').split('/')[:-1]
        for node in ast.walk(ast.parse(raw)):
            modules = []
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    prefix = package[:len(package) - node.level + 1]
                    modules = ['.'.join(prefix + ([node.module] if node.module else [a.name]))
                               for a in (node.names[:1] if node.module else node.names)]
                else:
                    modules = [node.module]
            elif isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            for module in modules:
                if module.startswith(('boi_api.', 'agent_kit.')):
                    pending.append(module.replace('.', '/') + '.py')
                else:
                    external.add(module.split('.')[0])
    if external - sys.stdlib_module_names - {'pydantic'}:
        raise ValueError('LOCAL_RUNTIME_UNDECLARED_DEPENDENCIES:' + ','.join(sorted(external)))
    # This bound catches accidental storage/application imports. Raising it is
    # a release review, not an automatic way to bundle the server with the kit.
    if len(files) > 29:
        raise ValueError('LOCAL_RUNTIME_CONTRACT_CLOSURE_EXPANDED')
    source_digests = {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())}
    for name in tuple(files):
        for parent in Path(name).parents:
            if str(parent) != '.':
                files.setdefault(parent.as_posix() + '/__init__.py', b'')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    archive = output.getvalue()
    provenance = {'contract_version': 'boi/local-runtime-release@1',
                  'archive': 'local-contracts.zip', 'sha256': hashlib.sha256(archive).hexdigest(),
                  'source_sha256': source_digests, 'third_party': ['pydantic==2.13.4'],
                  'generated_from_canonical_bytes': True}
    return {'local-contracts.zip': archive,
            'provenance.json': (json.dumps(provenance, indent=2, sort_keys=True) + '\n').encode()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    destination = ROOT / 'agent_kit/runtime'
    files = release_files()
    for name, raw in files.items():
        path = destination / name
        if args.check:
            if not path.is_file() or path.read_bytes() != raw:
                raise ValueError('LOCAL_RUNTIME_RELEASE_STALE:' + name)
        else:
            destination.mkdir(exist_ok=True)
            path.write_bytes(raw)
    print(json.dumps({'release': str(destination), 'checked': args.check,
                      'source_files': len(json.loads(files['provenance.json'])['source_sha256'])}))


if __name__ == '__main__':
    main()
