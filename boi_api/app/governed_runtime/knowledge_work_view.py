"""Progressive external delivery of the same protected work/context revision.

Full contexts remain immutable inputs to their existing consumers. Reference
views are explicitly a different projection and must not be hashed as a context.
"""
from .semantic_binding_contract import RevisionRef


def project_work_response(value, *, authorize_revision=None, full=False):
    checked = {}

    def allowed(ref):
        key = ref['ref']
        if key not in checked:
            try:
                if authorize_revision is not None:
                    authorize_revision(RevisionRef.model_validate(ref))
                checked[key] = True
            except ValueError:
                if full:
                    raise
                checked[key] = False
        return checked[key]

    def visit(work):
        result = dict(work)
        if 'items' in result and 'task_ref' not in result:
            result['items'] = [visit(item) for item in result['items']]
        for key in ('active_attempt', 'previous_attempt'):
            if isinstance(result.get(key), dict):
                result[key] = attempt_view(result[key], work['task_ref'])
        return result

    def attempt_view(attempt, task_ref):
        result = dict(attempt)
        context = attempt.get('interpretation_context')
        read = {'tool': 'boi_knowledge_work', 'arguments': {'operation': 'status',
                'request': {'task_ref': task_ref}, 'context_view': 'full'}}
        if context is not None:
            roots = {s['requirement']['revision']['ref'] for s in context['selections'] if s['parent'] is None}
            if full:
                for asset in context['assets']:
                    allowed(asset['revision'])
            else:
                root_assets = [a for a in context['assets'] if a['revision']['ref'] in roots]
                visible = [a for a in root_assets if allowed(a['revision'])]
                result['interpretation_context'] = {
                    'contract_version': 'boi/task-knowledge-reference-view@1',
                    'protected_context_digest': context['context_digest'],
                    'asset_count': len(context['assets']), 'returned_asset_count': len(visible),
                    'restricted_root_count': len(root_assets) - len(visible),
                    'assets': [{**{k: asset[k] for k in ('revision','kind','content_digest','authority')},
                               'read': {'tool': 'boi_knowledge_read', 'arguments': {'revision': asset['revision'], 'view': 'asset'}}}
                              for asset in visible],
                    'recorded_dependency_completeness': context['dependency_completeness'],
                    'full_context_read': read,
                    'scope': 'Root references of the protected context; content and transitive dependencies are available through exact reads. This projection is not a TaskKnowledgeContext or semantic-selection verdict. Use full_context_read only when the chosen consumer requires the complete bound context.'}
        if 'existing_knowledge' in attempt:
            catalog = attempt['existing_knowledge']
            visible = [item for item in catalog['items'] if allowed(item['revision'])]
            if not full:
                result['existing_knowledge'] = {**{k:v for k,v in catalog.items() if k != 'items'},
                    'items': [{**{k:item[k] for k in ('revision','logical_id','namespace','kind','title','description','content_contract') if k in item},
                        'read': {'tool':'boi_knowledge_read','arguments':{'revision':item['revision'],'view':'meaning_index'}}}
                        for item in visible],
                    'current_restricted_count': len(catalog['items']) - len(visible),
                    'scope': 'Recorded discovery candidates reauthorized now; select using their meanings and the current source, then add exact revisions through context before context-bound authoring. Run catalog for newly relevant knowledge.'}
        return result

    return visit(value)
