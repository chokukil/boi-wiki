"""Server-shipped mechanical checks on exact native revisions.

This is a built-in checker, not an uploaded plugin or a semantic evaluator.
Its output is evidence for admission; it grants neither publication nor use.
Domain checker requirements still need their separately adopted implementation.
"""
from importlib.metadata import version
from copy import deepcopy
import json
from pathlib import Path
import platform
import time

from pydantic import ValidationError

from .knowledge_content import decode_knowledge_content, meaning_pointer, validate_content_envelope
from .knowledge_profile import KnowledgeProfileDeclaration
from .knowledge_definition_checks import DEFINITION_CAPABILITIES, check_readable_definition
from .knowledge_profile_projector import ADAPTER_REVISION, KnowledgeProfileProjector, native_identity
from .knowledge_projection_contract import ProjectionPublication, PublicationChange
from .knowledge_unresolved_scope import overlaps as _overlap, typed_use_unresolved
from .knowledge_use_contract import typed_use_closure
from .ledger import record_digest
from .semantic_binding_contract import semantic_digest
from .source_envelope import byte_digest


CHECKER_ID = 'boi/native-content-mechanical@1'
# Pin the shipped implementation, including the validators called below. No
# source path, import name, code or registration authority comes from a bundle.
IMPLEMENTATION_FILES = (
    'native_knowledge_checks.py', 'knowledge_content.py', 'knowledge_use_purpose.py', 'knowledge_profile.py',
    'knowledge_profile_projector.py', 'knowledge_projection_contract.py',
    'typed_knowledge_meaning.py', 'okf_v02.py', 'semantic_binding_contract.py',
    'local_bundle_checks.py', 'native_mechanical_records.py', 'published_knowledge_context.py', 'local_bundle_import.py', 'local_bundle_index.py', 'local_bundle_service.py', 'domain_asset_store.py',
    'local_bundle_contract.py', 'local_bundle_snapshot.py', 'local_publication_plan.py', 'local_publication_state.py',
    '../v2/store.py', '../v2/store_connections.py',
    'domain_asset_staging.py', 'source_intake.py', 'source_envelope.py',
    'native_profile_catalog.py', 'local_native_review.py', 'native_definition_context.py', 'native_observation.py',
    'knowledge_formula_contract.py','formula_definition_context.py','common_knowledge_contract.py','formula_preview.py','svid_contract.py',
    'knowledge_definition_checks.py', 'knowledge_unresolved_scope.py','knowledge_unresolved_contract.py', 'knowledge_use_contract.py',
    'knowledge_statement_contract.py',
    'ledger.py', 'release_rebuild.py',
)


def _installed_checker_release():
    root = Path(__file__).parent
    return {'checker_id':CHECKER_ID, 'registration':'server_builtin',
        'implementation_manifest':{name:byte_digest((root / name).read_bytes()) for name in IMPLEMENTATION_FILES},
        'environment':{'python':platform.python_version(), 'pydantic':version('pydantic')},
        'input_contract':'boi/native-mechanical-input@1', 'output_contract':'boi/native-mechanical-report@1',
        'limits':{'native_bytes':16 * 1024 * 1024, 'total_native_bytes':64 * 1024 * 1024, 'native_revisions':128,
                  'report_bytes':4 * 1024 * 1024, 'cooperative_seconds':15},
        'effects':'read_only', 'semantic_verdict_issued':False}


# Replacing source files under a running process must not relabel old loaded
# functions with a new implementation digest. A new deployment loads a release.
_LOADED_RELEASE = _installed_checker_release()


def shipped_checker_release():
    if _installed_checker_release() != _LOADED_RELEASE:
        raise ValueError('NATIVE_CHECK_LOADED_RELEASE_STALE')
    return deepcopy(_LOADED_RELEASE)


