"""Opt-in development restart acceptance using the official authorized services.

No credentials, source text or automatic qualification writes. The config is
operator-owned, outside Wiki content. Liveness does not imply acceptance.
"""
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import threading

from .development_release_gate import check_release


def run_acceptance(config_path, *, observe, release_identity):
    path=Path(config_path)
    runs=path.parent/'development-release-runs'
    runs.mkdir(mode=0o700,parents=True,exist_ok=True)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex
    output=runs/(run_id+'.json')
    result={'run_id':run_id,'started_at':datetime.now(timezone.utc).isoformat(),
        'ready':False,'state':'checking','issues':[], 'observations':[],
        'scope':'configured required uses only; not semantic, performance or user-answer acceptance'}
    def save():
        temporary=output.with_suffix('.tmp')
        temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        temporary.chmod(0o600);temporary.replace(output)
    save()
    try:
        config=json.loads(path.read_text());manifest=config['manifest']
        from .governed_runtime.semantic_binding_contract import semantic_digest
        result.update(manifest_digest=semantic_digest(manifest),release_identity=release_identity())
        unique={json.dumps(m['revision'],sort_keys=True):m['revision']
            for scope in manifest['scopes'] for m in scope['members']}
        for revision in unique.values():
            try:
                result['observations'].append(observe(config['actor_id'],revision))
            except Exception:
                result['issues'].append({'revision':revision,'reason':'OFFICIAL_READ_FAILED_OR_UNKNOWN'})
            save()
        result['issues'].extend(check_release(manifest,result['observations']))
        if result['release_identity'].get('source_matches_deployment') is False:
            result['issues'].append({'reason':'DEPLOYED_SOURCE_CHANGED_OR_UNBOUND'})
        if release_identity()!=result['release_identity'] or json.loads(path.read_text())!=config:
            result['issues'].append({'reason':'RELEASE_OR_SCOPE_CHANGED_DURING_CHECK'})
        result.update(ready=not result['issues'],state='completed')
    except Exception:
        result.update(ready=False,state='failed')
        result['issues'].append({'reason':'ACCEPTANCE_CONFIGURATION_OR_RELEASE_UNKNOWN'})
    result['finished_at']=datetime.now(timezone.utc).isoformat();save()
    logging.getLogger(__name__).warning('Development qualification acceptance: ready=%s issues=%s report=%s',
        result['ready'],len(result['issues']),output)
    return result


def deployed_source_identity(root, expected):
    from .governed_runtime.semantic_binding_contract import semantic_digest
    from .governed_runtime.source_envelope import byte_digest
    root=Path(root).resolve();observed={}
    for name in expected.get('files',{}):
        path=(root/name).resolve()
        if not path.is_relative_to(root):
            raise ValueError('DEPLOYMENT_PATH_OUTSIDE_ROOT')
        observed[name]=byte_digest(path.read_bytes()) if path.is_file() else None
    return {'declared_commit':expected.get('commit'),
        'source_matches_deployment':bool(expected.get('commit') and observed) and observed==expected['files'],
        'installed_sources_digest':semantic_digest(observed),
        'deployment_manifest_digest':semantic_digest(expected)}


def start_development_release_acceptance(data_root, service, resolve_identity):
    path=Path(os.environ.get('BOI_DEVELOPMENT_RELEASE_CONFIG',str(Path(data_root)/'development-release.json')))
    if not path.is_file():
        return None  # Unconfigured installations acquire no development acceptance.
    def observe(actor_id,revision):
        from .governed_runtime.knowledge_published_read import PublishedDocumentRead
        from .governed_runtime.published_knowledge_contract import PublishedQualificationRead
        actor=resolve_identity(actor_id)  # Resolve current rights for each object.
        document=service.domain_intake.published_document(actor,PublishedDocumentRead(revision=revision))
        status=service.domain_intake.published_qualifications(actor,PublishedQualificationRead(revision=revision))
        return {'revision':status['revision'],'is_current_revision':document['is_current_revision'],'uses':status['uses']}
    def identity():
        from .governed_runtime.native_knowledge_checks import shipped_checker_release
        from .governed_runtime.local_knowledge_qualification import qualification_policy
        from .governed_runtime.semantic_binding_contract import semantic_digest
        root=Path(__file__).resolve().parents[2]
        deployment=json.loads(path.read_text()).get('deployment',{})
        return {**deployed_source_identity(root,deployment),'checker_release_digest':semantic_digest(shipped_checker_release()),
            'qualification_policy_digest':semantic_digest(qualification_policy())}
    thread=threading.Thread(target=run_acceptance,args=(path,),
        kwargs={'observe':observe,'release_identity':identity},name='development-release-acceptance',daemon=True)
    thread.start()
    return thread
