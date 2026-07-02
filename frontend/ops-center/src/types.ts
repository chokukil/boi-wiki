import type { Edge, Node } from "@xyflow/react";

export type OpsRisk = "normal" | "medium" | "high";

export interface OpsSummary {
  open_count: number;
  approval_required: number;
  missing_evidence: number;
  delay_risk: number;
  agent_jobs?: number;
}

export interface OpsRunPreview {
  run_id: string;
  sop_title: string;
  occurred_label: string;
  target: string;
  stage: string;
  status: string;
  status_line: string;
  focus_note: string;
  focus_points?: string[];
  business_brief?: string;
  url?: string;
  report_url?: string;
}

export interface OpsWorkstreamNodeData extends Record<string, unknown> {
  label: string;
  count: number;
  risk: OpsRisk;
  status: string;
  badges: string[];
  preview_items: OpsRunPreview[];
  overflow_count?: number;
  lane?: string;
  cluster_id?: string;
  display_priority?: number;
  collapsed?: boolean;
}

export interface OpsPersonNodeData extends Record<string, unknown> {
  label: string;
  employee_id: string;
  open_count: number;
  lane?: string;
  cluster_id?: string;
  display_priority?: number;
  collapsed?: boolean;
}

export interface OpsSimpleNodeData extends Record<string, unknown> {
  label: string;
  subtitle?: string;
  status?: string;
  risk?: OpsRisk;
  count?: number;
  latest_jobs?: SandboxJobSummary[];
  lane?: string;
  cluster_id?: string;
  display_priority?: number;
  collapsed?: boolean;
}

export interface AgentConversationMessage {
  role: string;
  content: string;
  created_at?: string;
}

export interface AgentConversationSummary {
  conversation_id: string;
  agent_id: string;
  title: string;
  updated_at?: string;
  created_at?: string;
  message_count?: number;
  archived?: boolean;
  latest_message?: string;
  messages?: AgentConversationMessage[];
}

export interface OpsAgentNodeData extends OpsSimpleNodeData {
  agent_id: string;
  deployment_id?: string;
  visibility?: "private" | "team" | "public";
  created_by?: string;
  owner_employee_id?: string;
  usage_count?: number;
  last_used_at?: string;
  conversation_count?: number;
  conversations?: AgentConversationSummary[];
  is_linked_to_me?: boolean;
}

export interface OpsCanvasPayload {
  ok: boolean;
  employee_id: string;
  summary: OpsSummary;
  nodes: Node[];
  edges: Edge[];
  focus_queue: OpsRunPreview[];
  selected_node_id?: string;
  selected_run_id?: string;
  runtime_health?: Record<string, unknown>;
  performance?: Record<string, unknown>;
  overview?: Record<string, unknown>;
}

export interface SandboxArtifactSummary {
  path: string;
  artifact_url?: string;
  bytes?: number;
  preview?: string;
}

export interface SandboxJobSummary {
  job_id: string;
  title: string;
  task?: string;
  status?: string;
  evidence_state?: string;
  execution_mode?: string;
  runtime_backend?: string;
  language?: string;
  created_at?: string;
  latency_ms?: number;
  exit_code?: number;
  stdout_preview?: string;
  stderr_preview?: string;
  validation_result?: {
    state?: string;
    message?: string;
  };
  summary?: {
    state?: string;
    ok?: boolean;
    model?: string;
    output?: string;
    error?: string;
  };
  artifacts?: SandboxArtifactSummary[];
}

export interface SopRunContext {
  ok: boolean;
  run: Record<string, unknown>;
  stage_state: {
    stage_id?: string;
    label?: string;
    status?: string;
    risk?: string;
  };
  business_context: Record<string, unknown>;
  focus_points: string[];
  decision_packet?: {
    why_assigned?: string;
    current_stage?: string;
    available_evidence?: string[];
    missing_evidence?: string[];
    recommended_action?: string;
    decision_actions?: string[];
  };
  evidence_packets?: Array<{
    label: string;
    kind: string;
    state: string;
    missing_reason?: string;
  }>;
  report_links?: Array<{ label: string; url: string }>;
  report_target?: {
    report_id: string;
    label?: string;
  };
}
