"""Small typed relation navigator inside the common source/knowledge view."""
from html import escape
from urllib.parse import urlencode


LABELS = {'broader':'상위 개념','narrower':'하위 개념','part_of':'구성 관계','precedes':'선행',
          'causes':'인과','requires':'필요 조건','supports':'뒷받침','contradicts':'반대 근거',
          'depends_on':'의존','in_collection':'목차 소속','related_to':'관련',
          'subject_identity':'주체','object_identity':'대상','condition':'조건','exception':'예외',
          'applicability':'적용 범위','counterevidence':'반대 근거','declared_dependency':'선언된 의존'}


def render_knowledge_graph(graph, url):
    nodes = graph['nodes']
    if not nodes:
        return ''
    names = {}
    items = []
    for node in nodes:
        value = node['value']
        label = value.get('label') or value.get('statement') or value.get('proposed_definition') or node['local_id'] or node['target_pointer']
        label = str(label)
        names[node['node_id']] = label
        if len(items) < 40:
            target = url + '?' + urlencode({'meaning':node['target_pointer']}) + '#evidence-group'
            items.append('<li><a href="'+escape(target, quote=True)+'">'+escape(label)+'</a></li>')
    rows = []
    for edge in graph['edges'][:80]:
        rows.append('<li>'+escape(names.get(edge['source'],edge['source']))+' → '
            +escape(LABELS.get(edge['type'],edge['type']))+' → '+escape(names.get(edge['target'],edge['target']))+'</li>')
    return ('<details data-knowledge-structure><summary>개념·주장과 관계 ('+str(len(nodes))+'개 의미)</summary>'
            '<p>목차, 개념 상하위, 구성, 공정 순서와 근거 관계를 구별합니다. 관계만으로 조건이나 검토 상태가 상속되지는 않습니다.</p>'
            +('<p>설명 맥락: '+escape(graph['context_layer'])+'</p>' if graph.get('context_layer') else '')
            +'<ul>'+''.join(items)+'</ul>'+('<ul>'+''.join(rows)+'</ul>' if rows else '')
            +('<p>화면에는 의미 40개와 관계 80개까지 표시합니다. 전체 연결은 같은 개정의 MCP graph 읽기에서 확인할 수 있습니다.</p>' if len(nodes)>40 or len(graph['edges'])>80 else '')
            +'</details>')
