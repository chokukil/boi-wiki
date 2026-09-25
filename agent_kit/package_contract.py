"""Portable structural package checks shared by the installer and Wiki.

These checks bind guidance bytes and declared dependencies, not semantic quality
or execution authority. No repository imports or third-party runtime required.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
from pathlib import Path, PurePosixPath
import re


RESOURCE_CONTRACT = 'boi/domain-package-resources@1'
MAX_PACKAGES = 20
PROFILE_ADMISSION_ROLES = frozenset(('root','reference'))


def canonical_digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def dependency_order(entries, roots=None):
    """Return a bounded dependencies-first closure; never infer domain identity."""
    index = {}
    for entry in entries:
        identity = entry.get('id')
        if not isinstance(identity, str) or not identity or identity in index:
            raise ValueError('DOMAIN_PACKAGE_SHIPPED_CATALOG_AMBIGUOUS')
        index[identity] = entry
    ordered, active, done = [], set(), set()

    def visit(identity):
        if identity in active:
            raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_CYCLE')
        if identity in done:
            return
        if identity not in index:
            raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_MISSING')
        if len(done | active) >= MAX_PACKAGES:
            raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_LIMIT')
        entry = index[identity]
        dependencies = entry.get('dependencies', [])
        if (not isinstance(dependencies, (list, tuple)) or
                any(not isinstance(item, str) or not item for item in dependencies) or
                len(set(dependencies)) != len(dependencies)):
            raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_INVALID')
        scoped = entry.get('resource_contract') == RESOURCE_CONTRACT
        versions = entry.get('dependency_versions', {})
        if not isinstance(versions, dict) or (scoped and set(versions) != set(dependencies)):
            raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_VERSION_INVALID')
        admissions=entry.get('profile_admissions',[])
        if (not isinstance(admissions,list) or any(not isinstance(item,dict)
                or set(item)!= {'namespace','profile_id','role','can_anchor_extension'}
                or not isinstance(item['namespace'],str) or not item['namespace']
                or not isinstance(item['profile_id'],str) or not item['profile_id']
                or item['role'] not in PROFILE_ADMISSION_ROLES
                or type(item['can_anchor_extension']) is not bool for item in admissions)):
            raise ValueError('DOMAIN_PACKAGE_PROFILE_ADMISSION_INVALID')
        identities=[(item['namespace'],item['profile_id']) for item in admissions]
        if len(identities)!=len(set(identities)):
            raise ValueError('DOMAIN_PACKAGE_PROFILE_ADMISSION_AMBIGUOUS')
        declarations=entry.get('profile_declarations')
        if declarations is not None and (not isinstance(declarations,list) or any(not isinstance(item,dict)
                or set(item)!= {'namespace','profile_id','declaration'}
                or not isinstance(item['namespace'],str) or not item['namespace']
                or not isinstance(item['profile_id'],str) or not item['profile_id']
                or not isinstance(item['declaration'],dict)
                or item['declaration'].get('contract_version')!='boi/knowledge-profile@1'
                or item['declaration'].get('profile_id')!=item['profile_id']
                for item in declarations)):
            raise ValueError('DOMAIN_PACKAGE_PROFILE_DECLARATION_INVALID')
        declaration_identities=[(item['namespace'],item['profile_id']) for item in declarations or ()]
        if declarations is not None and (len(declaration_identities)!=len(set(declaration_identities))
                or set(declaration_identities)!=set(identities)):
            raise ValueError('DOMAIN_PACKAGE_PROFILE_DECLARATION_COVERAGE_INVALID')
        active.add(identity)
        for dependency in dependencies:
            visit(dependency)
            if dependency in versions and versions[dependency] != index[dependency].get('version'):
                raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_VERSION_MISMATCH')
        active.remove(identity)
        done.add(identity)
        ordered.append(entry)

    for identity in index if roots is None else roots:
        visit(identity)
    return ordered


def resource_files(kit_root, names):
    root = Path(kit_root).resolve()
    files = {}
    for name in names:
        if not isinstance(name, str):
            raise ValueError('DOMAIN_PACKAGE_SHIPPED_RESOURCE_INVALID')
        path = PurePosixPath(name)
        if not name or path.is_absolute() or '..' in path.parts or '\\' in name:
            raise ValueError('DOMAIN_PACKAGE_SHIPPED_RESOURCE_INVALID')
        source = root / name
        if (not source.exists() or any(part.is_symlink() for part in (source, *source.parents)) or
                not source.resolve().is_relative_to(root)):
            raise ValueError('DOMAIN_PACKAGE_SHIPPED_RESOURCE_INVALID')
        for item in sorted(source.rglob('*')) if source.is_dir() else (source,):
            if item.is_symlink():
                raise ValueError('DOMAIN_PACKAGE_SHIPPED_RESOURCE_INVALID')
            if item.is_file() and '__pycache__' not in item.parts and item.suffix != '.pyc':
                files[item.relative_to(root).as_posix()] = item.read_bytes()
    return files


def validate_references(files, names=None):
    """A local Markdown link must resolve within this package's declared closure."""
    for name in files if names is None else names:
        if not name.endswith('.md'):
            continue
        for target in re.findall(r'\]\(([^)]+)\)', files[name].decode('utf-8')):
            target = target.split('#', 1)[0].strip('<>')
            if not target or '://' in target or target.startswith('mailto:'):
                continue
            path = posixpath.normpath(str(PurePosixPath(name).parent / target))
            if path.startswith('../') or path not in files:
                raise ValueError('BOI_KIT_REFERENCE_MISSING:' + name + ':' + target)


