(() => {
  "use strict";

  const metadataForm = document.querySelector('[data-metadata-intake-form]');
  if (metadataForm) {
    const message = metadataForm.querySelector('[data-metadata-intake-status]');
    const submit = metadataForm.querySelector('button[type="submit"]');
    let idempotencyKey = crypto.randomUUID();
    // Editing a selection/input cannot accidentally replay its old approval/run.
    metadataForm.addEventListener('change', () => { idempotencyKey = crypto.randomUUID(); });
    metadataForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!metadataForm.reportValidity()) return;
      submit.disabled = true;
      message.textContent = '원문을 보존하고 서버의 source·정의·정책 계약을 확인하고 있습니다.';
      message.setAttribute('role', 'status');
      try {
        const values = new FormData(metadataForm);
        const file = values.get('source_file');
        const artifact = String(values.get('registered_artifact') || '');
        if (artifact && file && file.size) throw new Error('원문은 파일 또는 등록 artifact 하나만 선택하세요.');
        let envelope;
        if (artifact) {
          envelope = {kind: 'artifact_ref', ...JSON.parse(artifact)};
        } else {
          if (!file || !file.size || file.size > 65536) throw new Error('64 KiB 이하 metadata 파일 또는 등록 artifact를 선택하세요.');
          const bytes = new Uint8Array(await file.arrayBuffer());
          let binary = '';
          bytes.forEach((value) => { binary += String.fromCharCode(value); });
          envelope = {kind: 'inline_source', role: 'corporate_metadata',
            media_type: /\.json$/i.test(file.name) ? 'application/json' : 'application/yaml', content_b64: btoa(binary)};
        }
        const purpose = String(values.get('purpose') || '');
        const response = await fetch('/api/v2/capabilities/ontology.migration.pipeline-run/plan', {
          method: 'POST', headers: {'content-type': 'application/json', 'x-boi-invocation-channel': 'ui'},
          body: JSON.stringify({goal: purpose, input: {project_id: values.get('project_id'), purpose,
            metadata_source_profile_id: values.get('metadata_source_profile_id'),
            max_objects_per_shard: Number(values.get('max_objects_per_shard')),
            idempotency_key: idempotencyKey, source_envelopes: [envelope]}}),
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok || !body.job_ref) {
          throw new Error(typeof body.detail === 'string' ? body.detail : (body.answer?.summary || `HTTP_${response.status}`));
        }
        // No source bytes in local storage, logs, reproduction references or URL.
        metadataForm.reset();
        window.location.assign(`/ontology/migrations/${encodeURIComponent(body.job_ref)}`);
      } catch (error) {
        message.setAttribute('role', 'alert');
        message.textContent = error instanceof Error ? error.message : 'METADATA_INTAKE_FAILED';
        submit.disabled = false;
      }
    });
  }

  const form = document.querySelector("[data-migration-intake-form]");
  if (!form) return;
  const status = form.querySelector("[data-migration-intake-status]");
  const button = form.querySelector('button[type="submit"]');

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.setAttribute("role", isError ? "alert" : "status");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const values = new FormData(form);
    button.disabled = true;
    setStatus("Source와 catalog ref를 candidate로 등록하는 중입니다.");
    try {
      let mappingCandidates;
      try {
        mappingCandidates = JSON.parse(values.get("mapping_candidates") || "[]");
      } catch (_error) {
        throw new Error("MAPPING_CANDIDATES_JSON_INVALID");
      }
      const response = await fetch(
        "/api/v2/capabilities/ontology.migration.pipeline-run/plan",
        {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "x-boi-invocation-channel": "ui",
          },
          body: JSON.stringify({
            goal: values.get("goal") || "",
            input: {
              project_id: values.get("project_id") || "",
              mode: "hybrid",
              source_artifacts: [
                {
                  artifact_ref: values.get("sql_source_ref") || "",
                  digest: values.get("sql_source_digest") || "",
                  role: "sql",
                },
                {
                  artifact_ref: values.get("metadata_source_ref") || "",
                  digest: values.get("metadata_source_digest") || "",
                  role: "corporate_metadata",
                },
              ],
              catalog_snapshot_ref: values.get("catalog_snapshot_ref") || "",
              catalog_snapshot_digest: values.get("catalog_snapshot_digest") || "",
              schema_snapshot_digest: values.get("schema_snapshot_digest") || "",
              selector: {
                systems: [values.get("system") || ""],
                schemas: [values.get("schema") || ""],
                tables: String(values.get("tables") || "").split(",").map((item) => item.trim()).filter(Boolean),
              },
              requested_skill_stages: [
                "legacy-source-intake",
                "sql-lineage-extract",
                "domain-ontology-draft",
                "existing-concept-match",
                "physical-mapping-verify",
                "query-contract-author",
                "migration-batch-review",
                "harness-evolution",
              ],
              profile_revisions: ["boi/domain@0.2.0", "boi/data-mapping@0.1.0", "boi/query@0.1.0"],
              evaluator_code_digests: [values.get("evaluator_code_digest") || ""],
              model_role_prompt_digests: [values.get("model_role_prompt_digest") || ""],
              active_concept_index_ref: values.get("active_concept_index_ref") || "",
              active_concept_index_digest: values.get("active_concept_index_digest") || "",
              evidence_span_refs: String(values.get("evidence_span_refs") || "").split(",").map((item) => item.trim()).filter(Boolean),
              mapping_candidates: mappingCandidates,
              acl_policy_digest: values.get("acl_policy_digest") || "",
              purpose: values.get("goal") || "",
              idempotency_key: values.get("idempotency_key") || "",
              before_hashes: {},
              atomic_object_count: Math.max(1, mappingCandidates.length),
              max_objects_per_shard: 100,
              dry_run: true,
              local_model_policy: "pi-unresolved-only-no-codex-fallback",
              resume_retry_policy: "exact-failed-shard-only",
            },
          }),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok || !body.job_ref) {
        const code = body?.detail?.code || body?.detail || `HTTP_${response.status}`;
        throw new Error(typeof code === "string" ? code : JSON.stringify(code));
      }
      setStatus("Candidate intake를 만들었습니다. 검토 화면으로 이동합니다.");
      window.location.assign(`/ontology/migrations/${encodeURIComponent(body.job_ref)}`);
    } catch (error) {
      setStatus(`Candidate intake를 만들지 못했습니다: ${error instanceof Error ? error.message : "UNKNOWN_ERROR"}`, true);
      button.disabled = false;
    }
  });
})();