class NativeKnowledgeChecks:
    def __init__(self, *, read_revision, ledger, objects, release=None, monotonic=time.monotonic):
        if not callable(read_revision):
            raise ValueError('NATIVE_CHECK_AUTHORIZED_READER_REQUIRED')
        self.read_revision, self.ledger, self.objects = read_revision, ledger, objects
        self.release = release or shipped_checker_release()
        self.monotonic = monotonic

    def run(self, *, revision, confirmation_ref, intended_uses):
        if self.release != shipped_checker_release():
            raise ValueError('NATIVE_CHECK_RELEASE_CHANGED')
        started = self.monotonic()
        loaded, checks, use_results, projected = {}, [], [], None
        identity_inputs={}
        total_bytes = 0

        def deadline():
            if self.monotonic() - started > self.release['limits']['cooperative_seconds']:
                raise TimeoutError('NATIVE_CHECK_COOPERATIVE_DEADLINE')

        def read(ref):
            nonlocal total_bytes
            deadline()
            if ref not in loaded:
                if len(loaded) >= self.release['limits']['native_revisions']:
                    raise OverflowError('NATIVE_CHECK_REVISION_LIMIT')
                record, asset = self.read_revision(ref)
                if (asset.revision != ref or record.record_id != ref.ref
                        or record_digest(record.record_id) != ref.revision_digest):
                    raise ValueError('NATIVE_CHECK_REVISION_BINDING_MISMATCH')
                if len(asset.content_json.encode('utf-8')) > self.release['limits']['native_bytes']:
                    raise OverflowError('NATIVE_CHECK_INPUT_BYTE_LIMIT')
                total_bytes += len(asset.content_json.encode('utf-8'))
                if total_bytes > self.release['limits']['total_native_bytes']:
                    raise OverflowError('NATIVE_CHECK_INPUT_BYTE_LIMIT')
                loaded[ref] = (record, asset)
            deadline()
            return loaded[ref]

        def check(capability, function):
            deadline()
            try:
                result = function()
            except ValidationError as exc:
                checks.append({'capability':capability, 'outcome':'violated',
                    'reason':'SCHEMA_INVALID', 'locations':[list(e['loc']) for e in exc.errors(include_input=False,include_url=False)[:32]]})
                return None
            except ValueError as exc:
                # Validator codes only. Never echo arbitrary document/error text.
                code = str(exc)
                if not code.isascii() or not all(c.isupper() or c.isdigit() or c == '_' for c in code):
                    code = 'CHECK_PROPERTY_INVALID'
                checks.append({'capability':capability, 'outcome':'violated', 'reason':code})
                return None
            deadline()
            checks.append({'capability':capability, 'outcome':'satisfied'})
            return result

        outcome = 'completed'
        try:
            # Access, immutable bytes and source authorization failures occur
            # outside property checks. They are execution errors, not false facts.
            record, asset = read(revision)
            native = json.loads(asset.content_json)
            from .domain_asset_staging import DomainAssetStaging
            draft = DomainAssetStaging._draft(record, asset)
            for dependency in draft.dependencies:
                if dependency.required:
                    read(dependency.revision)
            checks.append({'capability':'native_revision_and_required_references', 'outcome':'satisfied'})
            content = None
            if asset.kind == 'profile':
                check('profile_declaration', lambda:KnowledgeProfileDeclaration.model_validate(native))
            elif asset.kind == 'pack':
                from .local_native_review import CAPABILITY, parse_review_draft
                check(CAPABILITY, lambda:parse_review_draft(draft))
            elif asset.kind == 'definition':
                content = check('okf_content_contract', lambda:decode_knowledge_content(native))
                if content is None and checks[-1]['outcome'] == 'satisfied':
                    checks[-1] = {'capability':'okf_content_contract','outcome':'unsupported','reason':'CONTENT_ADAPTER_UNAVAILABLE'}
                if content is not None:
                    check('body_and_source_addresses', lambda:validate_content_envelope(native,
                        draft=draft, ledger=self.ledger, objects=self.objects))
                    def profiles():
                        for binding in content.profiles:
                            _, selected = read(binding.revision)
                            if selected.kind != 'profile':
                                raise ValueError('PROFILE_KIND_REQUIRED')
                            profile = KnowledgeProfileDeclaration.model_validate_json(selected.content_json)
                            if (binding.profile_id,binding.schema_ref) != (profile.profile_id,profile.schema_ref):
                                raise ValueError('PROFILE_BINDING_MISMATCH')
                            if profile.level_scheme:
                                if (binding.level is None or (binding.level.scheme,binding.level.version) !=
                                        (profile.level_scheme.scheme,profile.level_scheme.version)
                                        or binding.level.value not in profile.level_scheme.values):
                                    raise ValueError('PROFILE_LEVEL_INVALID')
                            elif binding.level is not None:
                                raise ValueError('PROFILE_LEVEL_UNDECLARED')
                    check('profile_bindings_and_levels', profiles)
                    if content.meaning.get('contract_version') == 'boi/typed-knowledge-meaning@1':
                        # An in-memory adapter input only; no generation is prepared
                        # and no publication manifest is committed by this checker.
                        projection = ProjectionPublication(scope_id=confirmation_ref, principal_id=record.payload['employee_id'],
                            base_generation=0, policy_digest=record.payload['policy_digest'], confirmation_ref=confirmation_ref,
                            source_manifest_digest=record.payload['source_manifest_digest'], adapter_revision=ADAPTER_REVISION,
                            changes=(PublicationChange(stable_id=native_identity(record),operation='upsert',
                                previous_revision=draft.previous_revision.model_dump(mode='json') if draft.previous_revision else None,
                                revision=revision.model_dump(mode='json')),))
                        def typed_projection():
                            from .native_mechanical_records import checked_identity_reference
                            from .typed_knowledge_meaning import TypedKnowledgeMeaning
                            batch,registry=KnowledgeProfileProjector(read_revision=read).materialize_with_registry(projection)
                            meaning=TypedKnowledgeMeaning.model_validate(content.meaning)
                            def target_type(stable_id,expected):
                                ref=checked_identity_reference(self.read_revision,stable_id)
                                target_record,target_asset=read(ref)
                                if native_identity(target_record)!=stable_id:
                                    raise ValueError('NATIVE_CHECK_IDENTITY_TARGET_CHANGED')
                                target=decode_knowledge_content(json.loads(target_asset.content_json))
                                if target is None:raise ValueError('NATIVE_CHECK_RELATION_TARGET_UNTYPED')
                                typed=TypedKnowledgeMeaning.model_validate(target.meaning)
                                if typed.object_type!=expected:raise ValueError('NATIVE_CHECK_RELATION_TARGET_TYPE_MISMATCH')
                                identity_inputs[stable_id]=ref.model_dump(mode='json')
                            for assertion in meaning.assertions:
                                _,predicate=registry.predicate(assertion.predicate)
                                if assertion.value.kind=='object':target_type(assertion.value.value,predicate.target_type)
                                for group in (assertion.conditions,assertion.exceptions,assertion.applicability):
                                    for clause in group:
                                        for atom in clause.atoms:
                                            _,predicate=registry.predicate(atom.predicate)
                                            if atom.subject_ref=='self':
                                                if predicate.subject_type!=meaning.object_type:
                                                    raise ValueError('NATIVE_CHECK_CONDITION_SUBJECT_TYPE_MISMATCH')
                                            else:target_type(atom.subject_ref,predicate.subject_type)
                                            if atom.value.kind=='object':target_type(atom.value.value,predicate.target_type)
                            return batch
                        projected = check('typed_profile_projection',typed_projection)
                        from .typed_knowledge_meaning import TypedKnowledgeMeaning
                        from .knowledge_formula_contract import CAPABILITY,check_parameter_definitions
                        def formula_parameters():
                            meaning=TypedKnowledgeMeaning.model_validate(content.meaning)
                            for i,parameter in enumerate(meaning.parameters):
                                if not any(b.meaning_pointer==f'/parameters/{i}' and b.assertion_kind==parameter.assertion_kind
                                           for b in content.body_bindings):
                                    raise ValueError('KNOWLEDGE_FORMULA_BODY_BINDING_REQUIRED')
                                check_parameter_definitions(parameter,asset,read)
                        check(CAPABILITY,formula_parameters)
                    elif content.meaning.get('contract_version') in DEFINITION_CAPABILITIES:
                        check(DEFINITION_CAPABILITIES[content.meaning['contract_version']],
                            lambda:check_readable_definition(content,record=record,asset=asset,
                                read_revision=read,ledger=self.ledger,objects=self.objects))
                    else:
                        checks.append({'capability':'typed_profile_projection','outcome':'unsupported','reason':'MEANING_ADAPTER_UNAVAILABLE'})
            else:
                checks.append({'capability':'native_content','outcome':'unsupported','reason':'CONTENT_KIND_UNSUPPORTED'})

            contracts = {u.purpose:u for u in content.use_contracts} if content else {}
            for purpose in dict.fromkeys(intended_uses):
                use = contracts.get(purpose)
                reasons, pointers = [], []
                if asset.kind == 'profile':
                    reasons.append('PROFILE_IS_A_DECLARATION')
                elif purpose != 'read' and use is None:
                    reasons.append('USE_CONTRACT_MISSING')
                if content is None:
                    reasons.append('OKF_CONTENT_UNAVAILABLE')
                elif use:
                    typed_scope=(typed_use_closure(content,use)
                        if content.meaning.get('contract_version')=='boi/typed-knowledge-meaning@1' else None)
                    if typed_scope is not None:
                        declared_unknown,projected_unknown=typed_use_unresolved(content,typed_scope,projected,purpose)
                        if declared_unknown:reasons.append('SELECTED_SCOPE_HAS_UNRESOLVED_INFORMATION')
                        if projected_unknown:reasons.append('SELECTED_TYPED_SCOPE_HAS_UNRESOLVED_INFORMATION')
                    for pointer in use.required_meaning_pointers:
                        pointers.append({'pointer':pointer,'value_digest':semantic_digest(meaning_pointer(content.meaning,pointer))})
                        if typed_scope is None and any(u.meaning_pointer is None or _overlap(pointer,u.meaning_pointer) for u in content.unresolved):
                            reasons.append('SELECTED_SCOPE_HAS_UNRESOLVED_INFORMATION')
                        if not any(pointer == b.meaning_pointer or pointer.startswith(b.meaning_pointer + '/')
                                   or b.meaning_pointer == '' for b in content.evidence_bindings):
                            reasons.append('SELECTED_SCOPE_EVIDENCE_ADDRESS_MISSING')
                    if use.prerequisites:
                        reasons.append('PREREQUISITE_EVALUATOR_REQUIRED')
                    if use.checker_requirements:
                        reasons.append('ADOPTED_DOMAIN_CHECKER_REQUIRED')
                relevant = [c for c in checks
                    if (purpose != 'read' or c['capability'] != 'typed_profile_projection')
                    and (purpose=='formula_input' or c['capability']!='formula_parameter_definitions')]
                if any(c['outcome'] != 'satisfied' for c in relevant):
                    reasons.append('MECHANICAL_CHECKS_INCOMPLETE')
                use_results.append({'purpose':purpose,'status':'mechanical_checks_complete' if not reasons else 'requires_qualification',
                    'selected_meaning':pointers,'requirements':use.model_dump(mode='json') if use else None,
                    'reasons':list(dict.fromkeys(reasons)), 'usable':False, 'semantic_status':'not_evaluated'})
        except TimeoutError:
            outcome = 'timeout'
        except OverflowError:
            outcome = 'limit_exceeded'
        except Exception:
            outcome = 'error'
        deadline_exceeded = self.monotonic() - started > self.release['limits']['cooperative_seconds']
        if deadline_exceeded:
            outcome = 'timeout'
        if self.release != _installed_checker_release():
            outcome = 'release_changed'
        if outcome != 'completed':
            for use in use_results:
                use['status'] = 'requires_qualification'
                use['reasons'].append('CHECK_EXECUTION_NOT_COMPLETED')
        report = {'contract_version':'boi/native-mechanical-report@1', 'target_revision':revision.model_dump(mode='json'),
            'confirmation_ref':confirmation_ref, 'checker_release':self.release,
            'checker_release_digest':semantic_digest(self.release), 'outcome':outcome, 'checks':checks,
            'native_inputs':[{'revision':ref.model_dump(mode='json'), 'content_digest':a.content_digest,
                'source_manifest_digest':r.payload['source_manifest_digest']} for ref,(r,a) in loaded.items()],
            'identity_inputs':[{'stable_id':stable_id,'revision':ref} for stable_id,ref in sorted(identity_inputs.items())],
            'intended_uses':list(intended_uses), 'use_results':use_results,
            'publication_granted':False, 'use_qualification_granted':False, 'semantic_verdict_issued':False}
        if len(json.dumps(report,ensure_ascii=False).encode()) > self.release['limits']['report_bytes']:
            report.update(outcome='limit_exceeded',checks=[],native_inputs=[],use_results=[])
        return report
