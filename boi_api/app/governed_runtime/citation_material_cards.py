"""Material cards over an already-authorized, request-local evidence projection.

This module performs no reads or authorization. Callers must supply only current
authorized identities and evidence. Cards neither grant recipient access nor
merge the meaning, knowledge revisions, or permissions of their references.
"""
import copy


def material_identity(source):
    """Never substitute a title, URL, digest alone, or display label for identity."""
    if not isinstance(source, dict):
        return None
    values = tuple(source.get(key) for key in ("artifact_ref", "role", "digest"))
    return values if all(isinstance(value, str) and value for value in values) else None


def material_source_cards(references):
    """Group trusted material identity; retain every evidence occurrence in order.

    Missing identity remains ungrouped in the caller's original evidence; no
    identity or citation is fabricated. Numbers are card labels, not replacements
    for the caller's exact evidence links or semantic citation roles.
    """
    cards, by_identity = [], {}
    for reference in references:
        source = reference.get("source")
        identity = material_identity(source)
        if identity is None:
            continue
        if identity not in by_identity:
            card = {"number": len(cards) + 1,
                "source": dict(zip(("artifact_ref", "role", "digest"), identity)),
                "references": []}
            cards.append(card)
            by_identity[identity] = card
        by_identity[identity]["references"].append(copy.deepcopy(
            {key: value for key, value in reference.items() if key != "source"}))
    return cards


def bound_source_identity(sources, digest, span_ref=None, field_locator=None):
    """Resolve only an unambiguous envelope in the supplied authorized readings."""
    matches = {}
    for reading in sources:
        source = reading.get("source")
        identity = material_identity(source)
        if identity is None or source["digest"] != digest:
            continue
        if span_ref is not None or field_locator is not None:
            if not any((span_ref is None or field.get("span_ref") == span_ref)
                    and (field_locator is None or field.get("field_locator") == field_locator)
                    for field in reading.get("fields", [])):
                continue
        matches[identity] = source
    return copy.deepcopy(next(iter(matches.values()))) if len(matches) == 1 else None


def composition_source_cards(answer, displayed_citations, sources):
    """Keep typed statement/evidence links alongside existing displayed citations."""
    from .semantic_binding_contract import semantic_digest
    references = []
    for section in ("sentences", "limitations"):
        for index, statement in enumerate(answer[section]):
            pointer = f"/{section}/{index}"
            displayed = [i for i, citation in enumerate(displayed_citations)
                if citation["statement_pointer"] == pointer]
            for ci, citation in enumerate(statement["citations"]):
                common = {"statement_pointer": pointer,
                    "evidence_pointer": pointer + f"/citations/{ci}",
                    "statement_citation_indices": [],
                    "evidence_role": citation["kind"]}
                # Preserve the semantic reference and knowledge revision separately.
                semantic = {key: citation[key] for key in ("kind", "asset_revision",
                    "target_pointer", "source_revision_digest", "reading_digest") if key in citation}
                for bi, binding in enumerate(citation.get("source_bindings", [])):
                    source = bound_source_identity(sources, binding["source_revision_digest"],
                        binding.get("span_ref"), binding.get("field_locator"))
                    references.append({**common, "source": source,
                        "binding_pointer": common["evidence_pointer"] + f"/source_bindings/{bi}",
                        "binding": binding, "citation_reference": semantic,
                        "statement_citation_indices":[i for i in displayed if semantic_digest({"citation":semantic_digest(citation),"binding":semantic_digest(binding)}) in
                            displayed_citations[i].get("evidence_binding_keys",[])]})
                if citation["kind"] == "source_scope":
                    references.append({**common,
                        "source": bound_source_identity(sources, citation["source_revision_digest"]),
                        "citation_reference": semantic,
                        "statement_citation_indices":[i for i in displayed if semantic_digest(citation) in
                            displayed_citations[i].get("scope_reference_keys",[])]})
    cards=material_source_cards(references)
    for card in cards:card['target_mapping']='typed_evidence@1'
    return cards


def material_display_groups(cards, reference_count, *, index_key='citation_index'):
    """Consume API card labels without changing protected evidence addresses.

    Legacy/missing identities remain separate unlabelled-identity groups. They
    never acquire another card's identity, title or authority by URL equality.
    """
    groups=[];used=set()
    for card in cards:
        indices=list(dict.fromkeys(ref[index_key] for ref in card['references']
            if index_key in ref and 0 <= ref[index_key] < reference_count))
        if not indices:continue
        if used.intersection(indices):raise ValueError('MATERIAL_DISPLAY_REFERENCE_AMBIGUOUS')
        used.update(indices)
        groups.append({**copy.deepcopy(card),'reference_indices':indices})
    number=max((card['number'] for card in cards),default=0)
    for index in range(reference_count):
        if index in used:continue
        number+=1
        groups.append({'number':number,'source':None,'references':[], 'reference_indices':[index]})
    return groups
