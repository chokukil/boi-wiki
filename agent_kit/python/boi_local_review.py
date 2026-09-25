"""Render an offline, read-only review of a digest-bound locally authored bundle.

No network requests, publication controls, model calls or invented semantic
scores. The source column and the authored body stay separate in the UI.
"""
import argparse
import json
from pathlib import Path

from .boi_local_knowledge_draft import load_authoring_inventory,authoring_context_roles,verify_authoring_fields
from boi_api.app.governed_runtime.local_bundle_contract import LocalBundleManifest
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from boi_api.app.governed_runtime.source_envelope import byte_digest


PAGE = r'''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>지식 자료 · 로컬 검토</title><style>
:root{font:16px/1.7 system-ui,sans-serif;color:#1a343c;background:#f3f6f7}*{box-sizing:border-box}
body{margin:0}header{padding:32px max(22px,calc((100vw - 1400px)/2));background:#163d45;color:white}
h1{font-size:30px;line-height:1.4;margin:8px 0}h2{font-size:25px;margin:0}h3{font-size:17px;margin:0 0 10px}
p{margin:8px 0}.eyebrow{letter-spacing:.08em;font-size:13px}.summary{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}
.badge{background:#ffffff1c;padding:6px 12px;border-radius:8px}.layout{display:grid;grid-template-columns:280px minmax(0,1fr);max-width:1440px;margin:auto;padding:24px;gap:24px}
aside{align-self:start;position:sticky;top:20px}input,button{font:inherit}input{width:100%;border:1px solid #b9ced2;padding:10px;border-radius:8px}
button{cursor:pointer;border:1px solid #c4d5d9;border-radius:8px;padding:10px;background:white;color:inherit;text-align:left}
.navigation{display:grid;gap:6px;margin-top:14px;max-height:calc(100vh - 380px);min-height:150px;overflow:auto}.navigation button[aria-current=true]{background:#e0eff0;border-color:#2b7379;font-weight:700}
.navigation button{min-width:0;overflow-wrap:anywhere}
main{min-width:0}.card{background:white;border:1px solid #d7e2e5;border-radius:12px;padding:24px;margin-bottom:18px;overflow-wrap:anywhere}
.muted{color:#52686f;font-size:14px}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.tabs button[aria-selected=true]{background:#205d65;color:white;border-color:#205d65}
.comparison{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.prose{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.85 system-ui,sans-serif}
.claim{border-top:1px solid #dce5e7;padding:18px 0}.claim:first-child{border-top:0}.tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}.tag{font-size:12px;background:#eaf2f3;padding:2px 8px;border-radius:5px}
.tag[data-polarity=negative]{background:#fff0d6;color:#71480e;font-weight:700}
details{margin:10px 0}summary{cursor:pointer;color:#245d67}code{font-size:12px;overflow-wrap:anywhere}blockquote{margin:10px 0;padding:10px 14px;border-left:3px solid #a1bfc4;white-space:pre-wrap;background:#f5f8f9;overflow-wrap:anywhere}
.notice{background:#fff8e9;border:1px solid #e7d8b0;border-radius:8px;padding:14px}.empty{padding:20px;color:#52686f}[hidden]{display:none!important}
@media(max-width:850px){.layout{display:block;padding:16px}aside{position:static;margin-bottom:18px}.navigation{max-height:190px}.comparison{grid-template-columns:1fr}.card{padding:18px}h1{font-size:25px}header{padding:24px 20px}}
</style><header><div class="eyebrow">BOI WIKI · 자료 검토</div><h1>원문에서 지식으로</h1>
<p>정리한 설명과 근거를 함께 살펴봅니다. 이 파일은 로컬 초안이며 Wiki에 게시되지 않았습니다.</p><div id="summary" class="summary"></div></header>
<div class="layout"><aside><label for="search">자료 찾기</label><input id="search" placeholder="자료 이름 검색" autocomplete="off"><nav id="navigation" class="navigation" aria-label="자료 목록"></nav></aside>
<main><section id="profile-change" class="card" hidden></section><section class="card"><h2 id="title"></h2><p id="description"></p><p id="locator" class="muted"></p>
<div class="tabs" role="tablist" aria-label="자료 보기"><button role="tab" data-tab="body">정리한 설명</button><button role="tab" data-tab="relations">연결된 지식</button><button role="tab" data-tab="compare">원문과 대조</button><button role="tab" data-tab="claims">주장과 근거</button><button role="tab" data-tab="limits">확인할 부분</button></div>
<div id="body" class="panel prose"></div><div id="compare" class="panel comparison" hidden><div><h3>제공된 셀 원문</h3><div id="source" class="prose"></div><div id="source-context"></div></div><div><h3>정리한 본문</h3><div id="authored" class="prose"></div></div></div>
<div id="relations" class="panel" hidden></div><div id="claims" class="panel" hidden></div><div id="limits" class="panel" hidden></div></section>
<section class="card"><h3>현재 준비 상태</h3><p>형식·타입·참조 위치·원문 인용 검사는 로컬에서 통과했습니다. 서버 검사, 현재 영향 확인, 사용자의 한 번 확인, 실제 게시가 남아 있습니다.</p>
<p class="muted">원문을 본문에 보존했다고 모든 의미가 구조화된 것은 아닙니다. 출처를 대조한 작성자의 의견과 독립적인 사실 검증도 구분합니다.</p>
<details><summary>묶음 식별 정보</summary><code id="digest"></code></details></section></main></div>
<script id="data" type="application/json">__DATA__</script><script>
'use strict';const data=JSON.parse(document.getElementById('data').textContent);
const byId=new Map(data.records.map(r=>[r.object_id,r]));let selected=data.records[0].object_id,tab='body';
const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
const summary=document.getElementById('summary');for(const text of [`다룬 원천 ${data.selected_source_records}개 / 전체 ${data.source_records}개`,`지식 ${data.records.length}개`,`구조화한 주장 ${data.records.reduce((n,r)=>n+r.assertions.length,0)}개`,'로컬 초안 · 미게시'])summary.append(el('span',text,'badge'));
document.getElementById('digest').textContent=data.manifest_digest;
if(data.profile_change){const p=data.profile_change,card=document.getElementById('profile-change');card.hidden=false;
 card.append(el('h3','자료 정리 기준 개정: '+p.title),el('p',p.correction.reason),el('p','기존 기준과의 차이: '+p.correction.source_difference),el('p','새 자료는 개정한 기준을 사용합니다. 이미 게시된 지식의 해석과 참조는 유지합니다. 현재 영향·권한·동시 수정은 서버에서 확인해야 합니다.','notice'));
 const details=el('details');details.append(el('summary','제안한 구성 항목과 기준 개정 보기'));for(const c of data.profile_components)details.append(el('p',c.label+(c.description?' · '+c.description:'')));details.append(el('code',p.previous_revision.ref));card.append(details);}
function navigation(){const nav=document.getElementById('navigation'),previousScroll=nav.scrollTop;nav.replaceChildren();const term=document.getElementById('search').value.trim().toLocaleLowerCase();
 for(const r of data.records){if(term&&!r.title.toLocaleLowerCase().includes(term))continue;const b=el('button',r.title);b.setAttribute('aria-current',String(r.object_id===selected));b.onclick=()=>{selected=r.object_id;render();};nav.append(b);}if(!nav.children.length)nav.append(el('div','이름이 일치하는 자료가 없습니다.','empty'));
 nav.scrollTop=previousScroll;const active=nav.querySelector('[aria-current=true]');if(active){const a=active.getBoundingClientRect(),n=nav.getBoundingClientRect();if(a.top<n.top)nav.scrollTop-=n.top-a.top;else if(a.bottom>n.bottom)nav.scrollTop+=a.bottom-n.bottom;}}
function render(){const r=byId.get(selected);navigation();document.getElementById('title').textContent=r.title;document.getElementById('description').textContent=r.description;
 const location=r.source_fields[0]?.structural_metadata;document.getElementById('locator').textContent=`원천: ${location?.sheet&&location?.excel_row?location.sheet+' · '+location.excel_row+'행':r.source_record_locator} · ${r.assertions.length}개 주장`;
 document.getElementById('body').textContent=r.body;document.getElementById('authored').textContent=r.body;
 const source=document.getElementById('source');source.replaceChildren();for(const s of r.source_fields){const field=el('article',undefined,'claim');field.dataset.sourceField=s.field_locator;field.append(el('h3',s.structural_metadata?.cell||s.field_locator),el('div',s.text,'prose'));source.append(field);}
 const context=document.getElementById('source-context');context.replaceChildren();for(const [role,label] of [['review_note','제공된 보완 기록'],['source','함께 확인한 원천'],['metadata','헤더·설명']]){const selectedContexts=r.context_fields?.map((c,i)=>({c,s:r.context_source_fields[i]})).filter(v=>v.c.role===role)||[];if(!selectedContexts.length)continue;const details=el('details');details.append(el('summary',label+' · '+selectedContexts.length+'개 셀'));if(role==='review_note')details.append(el('p','제공된 기록의 추정이나 교정이 사실로 검증되었다는 뜻은 아닙니다.','muted'));for(const {s,c} of selectedContexts){const article=el('article',undefined,'claim');article.dataset.contextLocator=s.field_locator;article.append(el('p',c.field_locator,'muted'),el('p',c.reason,'muted'),el('blockquote',s.text,'prose'));details.append(article);}context.append(details);}
 const list=document.getElementById('claims'),relations=document.getElementById('relations');list.replaceChildren();relations.replaceChildren(el('p','이 자료에서 명시한 관계입니다. 이름이 같다는 이유로 다른 자료나 실제 대상을 동일시하지 않습니다.','muted'));let relationCount=0;
 for(const n of r.assertions){const c=el('article',undefined,'claim'),tags=el('div',undefined,'tags');
  c.dataset.assertionId=n.id;
  for(const text of [data.predicate_labels[n.predicate_id]||n.predicate_id,({asserted:'원천 보고',intended:'목적',possible:'가능성',required:'요구사항'})[n.modality]||n.modality])tags.append(el('span',text,'tag'));
  const polarity=el('span',n.polarity==='negative'?'부정 주장':'긍정 주장','tag');polarity.dataset.polarity=n.polarity;tags.append(polarity);
  c.append(tags,el('p',n.statement));for(const [key,label] of [['conditions','조건'],['exceptions','예외'],['applicability','적용 범위']])for(const clause of n[key]){const p=el('p',label+': '+clause.statement,'muted');p.dataset.qualifier=key;c.append(p);}
  for(const id of n.depends_on){const linked=r.assertions.find(v=>v.id===id);c.append(el('p','함께 읽을 주장: '+(linked?linked.statement:'연결된 주장을 확인할 수 없음'),'muted'));}
  const details=el('details');details.append(el('summary','원문 근거 보기'));for(const q of n.evidence){details.append(el('p',q.field_locator,'muted'),el('blockquote',q.quote));}c.append(details);
  for(const limit of n.uncertainties)c.append(el('p',limit,'muted'));
  if(n.value.kind==='object'){const target=byId.get(n.value.target_object_id);const row=c.cloneNode(true);if(target){const open=el('button',target.title+' 열기');open.dataset.targetObject=target.object_id;open.onclick=()=>{selected=target.object_id;tab='body';document.getElementById('search').value='';render();};row.append(open);}else row.append(el('p','연결 대상은 이 묶음에 없습니다.','notice'));relations.append(row);relationCount++;}
  list.append(c);}if(!relationCount)relations.append(el('p','명시해 정리한 연결이 아직 없습니다. 원문에 관계가 없다는 뜻은 아닙니다.','empty'));
 for(const p of r.parameters||[]){const card=el('article',undefined,'claim');card.dataset.formulaParameter=p.id;const s=p.semantic_descriptor;card.append(el('h3',p.parameter_name),el('p',p.statement),el('p',s.role+' · '+p.component+' · '+s.unit_ref),el('p','계산 입력 정의 초안입니다. 관측값은 별도로 제공하며, 서버 검사와 계산 사용 자격을 아직 받지 않았습니다.','notice'));for(const c of [...s.conditions,...s.exceptions,...p.uncertainties])card.append(el('p',c,'muted'));const d=el('details');d.append(el('summary','원문 근거 보기'));for(const q of p.evidence)d.append(el('p',q.field_locator,'muted'),el('blockquote',q.quote));card.append(d);list.append(card);}
 const limits=document.getElementById('limits');limits.replaceChildren(el('p','작성자가 확인하지 못한 내용입니다. 미상인 부분을 정상 값이나 확인된 사실로 바꾸지 않았습니다.','notice'));
 for(const v of r.unresolved)limits.append(el('p',v.description));limits.append(el('p',`구조화의 완전성: ${r.coverage_disposition.typed_coverage_complete===true?'별도 증거 확인 필요':'아직 입증하지 않음'}`,'muted'));
 for(const p of document.querySelectorAll('.panel'))p.hidden=p.id!==tab;for(const b of document.querySelectorAll('[data-tab]'))b.setAttribute('aria-selected',String(b.dataset.tab===tab));}
document.getElementById('search').addEventListener('input',navigation);window.addEventListener('resize',navigation);for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>{tab=b.dataset.tab;render();};render();
</script></html>'''


