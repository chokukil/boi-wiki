export type BoiV2ClientOptions = {
  baseUrl?: string;
  token?: string;
};

export class BoiV2Client {
  private readonly baseUrl: string;
  private readonly token: string;

  constructor(options: BoiV2ClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? process.env.BOI_BASE_URL ?? "http://localhost:28000").replace(/\/$/, "");
    this.token = options.token ?? process.env.BOI_PAT ?? "";
    if (!this.token.startsWith("boi_pat_")) throw new Error("BOI_PAT must be a BoI Wiki personal access token");
  }

  private async request(path: string, init: RequestInit = {}): Promise<Record<string, unknown>> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
      },
    });
    if (!response.ok) throw new Error(`BoI API ${response.status}: ${await response.text()}`);
    return response.json() as Promise<Record<string, unknown>>;
  }

  bootstrap(pageRef = "") {
    return this.request(`/api/v2/bootstrap?page_ref=${encodeURIComponent(pageRef)}`);
  }

  search(query = "", options: { view?: "ranked" | "neighbors" | "path" | "impact" | "tour"; sourceRef?: string; targetRef?: string; depth?: number; includeHistory?: boolean; limit?: number } = {}) {
    const view = options.view ?? "ranked";
    const limit = options.limit ?? 8;
    if (view === "ranked") {
      return this.request(`/api/v2/search?q=${encodeURIComponent(query)}&include_history=${options.includeHistory ?? false}&limit=${limit}`);
    }
    const params = new URLSearchParams({
      view,
      source_ref: options.sourceRef ?? "",
      target_ref: options.targetRef ?? "",
      q: query,
      depth: String(options.depth ?? 2),
      limit: String(limit),
    });
    return this.request(`/api/v2/knowledge-graph/explore?${params.toString()}`);
  }

  agent(question: string, workSessionId = "", pageRef = "", taskRef = "", capabilityId = "", externalAiSummary = "", externalArtifactRefs: string[] = []) {
    const payload: Record<string, string | string[] | null> = {
      question,
      work_session_id: workSessionId || null,
      page_ref: pageRef,
      task_ref: taskRef,
      external_ai_summary: externalAiSummary,
      external_artifact_refs: externalArtifactRefs,
    };
    if (capabilityId) payload.capability_id = capabilityId;
    return this.request("/api/v2/agent/turns", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  plan(capabilityId: string, goal: string, pageRef = "", taskRef = "") {
    return this.request(`/api/v2/capabilities/${encodeURIComponent(capabilityId)}/plan`, {
      method: "POST",
      body: JSON.stringify({ goal, page_ref: pageRef, task_ref: taskRef, input: {} }),
    });
  }

  confirm(planId: string, reason: string) {
    return this.request(`/api/v2/plans/${encodeURIComponent(planId)}/confirm`, {
      method: "POST",
      body: JSON.stringify({ confirmation: "confirm", reason }),
    });
  }

  job(jobId: string) {
    return this.request(`/api/v2/deep-jobs/${encodeURIComponent(jobId)}`);
  }

  workRun(workRunId: string) {
    return this.request(`/api/v2/work-runs/${encodeURIComponent(workRunId)}`);
  }

  continueWorkRun(workRunId: string, expectedRevision: number, kind: string, summary: string, ref = "", confirm = false) {
    return this.request(`/api/v2/work-runs/${encodeURIComponent(workRunId)}/continue`, {
      method: "POST",
      body: JSON.stringify({
        expected_revision: expectedRevision,
        confirmation: confirm ? "confirm" : null,
        delta: { kind, summary, ref },
      }),
    });
  }

  knowledgeCandidates(status = "") {
    return this.request(`/api/v2/knowledge-candidates?status=${encodeURIComponent(status)}`);
  }

  reviewKnowledgeCandidate(candidateId: string, expectedRevision: number) {
    return this.request(`/api/v2/knowledge-candidates/${encodeURIComponent(candidateId)}`, {
      method: "PATCH",
      body: JSON.stringify({ expected_revision: expectedRevision, status: "reviewed" }),
    });
  }
}