def shipped_entries(manifest, kit_root, roots=None, *, cache=None):
    if manifest.get('schema_version', manifest.get('schema')) != 'boi/agent-kit-package@1':
        raise ValueError('DOMAIN_PACKAGE_SHIPPED_CATALOG_INVALID')
    ordered = dependency_order(manifest['domain_packages'], roots)
    built = {} if cache is None else cache
    contents = {}
    for entry in ordered:
        identity = entry['id']
        if identity in built:
            continue
        scoped = entry.get('resource_contract') == RESOURCE_CONTRACT
        if 'resource_contract' in entry and not scoped:
            raise ValueError('DOMAIN_PACKAGE_RESOURCE_CONTRACT_UNSUPPORTED')
        if scoped:
            names = entry.get('resource_paths')
            if not isinstance(names, list) or not names or not isinstance(entry.get('version'), str) or not entry['version']:
                raise ValueError('DOMAIN_PACKAGE_SHIPPED_RESOURCE_INVALID')
        else:
            # Legacy manifests remain readable; newly scoped packages exclude
            # unrelated domain resources and distribution version from identity.
            names = ['package.json', *manifest.get('resources', ()), *manifest.get('entrypoints', {}).values()]
        files = resource_files(kit_root, names)
        skill = entry['skill_path']
        if not skill.startswith('agent_kit/') or skill.removeprefix('agent_kit/') not in files:
            raise ValueError('DOMAIN_PACKAGE_SHIPPED_RESOURCE_INVALID')
        contents[identity] = files
        extra = {'dependency_manifest_digests': {
            dep: canonical_digest(built[dep]) for dep in entry['dependencies']},
            'runtime_contract': {key: manifest[key] for key in ('runtime', 'task_interface', 'supervision_interface') if key in manifest}
        } if scoped else {'kit_version': manifest['version']}
        built[identity] = {**entry, **extra,
            'skill_content_digest': 'sha256:' + hashlib.sha256(files[skill.removeprefix('agent_kit/')]).hexdigest(),
            'resource_digests': {'agent_kit/' + name: 'sha256:' + hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
            'execution_mode': 'external_agent_skill', 'semantic_quality': 'not_evaluated'}
    for entry in ordered:
        if entry.get('resource_contract') != RESOURCE_CONTRACT or entry['id'] not in contents:
            continue
        available = {}
        for member in dependency_order(manifest['domain_packages'], [entry['id']]):
            for path, digest in built[member['id']]['resource_digests'].items():
                name = path.removeprefix('agent_kit/')
                raw = contents.get(member['id'], {}).get(name)
                if raw is None:
                    raw = resource_files(kit_root, [name])[name]
                if 'sha256:' + hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError('DOMAIN_PACKAGE_SHIPPED_RESOURCE_CHANGED')
                if name in available and available[name] != raw:
                    raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_RESOURCE_CONFLICT')
                available[name] = raw
        validate_references(available, contents[entry['id']])
    return [built[entry['id']] for entry in ordered]
