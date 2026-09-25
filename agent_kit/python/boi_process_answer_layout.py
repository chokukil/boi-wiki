"""Small reviewed layout over existing cited statements; no added prose."""
from typing import Annotated, Literal
from pydantic import Field
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract, Ref

StatementPointer = Annotated[str, Field(pattern=r'^/(sentences|limitations)/(0|[1-9][0-9]*)$')]


class Paragraph(FrozenContract):
    kind: Literal['paragraph'] = 'paragraph'
    statements: tuple[StatementPointer, ...] = Field(min_length=1)


class BulletList(FrozenContract):
    kind: Literal['list'] = 'list'
    items: tuple[StatementPointer, ...] = Field(min_length=1)


class ComparisonTable(FrozenContract):
    kind: Literal['table'] = 'table'
    headers: tuple[Ref, ...] = Field(min_length=2, max_length=6)
    row_labels: tuple[Ref,...] | None = Field(default=None,exclude_if=lambda v:v is None,
        description='Optional row headings such as the compared aspect. One per row. These headings are visible and reviewed contextual text, not evidence or substitutes for cited content cells. Do not include a row-label column in headers or rows.')
    rows: tuple[tuple[StatementPointer, ...], ...] = Field(min_length=1,description='Each cell points to ONE entire cited text entry, not a substring extracted from a longer sentence. Short labels or phrases are welcome; do not force full sentences into row labels. Write separate entries for separate cells. Never repeat a pointer in another cell or paragraph. Each row has exactly len(headers) cells.')


AnswerLayout = tuple[Annotated[Paragraph | BulletList | ComparisonTable, Field(discriminator='kind')], ...]


def layout_errors(layout, sentences, limitations):
    """Exact structural locations for correction; no prose/meaning repair."""
    errors=[];occurrences={}
    for bi,block in enumerate(layout):
        path=f'/layout/{bi}'
        if block.kind=='table':
            if block.row_labels is not None and len(block.row_labels)!=len(block.rows):
                errors.append({'reason_code':'ANSWER_LAYOUT_ROW_LABEL_COUNT_MISMATCH',
                    'location':path+'/row_labels','expected_count':len(block.rows),'actual_count':len(block.row_labels)})
            for ri,row in enumerate(block.rows):
                if len(row)!=len(block.headers):
                    errors.append({'reason_code':'ANSWER_LAYOUT_TABLE_WIDTH_MISMATCH',
                        'location':f'{path}/rows/{ri}','expected_count':len(block.headers),'actual_count':len(row)})
                for ci,p in enumerate(row):occurrences.setdefault(p,[]).append(f'{path}/rows/{ri}/{ci}')
        else:
            field='statements' if block.kind=='paragraph' else 'items'
            for i,p in enumerate(getattr(block,field)):occurrences.setdefault(p,[]).append(f'{path}/{field}/{i}')
    expected=[f'/{section}/{i}' for section,items in [('sentences',sentences),('limitations',limitations)] for i in range(len(items))]
    missing=[p for p in expected if p not in occurrences]
    duplicates=[{'statement_pointer':p,'locations':locs} for p,locs in occurrences.items() if len(locs)>1]
    unknown=[{'statement_pointer':p,'locations':locs} for p,locs in occurrences.items() if p not in set(expected)]
    if missing or duplicates or unknown:
        errors.append({'reason_code':'ANSWER_LAYOUT_MUST_INCLUDE_EACH_STATEMENT_ONCE',
            'missing':missing,'duplicates':duplicates,'unknown':unknown})
    return errors


def validate_layout(layout, sentences, limitations):
    """Every visible statement occurs once; each cell retains its citations."""
    errors=layout_errors(layout,sentences,limitations)
    if errors:raise ValueError(errors[0]['reason_code'])


def proposal_layout_errors(proposal):
    from .boi_process_user_result import SourceExplanation
    return [{'answer_index':ai,**error}
        for ai,answer in enumerate(SourceExplanation.model_validate(proposal).answers)
        if answer.layout is not None
        for error in layout_errors(answer.layout,answer.sentences,answer.limitations)]


def rejected_layout(proposal):
    """A malformed layout stops binding before any model review can start."""
    errors=proposal_layout_errors(proposal)
    return errors[0]['reason_code'] if errors else None


def render_layout(layout, resolve, *, html=False, escape=lambda s:s):
    """Resolve text and citations verbatim. Only structural markup is inserted."""
    blocks=[]
    for block in layout:
        if block['kind']=='paragraph':
            text=' '.join(resolve(p) for p in block['statements'])
            blocks.append('<p>'+text+'</p>' if html else text)
        elif block['kind']=='list':
            items=[resolve(p) for p in block['items']]
            blocks.append('<ul>'+''.join('<li>'+v+'</li>' for v in items)+'</ul>' if html else '\n'.join('- '+v for v in items))
        else:
            headers=[escape(h) for h in block['headers']]
            rows=[[resolve(p) for p in row] for row in block['rows']]
            labels=[escape(v) for v in block['row_labels']] if block.get('row_labels') is not None else None
            if html:
                blocks.append(render_table(headers,rows,labels=labels))
            else:
                if labels is not None:
                    headers=['항목',*headers];rows=[[labels[i],*row] for i,row in enumerate(rows)]
                cell=lambda s:s.replace('|','\\|').replace('\n','<br>')
                blocks.append('\n'.join('| '+' | '.join(cell(v) for v in row)+' |' for row in [headers,['---']*len(headers),*rows]))
    return ('\n' if html else '\n\n').join(blocks)


def render_table(headers,rows,*,labels=None):
    """Shared presentation for already escaped/sanitized cells and headers."""
    return ('<div class="table-scroll" role="region" aria-label="비교표"><table role="table"><thead role="rowgroup"><tr role="row">'+('<th scope="col" role="columnheader">항목</th>' if labels is not None else '')+''.join('<th scope="col" role="columnheader">'+h+'</th>' for h in headers)+
                    '</tr></thead><tbody role="rowgroup">'+''.join('<tr role="row">'+('<th scope="row" role="rowheader">'+labels[ri]+'</th>' if labels is not None else '')+''.join(
                        '<td role="cell"><span class="mobile-column-label" aria-hidden="true">'+headers[i]+'</span><div class="table-value">'+v+'</div></td>'
                        for i,v in enumerate(row))+'</tr>' for ri,row in enumerate(rows))+'</tbody></table></div>')


RESPONSIVE_TABLE_CSS = '.mobile-column-label{display:none}.table-value{overflow-wrap:anywhere}@media(max-width:600px){\n.table-scroll{overflow:visible}.table-scroll table,.table-scroll tbody{display:block;width:100%}\n.table-scroll thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}\n.table-scroll tr{display:block;border:1px solid #bdcdd7;border-radius:8px;margin:0 0 14px;overflow:hidden}\n.table-scroll td{display:grid;grid-template-columns:minmax(4.5rem,28%) minmax(0,1fr);gap:10px;border:0;border-bottom:1px solid #e0e7eb;padding:10px}\n.table-scroll td:last-child{border-bottom:0}.table-scroll td:first-child{min-width:0;background:#f0f5f8}\n.mobile-column-label{display:block;font-weight:600;font-size:14px;color:#385061;overflow-wrap:anywhere}}'