def render(spec_path, bundle_path, output):
    spec=json.loads(Path(spec_path).read_text())
    bundle=Path(bundle_path)
    manifest=LocalBundleManifest.model_validate_json((bundle/'manifest.json').read_bytes())
    report=json.loads((bundle/'authoring-report.json').read_text())
    if (report['manifest_digest']!=manifest.digest or report['authoring_spec_digest']!=semantic_digest(spec)
            or report['publication_committed'] or not report['local_only']):
        raise ValueError('LOCAL_REVIEW_EXACT_LOCAL_BUNDLE_REQUIRED')
    if (not report.get('records') or len(report['records']) != len(spec['records'])
            or any(r.get('local_checks_passed') is not True for r in report['records'])):
        raise ValueError('LOCAL_REVIEW_LOCAL_CHECKS_REQUIRED')
    for obj in manifest.objects:
        raw=(bundle/(obj.object_id+'.blob')).read_bytes()
        if len(raw)!=obj.byte_length or byte_digest(raw)!=obj.byte_digest:
            raise ValueError('LOCAL_REVIEW_BUNDLE_OBJECT_CHANGED')
    inventories={key:load_authoring_inventory(source['inventory'],source['byte_digest'],
        context_roles=authoring_context_roles(spec,key))
        for key,source in spec['sources'].items()}
    for key,(fields,_) in inventories.items():
        source_file=bundle/(key+'.blob')
        if source_file.exists():
            raw=source_file.read_bytes()
        else:
            declared=spec['sources'][key].get('existing_artifact')
            if declared not in [s.model_dump(mode='json') for s in manifest.existing_sources]:
                raise ValueError('LOCAL_REVIEW_EXISTING_SOURCE_NOT_DECLARED')
            raw=Path(spec['sources'][key]['path']).read_bytes()
        if byte_digest(raw)!=spec['sources'][key]['byte_digest']:
            raise ValueError('LOCAL_REVIEW_SOURCE_BYTES_CHANGED')
        verify_authoring_fields(raw,fields)
    records=[]
    for record in spec['records']:
        fields=inventories[record['source_object_id']][0]
        source_fields=[f for f in fields.values() if f['role']=='source' and f['record_locator']==record['source_record_locator']]
        if not source_fields:raise ValueError('LOCAL_REVIEW_SOURCE_RECORD_REQUIRED')
        contexts=[fields[c['field_locator']] for c in record.get('context_fields',[])]
        records.append({**record,'source_fields':source_fields,'context_source_fields':contexts})
    data={'records':records,'manifest_digest':manifest.digest,
        'profile_change':next((c.model_dump(mode='json') for c in manifest.changes
            if c.kind=='profile' and c.operation=='revise'),None),
        'profile_components':spec['profile']['components'],
        'source_records':sum(v[1]['role_record_counts']['source'] for v in inventories.values()),
        'selected_source_records':len({(r['source_object_id'],r['source_record_locator']) for r in records}),
        'predicate_labels':{c['id']:c['label'] for c in spec['profile']['components'] if c['kind']=='predicate'}}
    encoded=json.dumps(data,ensure_ascii=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    with Path(output).open('x') as f:f.write(PAGE.replace('__DATA__',encoded))
    return {'output':str(output),'records':len(records),'manifest_digest':manifest.digest,
        'network_access':False,'publication_committed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec',required=True,type=Path)
    p.add_argument('--bundle',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    print(json.dumps(render(args.spec,args.bundle,args.output),ensure_ascii=False))


if __name__=='__main__':main()
