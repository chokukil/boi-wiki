"""Request-local source reads with one current authority fence per artifact.

Sharing a document does not share its sources. Only already authorized exact
bindings are joined; no search, semantic selection or persistent cache is used.
"""
from .knowledge_source_access import KnowledgeSourceAccess
from .ledger import RecordKind, record_digest
from .source_envelope import byte_digest
from .citation_material_cards import material_source_cards


class PublishedSourceFields:
    def __init__(self, reader, *, actor_id, revision, access, native, content, model_input):
        self.reader, self.actor_id, self.revision = reader, actor_id, revision
        self.access, self.native, self.content = access, native, content
        self.model_input = model_input
        self.rights = KnowledgeSourceAccess(reader.spaces, current_authorization=reader.current_authorization)
        self.sources, self.fields = {}, {}

    def read(self, index):
        if index >= len(self.content.evidence_bindings):
            raise ValueError('KNOWLEDGE_SOURCE_BINDING_UNAVAILABLE')
        binding = self.content.evidence_bindings[index]
        span = self.reader.intake.ledger.read(binding.span.ref)
        value = span.payload
        if (span.kind != RecordKind.EVIDENCE_SPAN or span.authority != 'evidence_service'
                or record_digest(span.record_id) != binding.span.revision_digest
                or value.get('contract_version') not in ('boi/source-field-projection@1', 'boi/source-image-transcription@1')
                or value.get('source_revision_digest') != binding.source_revision_digest
                or value.get('field_locator') != binding.field_locator):
            raise ValueError('KNOWLEDGE_SOURCE_FIELD_BINDING_CHANGED')
        source = next((s for s in self.native.payload['sources']
            if s['artifact_ref'] == value['artifact_ref'] and s['digest'] == binding.source_revision_digest), None)
        if source is None:
            raise ValueError('KNOWLEDGE_SOURCE_BINDING_UNAVAILABLE')
        key = source['artifact_ref']
        if key not in self.sources:
            _, before = self.rights.read(actor_id=self.actor_id, source=source,
                model_input=self.model_input, cite=not self.model_input)
            artifact = self.reader.intake.ledger.read(key)
            self.sources[key] = (source, before, artifact)
        saved_source, before, artifact = self.sources[key]
        if (saved_source != source or value.get('rights_record_ref') != before['rights_ref']
                or value.get('employee_id') != artifact.payload['owner']
                or value.get('policy_digest') != artifact.payload['policy_digest']):
            raise ValueError('KNOWLEDGE_SOURCE_FIELD_RIGHTS_CHANGED')
        field_key = (value['field_object_ref'], value['content_digest'])
        if field_key not in self.fields:
            raw = self.reader.intake.objects.get(value['field_object_ref'])
            if byte_digest(raw) != value['content_digest']:
                raise ValueError('KNOWLEDGE_SOURCE_FIELD_BYTES_CHANGED')
            self.fields[field_key] = raw.decode('utf-8')
        text = self.fields[field_key]
        if len(text) != value['character_count']:
            raise ValueError('KNOWLEDGE_SOURCE_FIELD_BYTES_CHANGED')
        start = -1
        for _ in range(binding.quote_occurrence + 1):
            start = text.find(binding.quote, start + 1)
            if start < 0:
                raise ValueError('KNOWLEDGE_SOURCE_QUOTE_NOT_FOUND')
        return binding, value, text, start

    def display_name(self, artifact):
        return self.reader.intake.source_display_name(artifact)

    def fence(self):
        for source, before, _ in self.sources.values():
            _, after = self.rights.read(actor_id=self.actor_id, source=source,
                model_input=self.model_input, cite=not self.model_input)
            if before != after:
                raise ValueError('KNOWLEDGE_SOURCE_AUTHORITY_CHANGED')
        self.reader._fence(self.actor_id, self.revision, self.access)

    def bundle(self, indices, *, url):
        fields, characters = {}, 0
        for index in indices:
            binding, value, text, start = self.read(index)
            key = (binding.source_revision_digest, binding.span.ref)
            if key not in fields:
                characters += len(text)
                if len(fields) >= 32 or characters > 65536:
                    raise ValueError('KNOWLEDGE_SOURCE_BUNDLE_LIMIT_REQUIRES_NARROWER_SELECTION')
                # This envelope was checked by read(), not recovered from a title or URL.
                source = self.sources[value['artifact_ref']][0]
                display_name=self.display_name(self.sources[value['artifact_ref']][2])
                fields[key] = {'source': dict(source), 'source_revision_digest': binding.source_revision_digest,
                    **({'source_display_name':display_name} if display_name else {}),
                    'span': binding.span.model_dump(mode='json'), 'field_locator': binding.field_locator,
                    'field_digest': value['content_digest'], 'text': text,
                    'complete_field': True, 'character_count': len(text),
                    'field_metadata': {k:value[k] for k in ('representation', 'field_state', 'value_kind',
                        'presence_basis', 'structural_metadata', 'parser_digest') if k in value},
                    'bindings': []}
            fields[key]['bindings'].append({'binding_index': index,
                'meaning_pointer': binding.meaning_pointer, 'quote': binding.quote,
                'quote_start': start, 'quote_end': start + len(binding.quote),
                'transformations': [r.model_dump(mode='json') for r in binding.transformations],
                'source_url': url + '/sources/' + str(index)})
        source_cards = material_source_cards([
            {'source': field['source'], 'knowledge_revision': self.revision.model_dump(mode='json'),
             'field_index': fi, 'binding_index': binding['binding_index'],
             'meaning_pointer': binding['meaning_pointer'], 'span': field['span'],
             'field_locator': field['field_locator'], 'field_digest': field['field_digest'],
             'quote_start': binding['quote_start'], 'quote_end': binding['quote_end'],
             'citation_url': binding['source_url'], 'evidence_role': 'source_quote'}
            for fi, field in enumerate(fields.values()) for binding in field['bindings']])
        numbers={ref['binding_index']:card['number'] for card in source_cards for ref in card['references']}
        for field in fields.values():
            for binding in field['bindings']:binding['display_number']=numbers[binding['binding_index']]
        return {'contract_version': 'boi/published-source-bundle@1', 'fields': list(fields.values()),
            'source_cards': source_cards,
            'selection_coverage': 'selected_meaning_and_declared_dependencies',
            'absence_proven': False, 'semantic_truth_proven': False,
            'access_checked_for': 'model_input' if self.model_input else 'cite',
            'reuse_requires_current_authority': True,
            'offset_basis': 'decoded_unicode_codepoints',
            'delivered_field_count': len(fields), 'delivered_characters': characters}
