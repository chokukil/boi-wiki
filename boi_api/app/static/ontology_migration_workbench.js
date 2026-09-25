(() => {
  "use strict";

  const root = document.querySelector("[data-migration-job-id]");
  if (!root) return;
  const status = document.getElementById("migration-action-status");
  root.querySelectorAll('[data-reviewed-query]').forEach((form) => {
    const option=JSON.parse(form.dataset.queryOption);
    const prepare=form.querySelector('[data-query-prepare]');
    const execute=form.querySelector('[data-query-execute]');
    const message=form.querySelector('[data-query-status]');
    const evidence=form.querySelector('[data-query-evidence]');
    const result=form.querySelector('[data-query-result]');
    const questionInput=form.querySelector('[data-query-question]');
    const fallbackInputs=form.querySelector('[data-query-fallback]');
    let frozen=null;
    function syncInputMode(){
      if(fallbackInputs)fallbackInputs.hidden=Boolean(questionInput?.value.trim());
    }
    function busy(value){form.querySelectorAll('input, textarea, select').forEach(control=>{
      if(value&&!control.disabled){control.dataset.queryLocked='true';control.disabled=true;}
      else if(!value&&control.dataset.queryLocked){control.disabled=false;delete control.dataset.queryLocked;}
    });}

    const report=(text,error=false)=>{message.textContent=text;message.setAttribute('role',error?'alert':'status');};
    function paragraph(text,className=''){
      const node=document.createElement('p');node.textContent=text;if(className)node.className=className;return node;
    }
    function renderBlocked(view){
      result.replaceChildren();
      result.append(paragraph(view?.direct_answer||'조회 계획을 준비하지 못했습니다.','query-answer-summary'));
      if(view?.next_action)result.append(paragraph(view.next_action,'query-answer-next-action'));
      if(view?.scope_notice)result.append(paragraph(view.scope_notice,'query-answer-scope'));
      if(view?.reason_codes?.length){
        const details=document.createElement('details');const summary=document.createElement('summary');
        summary.textContent='차단 근거';details.append(summary);
        const list=document.createElement('ul');for(const code of view.reason_codes){
          const item=document.createElement('li');const value=document.createElement('code');
          value.textContent=code;item.append(value);list.append(item);
        }details.append(list);result.append(details);
      }
    }
    function renderAnswer(answer,access){
      const view=answer.presentation;
      if(!view||view.execution_classification!=='PROVISIONAL')throw new Error('REVIEWED_ANSWER_PRESENTATION_REQUIRED');
      const labels=new Map((answer.meaning_context?.definitions||[]).map(item=>{
        const payload=item.logical_definition||{};
        const fallback=String(item.ref||'').split(':').at(-1)||String(item.ref||'');
        const label=String(payload.name||payload.display_name||payload.term||payload.symbol||fallback).trim();
        return [item.ref,label.slice(0,120)||fallback];
      }));
      const referenceLabel=ref=>labels.get(ref)||String(ref||'').split(':').at(-1)||String(ref||'');
      const unitLabel=unit=>{
        if(!unit)return '';
        if(String(unit).startsWith('property-ref:')){
          const ref=String(unit).slice('property-ref:'.length);
          return '행별 단위: '+referenceLabel(ref);
        }
        return referenceLabel(unit);
      };
      result.replaceChildren();
      result.append(paragraph(view.direct_answer,'query-answer-summary'));
      result.append(paragraph(view.scope_notice,'query-answer-scope'));
      if(view.meaning_context_completeness==='partial')result.append(paragraph(
        '일부 참조 정의가 현재 의미 묶음에 없어 이 응답은 부분 응답입니다.','query-answer-limitation'));
      result.append(paragraph(view.condition_summary,'query-answer-conditions-summary'));
      if(view.time_range)result.append(paragraph(view.time_range.display_text,'query-answer-time-range'));
      if(view.condition_conflicts?.length)result.append(paragraph('질문 조건과 검토된 원천 조건의 결정적 충돌이 확인되었습니다.','query-answer-conflict'));
      if(view.applied_conditions.length||view.time_range){
        const details=document.createElement('details');const summary=document.createElement('summary');
        summary.textContent='적용 조건';details.append(summary);const list=document.createElement('ul');
        for(const condition of view.applied_conditions){
          const item=document.createElement('li');
          const origins=condition.origins.map(origin=>origin==='QUESTION'?'질문':'검토 원천').join(' + ');
          item.textContent=`${condition.display_text} · ${origins}`;
          if(condition.source_support_count>1)item.textContent+=` · 원천 근거 ${condition.source_support_count}개`;
          list.append(item);
        }
        if(view.time_range){const item=document.createElement('li');item.textContent=`${view.time_range.display_text} · 질문`;list.append(item);}
        details.append(list);result.append(details);
      }
      for(const set of answer.result_sets){
        const heading=document.createElement('h4');
        const summary=view.result_summaries.find(item=>item.result_set_id===set.result_set_id);
        heading.textContent=summary?.display_name||set.object_ref;result.append(heading);
        const table=document.createElement('table');const head=document.createElement('tr');
        const columns=set.fields||[];
        for(const [index,field] of columns.entries()){const cell=document.createElement('th');cell.scope='col';
          const label=summary?.field_labels?.[index]||field.label;
          cell.textContent=field.unit?`${label} (${unitLabel(field.unit)})`:label;cell.title=field.field_ref;head.append(cell);}
        const thead=document.createElement('thead');thead.append(head);table.append(thead);
        const tbody=document.createElement('tbody');for(const row of set.rows||[]){const tr=document.createElement('tr');
          for(const field of columns){const cell=document.createElement('td');const value=row.values[field.output_name];
            cell.textContent=value===null?'—':typeof value==='object'?JSON.stringify(value):String(value);tr.append(cell);}tbody.append(tr);}
        table.append(tbody);result.append(table);
        if(!(set.rows||[]).length)result.append(paragraph('조건을 적용한 결과가 없습니다.','query-answer-empty'));
        if(set.paging){
          let shown=(set.rows||[]).length;
          let cursor=set.paging.next_cursor;
          const pagingStatus=paragraph(
            `전체 ${set.total_row_count.toLocaleString()}건 중 ${shown.toLocaleString()}건 표시`,
            'query-answer-paging-status');
          result.append(pagingStatus);
          if(cursor){
            const more=document.createElement('button');more.type='button';
            more.className='query-answer-next-page';more.dataset.queryNextPage=set.result_set_id;
            more.textContent=`다음 ${set.paging.page_size.toLocaleString()}건 보기`;
            result.append(more);
            more.addEventListener('click',async()=>{
              more.disabled=true;more.setAttribute('aria-busy','true');
              report('현재 원천·검토·실행 권한을 다시 확인하고 다음 결과를 읽는 중입니다.');
              try{
                const page=await post('page',{
                  preparation_receipt_digest:access.preparation_receipt_digest,
                  artifact_ref:access.artifact_ref,
                  answer_artifact_semantic_digest:access.answer_artifact_semantic_digest,
                  result_set_id:set.result_set_id,cursor});
                for(const row of page.rows||[]){const tr=document.createElement('tr');
                  for(const field of columns){const cell=document.createElement('td');const value=row.values[field.output_name];
                    cell.textContent=value===null?'—':typeof value==='object'?JSON.stringify(value):String(value);tr.append(cell);}tbody.append(tr);}
                shown+=page.returned_row_count;cursor=page.next_cursor;
                pagingStatus.textContent=`전체 ${page.total_row_count.toLocaleString()}건 중 ${shown.toLocaleString()}건 표시`;
                form.dataset.pageResponseDigest=page.response_digest;
                form.dataset.pageReceiptDigest=page.page_receipt_digest;
                if(cursor){more.disabled=false;more.textContent=`다음 ${page.page_size.toLocaleString()}건 보기`;}
                else{more.remove();pagingStatus.classList.add('query-answer-paging-complete');}
                report(`PROVISIONAL · 전체 ${page.total_row_count.toLocaleString()}건 중 ${shown.toLocaleString()}건을 확인했습니다.`);
              }catch(error){more.disabled=false;report(`다음 결과 조회 실패: ${error.message}`,true);}
              finally{more.removeAttribute('aria-busy');}
            });
          }else pagingStatus.classList.add('query-answer-paging-complete');
        }
      }
      form.dataset.answerPresentationDigest=view.presentation_digest;
    }
    async function post(action,payload) {
      const response=await fetch(`/api/v2/ontology/migration-jobs/${encodeURIComponent(root.dataset.migrationJobId)}/queries/${action}`,{
        method:'POST',headers:{'content-type':'application/json','X-Boi-Invocation-Channel':'ui'},body:JSON.stringify(payload)});
      const body=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:body.detail?.code||`HTTP_${response.status}`);
      return body;
    }
    form.addEventListener('input',()=>{syncInputMode();delete form.dataset.resultReceipt;delete form.dataset.answerPresentationDigest;
      frozen=null;execute.disabled=true;evidence.textContent='';result.replaceChildren();report('입력이 바뀌었습니다. 조회를 다시 준비하세요.');});
    form.addEventListener('submit',async(event)=>{
      event.preventDefault();prepare.disabled=true;execute.disabled=true;report('정의·근거와 Mapping을 확인 중입니다.');
      try {
        const values=new FormData(form);busy(true);const question=String(values.get('question')||'').trim();
        const payload=question?{shard_id:option.shard_id,preview_digest:option.preview_digest,question}:{
          shard_id:option.shard_id,preview_digest:option.preview_digest,
          intent:{contract_version:'boi/reviewed-object-query-intent@1',root_object_ref:option.root_object_ref,
            property_refs:[...new Set(values.getAll('property_ref'))],order_property_refs:option.key_refs,
            maximum_rows:Number(values.get('maximum_rows'))}};
        frozen=await post(question?'natural/prepare':'prepare',payload);
        evidence.textContent=JSON.stringify(frozen,null,2);
        if(frozen.query_plan_status&&frozen.query_plan_status!=='prepared'){
          renderBlocked(frozen.outcome_presentation);report(frozen.outcome_presentation?.direct_answer||'조회 준비가 차단되었습니다.',true);
          frozen=null;return;
        }
        execute.disabled=false;
        report('조회 준비가 끝났습니다. 조회 시 실행 권한을 확인합니다.');
      } catch(error){frozen=null;report(`조회 준비 실패: ${error.message}`,true);}
      finally{busy(false);prepare.disabled=false;}
    });
    execute.addEventListener('click',async()=>{
      if(!frozen)return;delete form.dataset.resultReceipt;busy(true);prepare.disabled=true;execute.disabled=true;report('실행 권한과 현재 원천을 확인 중입니다.');
      try {
        const digest=frozen.receipt_digest;
        const execution=await post('execute',{preparation_receipt_digest:digest,idempotency_key:`reviewed-query:${digest}`});
        const answer=await post('answer',{preparation_receipt_digest:digest,artifact_ref:execution.receipt.result_artifact_ref});
        renderAnswer(answer,{preparation_receipt_digest:digest,
          artifact_ref:execution.receipt.result_artifact_ref,
          answer_artifact_semantic_digest:answer.artifact_semantic_digest});
        evidence.textContent=JSON.stringify({preparation:frozen,answer_presentation:answer.presentation,
          artifact_semantic_digest:answer.artifact_semantic_digest},null,2);
        form.dataset.resultReceipt=execution.receipt.receipt_digest;
        report('PROVISIONAL · 응답과 적용 근거를 확인했습니다.');
      }catch(error){result.replaceChildren();report(`조회 실패: ${error.message}`,true);}
      finally{busy(false);prepare.disabled=false;execute.disabled=!frozen;}
    });
    syncInputMode();prepare.disabled=false;form.dataset.queryReady='true';report('질문을 입력하거나 조회할 속성을 선택한 뒤 준비하세요.');
  });

  const buttons = Array.from(root.querySelectorAll("[data-migration-action]"));

  function setStatus(message, isError = false) {
    if (!status) return;
    status.textContent = message;
    status.setAttribute("role", isError ? "alert" : "status");
  }

  async function submit(action, button) {
    const data = root.dataset;
    const common = {
      expected_revision: Number.parseInt(data.revision || "0", 10),
      expected_preview_digest: data.previewDigest || "",
    };
    const payload = action === "approve" ? {
      ...common,
      expected_candidate_digest: data.candidateDigest || "",
      expected_plan_digest: data.planDigest || "",
      expected_schema_digest: data.schemaDigest || "",
      expected_qualification_receipt_id: data.qualificationReceiptId || "",
    } : {
      ...common,
      expected_approval_receipt_digest: data.approvalReceiptDigest || "",
    };
    buttons.forEach((item) => { item.disabled = true; });
    button.setAttribute("aria-busy", "true");
    setStatus(action === "approve" ? "Exact preview를 승인 중입니다." : "Release proposal을 기록 중입니다.");
    try {
      const response = await fetch(
        `/api/v2/ontology/migration-jobs/${encodeURIComponent(data.migrationJobId)}/${action}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const code = body?.detail?.code || `HTTP_${response.status}`;
        throw new Error(code);
      }
      setStatus(action === "approve" ? "승인 기록을 저장했습니다." : "Release proposal을 기록했습니다. ReleaseManifest와 Active pointer는 생성하거나 변경하지 않았습니다.");
      window.location.reload();
    } catch (error) {
      setStatus(`처리하지 못했습니다: ${error instanceof Error ? error.message : "UNKNOWN_ERROR"}`, true);
      buttons.forEach((item) => {
        if (item.dataset.migrationAction === action) item.disabled = false;
      });
    } finally {
      button.removeAttribute("aria-busy");
    }
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => submit(button.dataset.migrationAction, button));
  });

  root.querySelectorAll('[data-interpretation-review]').forEach((form) => {
    form.querySelector('button[type="submit"]').disabled = false;
    form.dataset.reviewReady = 'true';
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const values = new FormData(form);
      const reason = String(values.get('reason') || '').trim();
      const output = form.querySelector('[data-interpretation-status]');
      const button = form.querySelector('button[type="submit"]');
      if (!reason || button.disabled) return;
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      output.textContent = '화면에 표시된 후보를 확인하고 있습니다.';
      async function post(url, body) {
        const response = await fetch(url, {method:'POST',
          headers:{'content-type':'application/json','x-boi-invocation-channel':'ui'},
          body:JSON.stringify(body)});
        const result = await response.json();
        if (!response.ok) throw new Error(result?.detail?.code || `HTTP_${response.status}`);
        return result;
      }
      try {
        const plan = await post('/api/v2/capabilities/ontology.migration.migration-batch-review/plan', {
          goal:'원문과 후보를 비교한 의미 해석 검토',
          input:{review_mode:'semantic_interpretation',run_id:root.dataset.migrationJobId,
            shard_id:form.dataset.shardId,expected_preview_digest:form.dataset.previewDigest,
            disposition:values.get('disposition')}});
        if (!plan.plan_ref || plan.job_ref !== root.dataset.migrationJobId)
          throw new Error(plan?.answer?.markdown || '검토 대상을 다시 확인해주세요.');
        const result = await post(`/api/v2/plans/${encodeURIComponent(plan.plan_ref)}/confirm`, {
          confirmation:'confirm',reason,expected_revision:plan.plan_revision,plan_checksum:plan.plan_checksum,
          input_fingerprint:plan.input_fingerprint});
        output.textContent = `검토를 기록했습니다. ${result.interpretation_receipt.receipt_digest}`;
        form.querySelectorAll('select,textarea').forEach((item) => { item.disabled = true; });
      } catch (error) {
        output.textContent = `기록하지 못했습니다: ${error.message}`;
        output.setAttribute('role','alert');
        button.disabled = false;
      } finally {
        button.removeAttribute('aria-busy');
      }
    });
  });

  const bulkPanel = root.querySelector("[data-bulk-run-digest]");
  const bulkButtons = Array.from(root.querySelectorAll("[data-bulk-action]"));
  bulkButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      if (!bulkPanel) return;
      bulkButtons.forEach((item) => { item.disabled = true; });
      button.setAttribute("aria-busy", "true");
      setStatus(`Bulk ${button.dataset.bulkAction} 요청을 기록 중입니다.`);
      try {
        const response = await fetch(
          `/api/v2/ontology/migration-jobs/${encodeURIComponent(root.dataset.migrationJobId)}/control`,
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              action: button.dataset.bulkAction,
              shard_id: button.dataset.shardId || null,
              expected_run_digest: bulkPanel.dataset.bulkRunDigest,
            }),
          },
        );
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
          const code = body?.detail?.code || `HTTP_${response.status}`;
          throw new Error(code);
        }
        setStatus("Bulk run ledger를 갱신했습니다.");
        window.location.reload();
      } catch (error) {
        setStatus(`Bulk action을 처리하지 못했습니다: ${error instanceof Error ? error.message : "UNKNOWN_ERROR"}`, true);
        button.disabled = false;
      } finally {
        button.removeAttribute("aria-busy");
      }
    });
  });

  root.querySelectorAll("[data-mapping-edit-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const data = root.dataset;
      const values = new FormData(form);
      const button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;
      setStatus("Mapping candidate를 저장하고 downstream authority를 무효화하는 중입니다.");
      try {
        const response = await fetch(
          `/api/v2/ontology/migration-jobs/${encodeURIComponent(data.migrationJobId)}/mapping-edit`,
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              expected_revision: Number.parseInt(data.revision || "0", 10),
              expected_candidate_digest: data.candidateDigest || "",
              mapping_id: form.dataset.mappingId || "",
              table_ref: values.get("table_ref") || "",
              column_ref: values.get("column_ref") || "",
              data_type: values.get("data_type") || "",
              key_role: values.get("key_role") || "none",
              unit: values.get("unit") || null,
              cardinality: values.get("cardinality") || "unknown",
              reason: values.get("reason") || "",
            }),
          },
        );
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
          const code = body?.detail?.code || `HTTP_${response.status}`;
          throw new Error(code);
        }
        setStatus("Mapping candidate를 저장했습니다. 새 digest에 대한 결정적 재검증이 필요합니다.");
        window.location.reload();
      } catch (error) {
        setStatus(`Mapping을 저장하지 못했습니다: ${error instanceof Error ? error.message : "UNKNOWN_ERROR"}`, true);
        if (button) button.disabled = false;
      }
    });
  });
})();
