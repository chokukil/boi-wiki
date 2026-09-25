#!/usr/bin/env python3
"""Install or bundle the complete native agent kit without repository imports."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid
import zipfile


# Explicit sibling loading also works when the downloaded installer is run
# with Python -I, which intentionally omits the script directory from sys.path.
_contract_spec = importlib.util.spec_from_file_location('boi_kit_package_contract', Path(__file__).with_name('package_contract.py'))
_contract = importlib.util.module_from_spec(_contract_spec)
_contract_spec.loader.exec_module(_contract)
validate_references = _contract.validate_references


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def package_files(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'package.json').read_text())
    if manifest.get('schema_version') != 'boi/agent-kit-package@1':
        raise ValueError('BOI_KIT_MANIFEST_INVALID')
    names = ['package.json', 'install.py', *manifest['entrypoints'].values(), *manifest['resources']]
    files = {}
    for name in names:
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('BOI_KIT_RESOURCE_PATH_INVALID')
        source = root / name
        if not source.exists() or source.is_symlink():
            raise ValueError('BOI_KIT_RESOURCE_MISSING_OR_LINKED')
        candidates = source.rglob('*') if source.is_dir() else (source,)
        for item in candidates:
            if item.is_symlink():
                raise ValueError('BOI_KIT_RESOURCE_LINKED')
            if item.is_file() and '__pycache__' not in item.parts and item.suffix != '.pyc':
                files[item.relative_to(root).as_posix()] = item.read_bytes()
    for package in manifest['domain_packages']:
        name = package['skill_path'].removeprefix('agent_kit/')
        if name not in files:
            raise ValueError('BOI_KIT_PACKAGE_SKILL_MISSING')
    entries = _contract.shipped_entries(manifest, root)
    for entry in entries:
        if any(name.removeprefix('agent_kit/') not in files for name in entry['resource_digests']):
            raise ValueError('BOI_KIT_PACKAGE_RESOURCE_NOT_DISTRIBUTED')
    return manifest, files


def install(root, target, client):
    manifest, files = package_files(root)
    if client not in manifest['entrypoints']:
        raise ValueError('BOI_KIT_CLIENT_INVALID')
    # Entrypoint is installed at the package root; its source copy is retained.
    files['SKILL.md'] = files[manifest['entrypoints'][client]].replace(b'](../', b'](')
    validate_references(files)
    installed = {'schema_version': 'boi/agent-kit-install@1', 'version': manifest['version'],
                 'client': client, 'files': {name: digest(raw) for name, raw in sorted(files.items())}}
    files['installed-manifest.json'] = (json.dumps(installed, ensure_ascii=False, indent=2) + '\n').encode()
    target = Path(target).absolute()
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise ValueError('BOI_KIT_TARGET_INVALID')
    if target.exists() and all((target / name).is_file() and not (target / name).is_symlink()
                               and (target / name).read_bytes() == raw for name, raw in files.items()):
        return {'status': 'unchanged', 'target': str(target), 'version': manifest['version']}
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + target.name + '-stage-', dir=target.parent))
    backup = None
    try:
        if target.exists():
            shutil.copytree(target, stage, dirs_exist_ok=True, symlinks=True)
        for name, raw in files.items():
            destination = stage / name
            if any(part.is_symlink() for part in (destination, *destination.parents)):
                raise ValueError('BOI_KIT_TARGET_RESOURCE_LINKED')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        if target.exists():
            backup = target.parent / ('.' + target.name + '-backup-' + uuid.uuid4().hex)
            target.rename(backup)
        try:
            stage.rename(target)
        except BaseException:
            if backup is not None:
                backup.rename(target)
            raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {'status': 'installed', 'target': str(target), 'version': manifest['version'],
            'files': len(installed['files']), 'previous_install_backup': str(backup) if backup else None,
            'server_connection_verified': False}


def verify(target):
    target = Path(target)
    installed = json.loads((target / 'installed-manifest.json').read_text())
    files = {}
    for name, expected in installed['files'].items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('BOI_KIT_INSTALLED_PATH_INVALID')
        actual = target / name
        if any(part.is_symlink() for part in (actual, *actual.parents)) or not actual.is_file():
            raise ValueError('BOI_KIT_INSTALLED_FILE_MISSING:' + name)
        files[name] = actual.read_bytes()
        if digest(files[name]) != expected:
            raise ValueError('BOI_KIT_INSTALLED_FILE_CHANGED:' + name)
    validate_references(files)
    package_files(target)
    return {'status': 'verified', 'files': len(files), 'version': installed['version'],
            'server_connection_verified': False, 'semantic_qualification': False}


def bundle(root, destination):
    manifest, files = package_files(root)
    validate_references(files)
    destination = Path(destination)
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            archive.writestr('boi-agent-kit/' + name, raw)
    return {'status': 'bundled', 'path': str(destination), 'version': manifest['version'],
            'sha256': digest(destination.read_bytes()), 'files': len(files)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', choices=('codex', 'claude'))
    parser.add_argument('--target', type=Path)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    try:
        if args.bundle:
            value = bundle(root, args.bundle)
        elif args.verify:
            if not args.target:
                raise ValueError('BOI_KIT_TARGET_REQUIRED')
            value = verify(args.target)
        else:
            if not args.client:
                raise ValueError('BOI_KIT_CLIENT_REQUIRED')
            target = args.target
            if target is None:
                base = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) if args.client == 'codex' else Path.home() / '.claude'
                target = base / 'skills' / 'boi-wiki-v2'
            value = install(root, target, args.client)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
