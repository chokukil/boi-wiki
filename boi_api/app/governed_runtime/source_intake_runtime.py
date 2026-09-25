"""Server-owned runtime bindings; shared configured ledger/objects, no query DB dependency."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, model_validator
from typing import Callable
from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.governed_runtime.source_intake import SourceIntakeService, IntakeAuthorization
from boi_api.app.governed_runtime.ledger import GovernedRuntimeLedger
from boi_api.app.governed_runtime.release_rebuild import KnowledgeObjectStore
from boi_api.app.governed_runtime.semantic_profile_loader import ActiveReleaseProfileLoader
from boi_api.app.governed_runtime.record_field_metadata_intake import RecordSourceProfileContract
from boi_api.app.governed_runtime.semantic_binding_contract import Digest, semantic_digest
from boi_api.app.governed_runtime.metadata_mapping_profile import PhysicalColumnMetadataPolicy


class MetadataSourceSelection(BaseModel):
    """Server-registered scope; never a caller-proposed semantic authority."""
    model_config = ConfigDict(extra='forbid', frozen=True, hide_input_in_errors=True)
    source_profile: RecordSourceProfileContract
    catalog_snapshot_ref: str
    catalog_record_digest: Digest
    selector: dict[str, list[str]]
    physical_metadata_policy: PhysicalColumnMetadataPolicy | None = None


class MetadataRuntimeConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, hide_input_in_errors=True)
    contract_version: Literal['boi/metadata-runtime-configuration@1']
    source_selections: dict[str, MetadataSourceSelection]
    model_base_url: str
    model_id: str
    model_digest: Digest


class MetadataLogicalRuntimeConfiguration(MetadataRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@2']
    draft_contract_version:Literal['boi/metadata-logical-draft@1']


class MetadataReviewedRuntimeConfiguration(MetadataLogicalRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@3']
    reviewed_definition_policy:Literal['boi/reviewed-definitions@1']


class MetadataSourceMeaningRuntimeConfiguration(MetadataLogicalRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@4']
    source_meaning_policy:Literal['boi/separate-source-reading@1']


class MetadataSourceGroundedRuntimeConfiguration(MetadataSourceMeaningRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@5']
    domain_materialization_policy:Literal['boi/source-grounded-domain@1']


class MetadataReviewedSourceGroundedRuntimeConfiguration(MetadataSourceGroundedRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@6']
    reviewed_definition_policy:Literal['boi/reviewed-definitions@1']


class MetadataTypedSourceRuntimeConfiguration(MetadataReviewedSourceGroundedRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@7']
    typed_reading_policy:Literal['boi/source-meaning-reading@2']


class MetadataSegmentSourceRuntimeConfiguration(MetadataTypedSourceRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@8']
    typed_reading_policy:Literal['boi/source-meaning-reading@3']
    source_segment_policy:Literal['boi/source-segment-catalog@1']


class MetadataGraphSourceRuntimeConfiguration(MetadataSegmentSourceRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@9']
    source_contract_graph_policy:Literal['boi/source-contract-graph@1']


class MetadataQualifierSourceRuntimeConfiguration(MetadataGraphSourceRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@10']
    source_contract_graph_policy:Literal['boi/source-contract-graph@2']
    source_qualifier_policy:Literal['boi/semantic-qualifier@1']


class MetadataSubjectFacetRuntimeConfiguration(MetadataQualifierSourceRuntimeConfiguration):
    contract_version:Literal['boi/metadata-runtime-configuration@11']
    source_contract_graph_policy:Literal['boi/source-contract-graph@3']
    source_subject_facet_policy:Literal['boi/source-subject-facets@1']


@dataclass(frozen=True)
class PreparedMetadataInvocation:
    input: dict
    published_records: tuple
    definitions: object
    authorization: object
    model_client: object
    source_meaning_client: object = None


class SourceIntakeRuntimePolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, hide_input_in_errors=True)
    contract_version: Literal['boi/source-intake-runtime-policy@0.1.0']
    principal_ids: tuple[str, ...] = ()
    role_ids: tuple[str, ...] = ()
    allowed_uses: tuple[Literal['store','cite','derive','model_input','model_training','org_share'], ...]
    visibility: Literal['private','team','public']
    team_id: str | None = None
    effective_from: datetime
    stale_after: datetime

    @model_validator(mode='after')
    def closed_grant(self):
        if not self.principal_ids and not self.role_ids:
            raise ValueError('SOURCE_POLICY_EMPTY_GRANT')
        if any(not item.strip() or item=='*' for item in (*self.principal_ids,*self.role_ids)):
            raise ValueError('SOURCE_POLICY_EXPLICIT_GRANT_REQUIRED')
        if 'store' not in self.allowed_uses:
            raise ValueError('SOURCE_POLICY_STORE_RIGHT_REQUIRED')
        if self.visibility=='team' and not self.team_id:
            raise ValueError('SOURCE_POLICY_TEAM_REQUIRED')
        if (self.effective_from.tzinfo is None or self.stale_after.tzinfo is None
            or self.effective_from>=self.stale_after):
            raise ValueError('SOURCE_POLICY_TIME_INVALID')
        return self


@dataclass(frozen=True)
class SourceIntakeBindings:
    policy_path: Path
    policy_digest: str
    ledger: GovernedRuntimeLedger
    objects: KnowledgeObjectStore
    clock: Callable[[], datetime]
    metadata_configuration_path: Path | None = None
    metadata_configuration_digest: str = ''

    def current_policy(self):
        try:
            with self.policy_path.open('rb') as handle:
                raw=handle.read(65537)
            if len(raw)>65536 or byte_digest(raw)!=self.policy_digest:
                raise ValueError('SOURCE_RUNTIME_POLICY_DIGEST_MISMATCH')
            policy=SourceIntakeRuntimePolicy.model_validate_json(raw)
        except (OSError, ValueError):
            raise ValueError('SOURCE_RUNTIME_POLICY_INVALID_OR_CHANGED') from None
        now=self.clock()
        if now.tzinfo is None or not policy.effective_from<=now<policy.stale_after:
            raise ValueError('SOURCE_RUNTIME_POLICY_STALE')
        return policy

    def authorize(self, principal):
        policy=self.current_policy()
        if (principal.employee_id not in policy.principal_ids
            and not set(principal.roles).intersection(policy.role_ids)):
            raise ValueError('SOURCE_RUNTIME_PRINCIPAL_DENIED')
        if principal.token_id and not {'boi.draft','boi.admin'}.intersection(principal.token_scopes):
            raise ValueError('SOURCE_RUNTIME_TOKEN_SCOPE_DENIED')
        if policy.visibility=='team' and policy.team_id not in principal.teams:
            raise ValueError('SOURCE_RUNTIME_TEAM_DENIED')
        return IntakeAuthorization(principal.employee_id,self.policy_digest,policy.allowed_uses,
                                   policy.visibility,policy.team_id)

    def factory(self, store):
        # Reads/writes exactly these injected canonical resource objects.
        return SourceIntakeService(store=store,ledger=self.ledger,objects=self.objects,clock=self.clock,
            current_source_policy=self.current_policy_digest)

    def current_policy_digest(self):
        self.current_policy()
        return self.policy_digest

    def definition_loader(self):
        return ActiveReleaseProfileLoader(self.ledger,self.objects)

    def semantic_authority(self, *, source_intake, principal, prepared):
        from .semantic_definition_reading import ActiveDefinitionAuthorityResolver
        from .semantic_profile_loader import ProfilePrincipal
        return ActiveDefinitionAuthorityResolver(source_intake=source_intake,
            authorization=prepared.authorization,definitions=prepared.definitions,
            current_authorization=lambda:self.authorize(principal),
            reload_definitions=lambda:self.definition_loader().load_definition_scope(
                principal=ProfilePrincipal(principal_id=principal.employee_id,team_ids=tuple(principal.teams)),
                purpose=prepared.input['purpose'],namespace=prepared.definitions.lookup.namespace,
                policy_digest=prepared.authorization.policy_digest,at=self.clock()))

    def metadata_mapping_service(self, *, source_intake, principal, prepared, gateway=None):
        from .metadata_mapping_profile import SemanticMetadataMappingService
        configuration=self.current_metadata_configuration()
        selection=configuration.source_selections[prepared.input['metadata_source_profile_id']]
        return SemanticMetadataMappingService(source_intake=source_intake,
            authorization=prepared.authorization,source_profile=selection.source_profile,
            policy=selection.physical_metadata_policy,current_authorization=lambda:self.authorize(principal),
            gateway=gateway,purpose=prepared.input['purpose'])

    def current_metadata_configuration(self):
        self.current_policy()
        if not self.metadata_configuration_path:
            raise ValueError('SEMANTIC_METADATA_RUNTIME_UNAVAILABLE')
        try:
            with self.metadata_configuration_path.open('rb') as handle:
                raw=handle.read(1048577)
            if len(raw)>1048576 or byte_digest(raw)!=self.metadata_configuration_digest:
                raise ValueError('METADATA_RUNTIME_CONFIGURATION_DRIFT')
            import json
            value=json.loads(raw)
            if not isinstance(value,dict):
                raise ValueError('METADATA_RUNTIME_CONFIGURATION_OBJECT_REQUIRED')
            models={1:MetadataRuntimeConfiguration,2:MetadataLogicalRuntimeConfiguration,
                3:MetadataReviewedRuntimeConfiguration,4:MetadataSourceMeaningRuntimeConfiguration,
                5:MetadataSourceGroundedRuntimeConfiguration,6:MetadataReviewedSourceGroundedRuntimeConfiguration,
                7:MetadataTypedSourceRuntimeConfiguration,8:MetadataSegmentSourceRuntimeConfiguration,
                9:MetadataGraphSourceRuntimeConfiguration,10:MetadataQualifierSourceRuntimeConfiguration,
                11:MetadataSubjectFacetRuntimeConfiguration}
            model=next((cls for version,cls in models.items() if value.get('contract_version')==
                f'boi/metadata-runtime-configuration@{version}'),MetadataRuntimeConfiguration)
            result=model.model_validate(value)
        except (OSError, ValueError):
            raise ValueError('METADATA_RUNTIME_CONFIGURATION_INVALID_OR_CHANGED') from None
        return result

    def prepare_metadata(self, *, source_intake, principal, value):
        """Resolve source/scope/purpose into exact refs before shared execution.

        No model invocation, query execution, Release mutation or alternate SOT.
        Repeated normalization validates the same server pins, never trusts the
        client's copied catalog/definition/profile digests.
        """
        from boi_api.app.governed_runtime.semantic_profile_loader import ProfilePrincipal
        from boi_api.app.governed_runtime.semantic_metadata_pi_client import SemanticMetadataPiClient
        from boi_api.app.governed_runtime.bulk_migration_execution import SEMANTIC_METADATA_PIPELINE_V1
        if source_intake.ledger is not self.ledger or source_intake.objects is not self.objects:
            raise ValueError('SOURCE_RUNTIME_CANONICAL_RESOURCE_MISMATCH')
        authorization=self.authorize(principal)
        configuration=self.current_metadata_configuration()
        selection_id=str(value.get('metadata_source_profile_id') or '')
        selection=configuration.source_selections.get(selection_id)
        if selection is None:
            raise ValueError('METADATA_SOURCE_PROFILE_NOT_REGISTERED')
        if value.get('mode','metadata_first')!='metadata_first':
            raise ValueError('METADATA_RUNTIME_MODE_UNSUPPORTED')
        if value.get('mapping_candidates') or value.get('evidence_span_refs'):
            raise ValueError('METADATA_SERVER_EVIDENCE_REQUIRED')
        if not str(value.get('purpose') or '').strip():
            raise ValueError('PURPOSE_REQUIRED')
        if not value.get('source_artifacts'):
            raise ValueError('SOURCE_ARTIFACT_REQUIRED')
        catalog=source_intake.store.get('bulk_migration_catalog_snapshots',selection.catalog_snapshot_ref)
        if not catalog or catalog.get('employee_id')!=principal.employee_id:
            raise ValueError('METADATA_CATALOG_ACCESS_DENIED')
        material={k:v for k,v in catalog.items() if k!='updated_at'}
        if semantic_digest(material)!=selection.catalog_record_digest:
            raise ValueError('METADATA_CATALOG_SNAPSHOT_DRIFT')
        definitions=self.definition_loader().load_definition_scope(
            principal=ProfilePrincipal(principal_id=principal.employee_id,team_ids=tuple(principal.teams)),
            purpose=value['purpose'],namespace=selection.source_profile.namespace,
            policy_digest=authorization.policy_digest,at=self.clock())
        if not definitions.lookup.permits_absence_claim:
            raise ValueError('DEFINITION_READ_LOOKUP_SCOPE_INCOMPLETE')
        published=[]
        for reference in sorted(value['source_artifacts'],key=lambda r:r['artifact_ref']):
            published.extend(source_intake.metadata.extract(authorization=authorization,reference=reference,
                profile=selection.source_profile,profile_digest=semantic_digest(selection.source_profile)))
        if not published:
            raise ValueError('EMPTY_SELECTOR_EXPANSION')
        client=SemanticMetadataPiClient(base_url=configuration.model_base_url,model_id=configuration.model_id,
            model_digest=configuration.model_digest,
            input_contract_version='boi/definition-first-input@0.4.0' if isinstance(configuration,MetadataLogicalRuntimeConfiguration)
                else 'boi/definition-first-input@0.3.0'
                if selection.source_profile.profile_version=='boi/record-field-metadata-source@0.2.0'
                else 'boi/definition-first-input@0.2.0')
        source_meaning_client=None
        if isinstance(configuration,MetadataSourceMeaningRuntimeConfiguration):
            from .source_meaning_client import SourceMeaningClient,SourceGroundedDomainClient
            client_type=SourceGroundedDomainClient if isinstance(configuration,MetadataSourceGroundedRuntimeConfiguration) else SourceMeaningClient
            if isinstance(configuration,MetadataTypedSourceRuntimeConfiguration):
                from .source_meaning_client import TypedSourceGroundedDomainClient
                client_type=TypedSourceGroundedDomainClient
            if isinstance(configuration,MetadataSegmentSourceRuntimeConfiguration):
                from .source_meaning_client import SegmentSourceGroundedDomainClient
                client_type=SegmentSourceGroundedDomainClient
            if isinstance(configuration,MetadataGraphSourceRuntimeConfiguration):
                from .source_meaning_client import GraphSourceGroundedDomainClient
                client_type=GraphSourceGroundedDomainClient
            if isinstance(configuration,MetadataQualifierSourceRuntimeConfiguration):
                from .source_meaning_client import QualifierSourceGroundedDomainClient
                client_type=QualifierSourceGroundedDomainClient
            if isinstance(configuration,MetadataSubjectFacetRuntimeConfiguration):
                from .source_meaning_client import SubjectFacetSourceGroundedDomainClient
                client_type=SubjectFacetSourceGroundedDomainClient
            source_meaning_client=client_type(base_url=configuration.model_base_url,
                model_id=configuration.model_id,model_digest=configuration.model_digest)
        cap=int(value.get('max_objects_per_shard',100))
        if not 1<=cap<=100:
            raise ValueError('SHARD_SIZE_LIMIT_INVALID')
        # Four atoms per source record, at most one physical binding and one
        # owner shape per atom. Reserve all three profile families when physical
        # mapping is configured. Small explicit caps still fail closed on actual
        # excess; they are never silently raised. Historical v1 remains readable.
        profiles_enabled=selection.physical_metadata_policy is not None
        per_record=min(12 if profiles_enabled else 4,cap); per_shard=max(1,cap//per_record)
        fingerprints=tuple(item.receipt_ref for item in published)
        metadata_closure={
            'contract_version':'boi/metadata-execution-closure@2' if profiles_enabled else 'boi/metadata-execution-closure@1',
            'configuration_digest':self.metadata_configuration_digest,
            'source_profile_digest':semantic_digest(selection.source_profile),
            'source_selection_id':selection_id,
            'definition_closure_digest':semantic_digest(definitions.lookup),
            'source_record_count':len(published),'source_record_set_digest':semantic_digest(fingerprints),
            'records_per_shard':per_shard,'candidate_capacity_per_record':per_record,
            'atomic_count_basis':'domain_mapping_query_candidate_capacity' if profiles_enabled else 'derived_candidate_capacity'}
        if client.logical:
            metadata_closure.update(contract_version='boi/metadata-execution-closure@3',
                draft_contract_version=client.output_contract_version,logical_profile_revision='boi/domain@0.4.0')
        if isinstance(configuration,(MetadataReviewedRuntimeConfiguration,MetadataReviewedSourceGroundedRuntimeConfiguration)):
            metadata_closure.update(contract_version='boi/metadata-execution-closure@4',
                reviewed_definition_policy=configuration.reviewed_definition_policy)
        index_ref='definition-index:'+semantic_digest(definitions.lookup)
        index={'employee_id':principal.employee_id,'index_ref':index_ref,
            'digest':definitions.lookup.index_revision_digest,'lookup':definitions.lookup.model_dump(mode='json'),
            'items':[entry.model_dump(mode='json') for entry in definitions.entries]}
        source_intake.metadata._save_exact([('bulk_migration_concept_indexes',index_ref,index)])
        resolved={
            'mode':'metadata_first','pipeline_contract_id':SEMANTIC_METADATA_PIPELINE_V1.contract_id,
            'catalog_snapshot_ref':selection.catalog_snapshot_ref,'catalog_snapshot_digest':catalog['digest'],
            'schema_snapshot_digest':catalog['schema_digest'],'selector':selection.selector,
            'active_concept_index_ref':index_ref,'active_concept_index_digest':definitions.lookup.index_revision_digest,
            'acl_policy_digest':authorization.policy_digest,'metadata_execution':metadata_closure,
            'profile_revisions':[selection.source_profile.profile_version,SEMANTIC_METADATA_PIPELINE_V1.contract_id],
            'evaluator_code_digests':[semantic_digest({name:byte_digest((Path(__file__).parent/name).read_bytes())
                for name in ('source_intake_runtime.py','canonical_metadata_intake.py','semantic_metadata_stages.py',
                    'metadata_atomic_draft.py','semantic_binding_validator.py','semantic_definition_reading.py',
                    'domain_profile_v05.py','domain_profile_v04.py','domain_profile_v03.py','domain_profile_v02.py',
                    'semantic_metadata_pi_client.py','metadata_reference_scope.py','record_field_metadata_intake.py',
                    'source_meaning_client.py','source_meaning_comparison.py','source_segment_catalog.py','source_contract_graph.py',
                    'semantic_qualifier.py','source_subject_facets.py','frozen_source_meaning.py','source_grounded_domain.py',
                    'semantic_profile_loader.py','okf_v02.py','metadata_mapping_profile.py',
                    'corporate_metadata_intake.py','bulk_migration_execution.py','bulk_migration.py',
                    'bulk_migration_qualification.py','bulk_migration_review.py','query_gateway.py',
                    'multi_result_query_gateway.py','sqlite_source_snapshot.py',
                    'bulk_migration_tasks.py','semantic_inference_cache.py','reviewed_metadata_query.py')})],
            'model_role_prompt_digests':[configuration.model_digest,semantic_digest(client.ROLE),client.prompt_digest],
            'atomic_object_count':min(len(published),per_shard)*per_record,
            'local_model_policy':'pi-unresolved-only-no-codex-fallback',
            'resume_retry_policy':'exact-failed-shard-only'}
        if client.logical:
            resolved['profile_revisions'].extend([client.output_contract_version,'boi/domain@0.4.0'])
        if source_meaning_client is not None:
            reading_revision=(configuration.typed_reading_policy if isinstance(configuration,MetadataTypedSourceRuntimeConfiguration)
                              else 'boi/source-meaning-reading@1')
            resolved['profile_revisions'].extend([reading_revision,'boi/source-meaning-comparison@1'])
            if isinstance(configuration,MetadataSegmentSourceRuntimeConfiguration):
                resolved['profile_revisions'].append(configuration.source_segment_policy)
            if isinstance(configuration,MetadataGraphSourceRuntimeConfiguration):
                resolved['profile_revisions'].append(configuration.source_contract_graph_policy)
            if isinstance(configuration,MetadataQualifierSourceRuntimeConfiguration):
                resolved['profile_revisions'].append(configuration.source_qualifier_policy)
            if isinstance(configuration,MetadataSubjectFacetRuntimeConfiguration):
                resolved['profile_revisions'].append(configuration.source_subject_facet_policy)
            if getattr(source_meaning_client,'max_reading_passes',1)>1:
                resolved['profile_revisions'].append('boi/source-reading-continuation@1')
            resolved['model_role_prompt_digests'].append(source_meaning_client.prompt_digest)
            if isinstance(configuration,MetadataSourceGroundedRuntimeConfiguration):
                resolved['profile_revisions'].append(configuration.domain_materialization_policy)
        for key,expected in resolved.items():
            if key in value and value[key]!=expected:
                raise ValueError('METADATA_SERVER_RESOLVED_INPUT_DRIFT')
        normalized={**value,**resolved}
        normalized.setdefault('requested_skill_stages',list(SEMANTIC_METADATA_PIPELINE_V1.required_stage_ids))
        normalized.setdefault('max_objects_per_shard',100)
        normalized.setdefault('evaluator_code_digests',[])
        normalized.setdefault('before_hashes',{})
        normalized.setdefault('dry_run',True)
        return PreparedMetadataInvocation(normalized,tuple(published),definitions,authorization,client,source_meaning_client)


def build_source_intake_bindings(environ, *, clock=None, ledger=None, objects=None):
    if str(environ.get('BOI_SOURCE_INTAKE_ENABLED','')).lower() not in {'1','true','yes','on'}:
        return None
    names=('BOI_PROFILE_QUERY_LEDGER_ROOT','BOI_PROFILE_QUERY_OBJECT_ROOT',
           'BOI_SOURCE_INTAKE_POLICY_PATH','BOI_SOURCE_INTAKE_POLICY_DIGEST')
    if not all(str(environ.get(name,'')).strip() for name in names):
        raise ValueError('SOURCE_RUNTIME_CONFIGURATION_INCOMPLETE')
    ledger_root=Path(environ[names[0]]).resolve()
    object_root=Path(environ[names[1]]).resolve()
    # Do not initialize a new ledger as a fallback for a missing canonical path.
    if not (ledger_root/'records').is_dir() or not object_root.is_dir():
        raise ValueError('SOURCE_RUNTIME_CANONICAL_RESOURCES_MISSING')
    if (ledger is None) != (objects is None):
        raise ValueError('SOURCE_RUNTIME_RESOURCE_PAIR_REQUIRED')
    if ledger is not None and (ledger.root.resolve()!=ledger_root or objects.root.resolve()!=object_root):
        raise ValueError('SOURCE_RUNTIME_CANONICAL_RESOURCE_MISMATCH')
    metadata_path=str(environ.get('BOI_METADATA_RUNTIME_CONFIGURATION_PATH','')).strip()
    metadata_digest=str(environ.get('BOI_METADATA_RUNTIME_CONFIGURATION_DIGEST','')).strip()
    if bool(metadata_path)!=bool(metadata_digest):
        raise ValueError('METADATA_RUNTIME_CONFIGURATION_INCOMPLETE')
    bindings=SourceIntakeBindings(Path(environ[names[2]]),str(environ[names[3]]),
        ledger or GovernedRuntimeLedger(ledger_root),objects or KnowledgeObjectStore(object_root),
        clock or (lambda:datetime.now(timezone.utc)),
        Path(metadata_path) if metadata_path else None,metadata_digest)
    bindings.current_policy()
    if metadata_path:
        configuration=bindings.current_metadata_configuration()
        from boi_api.app.governed_runtime.semantic_metadata_pi_client import SemanticMetadataPiClient
        SemanticMetadataPiClient(base_url=configuration.model_base_url,model_id=configuration.model_id,
            model_digest=configuration.model_digest)  # validates local transport, no model call
    return bindings
