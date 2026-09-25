"""Presentation over already authorized source bindings; no new read or judgment."""
import copy
from agent_kit.python.boi_recipient_citations import recipient_access, access_notice


def with_published_citations(document, *, recipient_check=None):
    bundle=document.get('source_bundle')
    if not isinstance(bundle,dict) or not bundle.get('fields'):
        return document
    fields=[];references=[]
    source_cards=bundle.get('source_cards',[])

    def material_number(binding):
        exact={card.get('number') for card in source_cards
            for reference in card.get('references',[])
            if reference.get('binding_index')==binding.get('binding_index')
            and reference.get('citation_url')==binding.get('source_url')
            and card.get('number') is not None}
        explicit=binding.get('display_number')
        if explicit is not None:
            return explicit if not exact or exact=={explicit} else None
        return next(iter(exact)) if len(exact)==1 else None
    for index,field in enumerate(bundle['fields']):
        meta=field.get('field_metadata',{}).get('structural_metadata',{})
        location=' '.join(str(meta[k]) for k in ('sheet','cell') if meta.get(k))
        fields.append({'field_index':index,'location_label':location or field['field_locator'],
            'field_locator':field['field_locator'],'source_revision_digest':field['source_revision_digest'],
            'span':copy.deepcopy(field['span']),'field_digest':field['field_digest']})
        for binding in field.get('bindings',[]):
            number=material_number(binding)
            references.append({'label':str(number) if number is not None else '원문','field_index':index,
                **({'material_number':number} if number is not None else {}),
                'binding_index':binding['binding_index'],'meaning_pointer':binding['meaning_pointer'],
                'url':binding['source_url'],'quote_start':binding['quote_start'],'quote_end':binding['quote_end']})
    access=recipient_access([r['url'] for r in references],check=recipient_check)
    for reference in references:
        reference['recipient_access']=copy.deepcopy(access[reference['url']])
        reference['source_label']=reference['label']
        reference['label']=reference['source_label']+' · '+access[reference['url']]['label']
        reference['display_label']=reference['label']
    return {**document,'citation_presentation':{
        'contract_version':'boi/published-citation-presentation@1',
        'documents':[{'title':document['title'],'revision':copy.deepcopy(document.get('revision')),
            'fields':fields}],
        'source_cards':copy.deepcopy(source_cards),
        'recipient_citation_access':access,'recipient_access_notice':access_notice(access).strip(),
        'references':references,'label_scope':'this_document_response_only',
        'guidance':('Explain the answer first. Cite the exact references supporting each statement. '
            'Use display_label, including each recipient access status, for links; preserve recipient_access_notice in the final answer. '
            'Caller access and public visibility never prove recipient access. Do not suppress supported answer text '
            'because a source link is denied or unverified; limit the source-opening claim only. '
            'Use short numbered links and name the document and source location once nearby, '
            'instead of repeating a generic source label or a long URL. A shared paragraph-end citation '
            'is sufficient only when its exact evidence supports every claim in that paragraph. '
            'Different bindings, source fields and revisions are not interchangeable. Retain claim-to-reference '
            'correspondence; these numbers are display labels, not semantic approval. When combining document '
            'responses, use typed API composition for response-wide labels; do not relabel bare numbers in prose.'),
        'user_link_access':'not_observed','semantic_support_verified':False}}
