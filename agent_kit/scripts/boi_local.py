#!/usr/bin/env python3
"""Portable local preparation. Never sends data or runs a model."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path
import sys


def runtime():
    root = Path(__file__).resolve().parents[1] / 'runtime'
    provenance = json.loads((root / 'provenance.json').read_text(encoding='utf-8'))
    archive = root / 'local-contracts.zip'
    if (archive.is_symlink() or provenance.get('contract_version') != 'boi/local-runtime-release@1'
            or hashlib.sha256(archive.read_bytes()).hexdigest() != provenance['sha256']):
        raise ValueError('LOCAL_RUNTIME_RELEASE_CHANGED')
    try:
        if version('pydantic') != '2.13.4':
            raise ValueError('LOCAL_RUNTIME_INSTALL_PINNED_REQUIREMENTS')
    except PackageNotFoundError:
        raise ValueError('LOCAL_RUNTIME_INSTALL_PINNED_REQUIREMENTS') from None
    # Only the distributed archive is added; no repository or PYTHONPATH needed.
    sys.path.insert(0, str(archive))
    return provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Verify the distributed local runtime')
    schema = commands.add_parser('schema', help='Write the actual shared contract schemas and authoring field mapping')
    schema.add_argument('--output', type=Path, required=True)
    inspect = commands.add_parser('inspect', help='Read original XLSX fields without assigning roles')
    inspect.add_argument('--source', type=Path, required=True)
    inspect.add_argument('--output', type=Path, required=True)
    inventory = commands.add_parser('inventory', help='Preserve an explicitly authored field-role layout')
    inventory.add_argument('--source', type=Path, required=True)
    inventory.add_argument('--layout', type=Path, required=True)
    inventory.add_argument('--output', type=Path, required=True)
    assemble_parser = commands.add_parser('assemble', help='Check and assemble explicitly authored meanings')
    assemble_parser.add_argument('--spec', type=Path, required=True)
    assemble_parser.add_argument('--output', type=Path, required=True)
    review = commands.add_parser('review', help='Render a local read-only source/body comparison')
    review.add_argument('--spec', type=Path, required=True)
    review.add_argument('--bundle', type=Path, required=True)
    review.add_argument('--output', type=Path, required=True)
    pack = commands.add_parser('pack', help='Create one transport archive from the checked bundle')
    pack.add_argument('--bundle', type=Path, required=True)
    pack.add_argument('--output', type=Path, required=True)
    profile_prepare = commands.add_parser('profile-prepare',
        help='Prepare source records against the current admitted Profile catalog')
    profile_prepare.add_argument('--records', type=Path, required=True)
    profile_prepare.add_argument('--profile-material', type=Path, required=True)
    profile_prepare.add_argument('--source-scope', type=Path, required=True)
    profile_prepare.add_argument('--domain-guidance', type=Path)
    profile_prepare.add_argument('--maximum-selected', type=int, default=12)
    profile_prepare.add_argument('--output', type=Path, required=True)
    profile_candidates = commands.add_parser('profile-candidates',
        help='Validate candidate selection and prepare the full Profile comparison')
    profile_candidates.add_argument('--preparation', type=Path, required=True)
    profile_candidates.add_argument('--observation', type=Path, required=True)
    profile_candidates.add_argument('--output', type=Path, required=True)
    profile_route = commands.add_parser('profile-route',
        help='Validate reuse, extension or new-Profile routing')
    profile_route.add_argument('--candidate-stage', type=Path, required=True)
    profile_route.add_argument('--observation', type=Path, required=True)
    profile_route.add_argument('--output', type=Path, required=True)
    profile_layout_prepare = commands.add_parser('profile-layout-prepare',
        help='Prepare complete source-row disposition review')
    profile_layout_prepare.add_argument('--session', type=Path, required=True)
    profile_layout_prepare.add_argument('--output', type=Path, required=True)
    profile_layout_complete = commands.add_parser('profile-layout-complete',
        help='Validate the disposition of every source row')
    profile_layout_complete.add_argument('--preparation', type=Path, required=True)
    profile_layout_complete.add_argument('--observation', type=Path, required=True)
    profile_layout_complete.add_argument('--output', type=Path, required=True)
    profile_query_prepare = commands.add_parser('profile-query-prepare',
        help='Prepare a record-blind natural-language query plan')
    profile_query_prepare.add_argument('--session', type=Path, required=True)
    profile_query_prepare.add_argument('--question', required=True)
    profile_query_prepare.add_argument('--review', type=Path)
    profile_query_prepare.add_argument('--layout-review', type=Path)
    profile_query_prepare.add_argument('--output', type=Path, required=True)
    profile_query_execute = commands.add_parser('profile-query-execute',
        help='Validate and execute a Profile query plan')
    profile_query_execute.add_argument('--preparation', type=Path, required=True)
    profile_query_execute.add_argument('--plan', type=Path, required=True)
    profile_query_execute.add_argument('--output', type=Path, required=True)
    profile_query_recover = commands.add_parser('profile-query-recover',
        help='Prepare one record-blind retry for a zero-result plan')
    profile_query_recover.add_argument('--preparation', type=Path, required=True)
    profile_query_recover.add_argument('--execution', type=Path, required=True)
    profile_query_recover.add_argument('--output', type=Path, required=True)
    profile_query_render = commands.add_parser('profile-query-render',
        help='Render exact result values and source locations for the user')
    profile_query_render.add_argument('--preparation', type=Path, required=True)
    profile_query_render.add_argument('--execution', type=Path, required=True)
    profile_query_render.add_argument('--source-name', required=True)
    profile_query_render.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        provenance = runtime()
        from boi_api.app.governed_runtime.local_bundle_json import LocalJsonDocument
        if args.command == 'doctor':
            from agent_kit.python.boi_local_knowledge_draft import assemble
            result = {'runtime_sha256': provenance['sha256'], 'source_files': len(provenance['source_sha256']),
                      'assembler': assemble.__module__, 'repository_checkout_required': False,
                      'registered_server_checks_passed': False}
        elif args.command == 'schema':
            from boi_api.app.governed_runtime.knowledge_content import KnowledgeContent
            from boi_api.app.governed_runtime.knowledge_profile import KnowledgeProfileDeclaration
            from boi_api.app.governed_runtime.knowledge_use_contract import LocalKnowledgeAssessment
            from boi_api.app.governed_runtime.local_bundle_contract import LocalKnowledgeCorrection
            from boi_api.app.governed_runtime.typed_knowledge_meaning import TypedKnowledgeMeaning
            from agent_kit.python.boi_source_inventory import WorkbookInventoryLayout
            value = {model.__name__: model.model_json_schema() for model in (
                KnowledgeContent, KnowledgeProfileDeclaration, LocalKnowledgeAssessment,
                TypedKnowledgeMeaning, WorkbookInventoryLayout, LocalKnowledgeCorrection)}
            value['authoring_input'] = {
                'spec_fields': ['namespace','profile_logical_id','title','description','author_session_ref',
                                'sources','profile','records','intended_uses','unresolved','assessments',
                                'existing_profile_revision','profile_base_revision','profile_correction','existing_records'],
                'existing_profile_mapping': 'Optional existing_profile_revision is the exact {ref, revision_digest} '
                    'of a Wiki Profile already read. Supply its unchanged declaration in profile for local type checks. '
                    'The assembler creates no replacement Profile or schema source; it binds the revision in native '
                    'dependencies, component references, manifest and assessment inputs. The server rechecks the actual '
                    'Profile and current authority. Local validation cannot prove the supplied declaration matches '
                    'the live revision or grant usage. Omit this field when authoring a new Profile; null is invalid.',
                'profile_revision_mapping': 'If a Profile needs an explicitly authored change, use profile_base_revision '
                    'with the exact existing {ref, revision_digest} and its original namespace/profile_logical_id. '
                    'It requires profile_correction with the exact current expected_policy_revision '
                    '{ref, revision_digest}, a reason and source_difference describing the schema change. '
                    'This is the existing correction intent in the manifest, not permission or a semantic verdict. '
                    'The Profile change is revise against that base, while new records reference the revised local '
                    'Profile. Existing Wiki records retain their old references and are not rewritten. This field '
                    'is mutually exclusive with existing_profile_revision. Server impact, current edit permission '
                    'and concurrency checks remain required; the assembler does not approve the change.',
                'source_fields': ['path','inventory','byte_digest','media_type','source_role'],
                'record_fields': ['object_id','logical_id','source_object_id','source_record_locator',
                                  'object_type_id','title','description','frontmatter','body','assertions',
                                  'unresolved','use_contracts','coverage_disposition','context_fields','parameters',
                                  'previous_revision','correction','existing_sources'],
                'record_correction_mapping': 'For an existing knowledge record, supply its current exact '
                    'previous_revision together with correction {expected_policy_revision, reason, source_difference, '
                    'feedback_refs?}. Keep its namespace/logical_id. Supply the exact previously read source '
                    'ArtifactEnvelopes in record.existing_sources to retain lineage alongside the newly supplied '
                    'workbook. The assembler emits revise and declares existing refs/sources; it never infers the '
                    'base, policy or preserved source list. Server checks verify current head, edit/source rights '
                    'and source preservation. Absence of both revision fields retains create behavior.',
                'existing_record_mapping': 'spec.existing_records maps explicit local target keys to '
                    '{stable_id, revision, object_type}. All values must come from a current authorized read. '
                    'object_type is an exact Profile ProjectionComponent {revision, pointer}. Reference the key '
                    'through target_object_id or subject_object_id as for local records. Keys cannot overlap '
                    'records. The existing target is not recreated: its stable identity is retained and its exact '
                    'revision becomes a required relation_target dependency, manifest existing_revision and '
                    'assessment input revision. Local checking compares declared types only; the server verifies '
                    'identity, current revision/type and access. A name match or closest revision is not a binding.',
                'parameter_mapping': 'Optional parameters use TypedKnowledgeMeaning parameter fields plus evidence, '
                    'body_quote and body_occurrence as for assertions. Parameter definitions contain no observed value. '
                    'Use exact existing Wiki unit_definition and quantity_definition revisions. The assembler derives '
                    'their required dependencies and assessment input references; it does not verify current server '
                    'authority or unit definitions. Server checks and formula_input qualification remain required. '
                    'Do not infer measurement/setpoint roles, units or physical binding from labels.',
                'context_mapping': 'Optional context_fields declares up to 64 exact surrounding cells with '
                    'field_locator, role (source, metadata, review_note) and a nonempty reason. '
                    'Only explicitly declared surrounding cells can be quoted. At least one evidence quote '
                    'must anchor the primary source record. Review notes are read only when declared; '
                    'provided_model_answer and unassigned roles are not accepted. Preserve restoration uncertainty.',
                'assertion_mapping': 'Use the TypedKnowledgeMeaning assertion fields, replacing predicate with '
                    'the explicitly selected local predicate_id. Add evidence quotations to each assertion and '
                    'each conditions/exceptions/applicability clause. Each quotation contains field_locator, '
                    'quote and optional quote_occurrence. For condition atoms replace predicate with predicate_id. '
                    'Non-unknown valid_time needs valid_time_evidence. Optional body_quote selects the exact authored '
                    'prose passage; otherwise statement must appear verbatim in body. body_occurrence defaults to 0. '
                    'For object values use kind=object and target_object_id naming an explicitly authored record. '
                    'Its type must match the declared predicate target_type. For an external condition subject use '
                    'subject_object_id instead of subject_ref; no server identity is invented locally.',
                'unresolved_evidence_mapping': 'An unresolved item may supply evidence quotations with field_locator, '
                    'quote and optional quote_occurrence, using the same source record and explicitly declared '
                    'context_fields as assertion evidence. Do not combine this with nonempty source_spans. The '
                    'assembler binds those exact source fields through local placeholders to existing source_spans '
                    'and root source-context evidence. It does not change meaning_pointer, description, facets or '
                    'review labels. Omission preserves the existing global/node source-scope rules. First assemble '
                    'the source interpretation; read use_preparation.source_review_inventories for each exact '
                    'original inventory_digest, item_digest and required_fields. Supply the source-reviewed '
                    'statement_review with those digests. They bind original proposal tokens before server '
                    'reference replacement; never guess native refs or hash a later imported version. Changing '
                    'source evidence or unknown wording requires reviewing the changed exact inventory. '
                    'Neither matching digests nor complete quotations grant semantic qualification.',
                'relation_traversal_mapping': 'For source-reported object relations, explicitly declare purpose=traverse '
                    'in intended_uses and the knowledge use_contract, selecting complete relation roots. The matching '
                    'LocalUseAssessment.statement_review uses boi/source-relation-review@1 and the full original '
                    'unresolved inventory. boi/source-statement-review@1 remains filter-only; grants do not transfer '
                    'between purposes. Reconcile multiple purposes in one fresh assessment for the same target, '
                    'preserving prior opinions separately. Pin reviewed existing target revisions in required native '
                    'dependencies and assessment inputs. Current target type/identity, source rights, server checks '
                    'and purpose-specific qualification are still required. The host selects exact predicates from '
                    'the connected boi_knowledge_query schema/Profile and calls traverse; no alias, inverse, adjacency, '
                    'causal or world-condition inference is granted.',
                'assessment_mapping': 'Supply LocalKnowledgeAssessment opinions without target_byte_digest and '
                    'input_objects; the assembler derives those from exact output bytes. No labels are generated. '
                    'Assembly reports missing declared-use reviews and exact external revision declarations in '
                    'use_preparation, preserving the draft. Pack rechecks the actual bytes and refuses missing '
                    'review closure. Complete negative opinions remain valid inputs to server qualification; '
                    'reviews_present never means usable. Filter/traverse require their own source inventory review.',
                'local_only': True}
            with args.output.open('x', encoding='utf-8') as handle:
                args.output.chmod(0o600)
                json.dump(value, handle, ensure_ascii=False, indent=2)
            result = {'output': str(args.output), 'schema_models': 5, 'semantic_interpretation_performed': False}
        elif args.command == 'inspect':
            from dataclasses import asdict
            from boi_api.app.governed_runtime.spreadsheet_source_projection import workbook_fields
            from boi_api.app.governed_runtime.source_envelope import byte_digest
            raw = args.source.read_bytes()
            value = {'source_digest': byte_digest(raw), 'fields': [asdict(f) for f in workbook_fields(raw)],
                     'field_roles_assigned': False, 'semantic_interpretation_performed': False}
            with args.output.open('x', encoding='utf-8') as handle:
                args.output.chmod(0o600)
                json.dump(value, handle, ensure_ascii=False, indent=2)
            result = {'source_digest': value['source_digest'], 'fields': len(value['fields']),
                      'output': str(args.output), 'local_only': True}
        elif args.command == 'inventory':
            from agent_kit.python.boi_source_inventory import inventory_workbook, write_inventory_bundle
            layout = LocalJsonDocument(args.layout.read_bytes(), require_content=False).value
            result = write_inventory_bundle(inventory_workbook(args.source.read_bytes(), layout), args.output)
        elif args.command == 'assemble':
            from agent_kit.python.boi_local_knowledge_draft import assemble
            spec = LocalJsonDocument(args.spec.read_bytes(), require_content=False).value
            result = assemble(spec, output=args.output)
        elif args.command == 'review':
            from agent_kit.python.boi_local_review import render
            render(args.spec, args.bundle, args.output)
            result = {'output': str(args.output), 'local_only': True}
        elif args.command == 'pack':
            from agent_kit.python.boi_local_bundle_archive import pack_bundle
            result = pack_bundle(args.bundle, args.output)
        elif args.command.startswith('profile-'):
            from agent_kit.python.boi_profile_intake_host import (
                complete_profile_layout, complete_profile_route, execute_profile_question,
                prepare_profile_intake, prepare_profile_layout, prepare_profile_question,
                prepare_profile_question_recovery, render_profile_question,
                select_profile_candidates)
            def read(path):
                return LocalJsonDocument(path.read_bytes(), require_content=False).value
            def write(value):
                with args.output.open('x', encoding='utf-8') as handle:
                    args.output.chmod(0o600)
                    json.dump(value, handle, ensure_ascii=False, indent=2)
                return {'output': str(args.output), 'contract_version': value.get('contract_version'),
                        'release_authority_granted': value.get('release_authority_granted', False)}
            if args.command == 'profile-prepare':
                value=prepare_profile_intake(preserved_workbook_records=read(args.records),
                    profile_material=read(args.profile_material),source_scope=read(args.source_scope),
                    domain_guidance=read(args.domain_guidance) if args.domain_guidance else None,
                    maximum_selected=args.maximum_selected)
            elif args.command == 'profile-candidates':
                value=select_profile_candidates(preparation=read(args.preparation),
                    observation=read(args.observation))
            elif args.command == 'profile-route':
                value=complete_profile_route(candidate_stage=read(args.candidate_stage),
                    observation=read(args.observation))
            elif args.command == 'profile-layout-prepare':
                value=prepare_profile_layout(session=read(args.session))
            elif args.command == 'profile-layout-complete':
                value=complete_profile_layout(preparation=read(args.preparation),
                    observation=read(args.observation))
            elif args.command == 'profile-query-prepare':
                value=prepare_profile_question(session=read(args.session),question=args.question,
                    review=read(args.review) if args.review else None,
                    layout_review=read(args.layout_review) if args.layout_review else None)
            elif args.command == 'profile-query-execute':
                value=execute_profile_question(preparation=read(args.preparation),plan=read(args.plan))
            elif args.command == 'profile-query-recover':
                value=prepare_profile_question_recovery(preparation=read(args.preparation),
                    execution=read(args.execution))
            else:
                value=render_profile_question(preparation=read(args.preparation),
                    execution=read(args.execution),source_name=args.source_name)
            result=write(value)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError) as error:
        # Pydantic errors and filesystem exceptions can contain source values
        # or local paths. Show codes/field locations, never echo input payloads.
        pydantic = sys.modules.get('pydantic')
        if pydantic is not None and isinstance(error, pydantic.ValidationError):
            details = [{'field': list(e['loc']), 'error': e['type']}
                       for e in error.errors(include_input=False, include_url=False)]
            result = {'error': 'LOCAL_PREPARATION_CONTRACT_INVALID', 'fields': details}
        else:
            code = str(error)
            result = {'error': code if code and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in code)
                      else 'LOCAL_PREPARATION_FAILED', 'kind': type(error).__name__}
            if code == 'LOCAL_PREPARATION_INCOMPLETE' and hasattr(error, 'report'):
                result['use_preparation'] = error.report
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
