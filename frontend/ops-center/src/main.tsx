import React, { memo, useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Background,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  MiniMap,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type EdgeProps,
  type Node,
  type NodeProps
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import type {
  AgentConversationMessage,
  AgentConversationSummary,
  OpsCanvasPayload,
  OpsAgentNodeData,
  OpsPersonNodeData,
  OpsRisk,
  OpsRunPreview,
  SandboxJobSummary,
  OpsSimpleNodeData,
  OpsWorkstreamNodeData,
  SopRunContext
} from "./types";

type DrawerMode = "summary" | "workstream" | "run" | "agent" | "evidence" | "decision";

interface DrawerState {
  mode: DrawerMode;
  title: string;
  subtitle?: string;
  runId?: string;
  nodeId?: string;
  preview?: OpsRunPreview;
  workstream?: OpsWorkstreamNodeData;
  sandboxJobs?: SandboxJobSummary[];
  agent?: OpsAgentNodeData;
}

const riskLabel: Record<OpsRisk, string> = {
  high: "고위험",
  medium: "주의",
  normal: "정상"
};

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function readBootstrap(): { employeeId: string; initialCanvas?: OpsCanvasPayload } {
  const el = document.getElementById("ops-center-bootstrap");
  if (!el) return { employeeId: "100001" };
  try {
    const parsed = JSON.parse(el.textContent || "{}");
    return {
      employeeId: String(parsed.employee_id || parsed.employeeId || "100001"),
      initialCanvas: parsed.canvas
    };
  } catch (_error) {
    return { employeeId: "100001" };
  }
}

function nodeRiskClass(risk?: unknown) {
  const value = String(risk || "normal");
  if (value === "high") return "risk-high";
  if (value === "medium") return "risk-medium";
  return "risk-normal";
}

const PersonNode = memo(function PersonNode({ data }: NodeProps<Node<OpsPersonNodeData>>) {
  return (
    <section className="ops-rf-node ops-person-node">
      <Handle type="source" position={Position.Right} />
      <Handle type="source" position={Position.Left} />
      <span>나</span>
      <strong>{data.employee_id || data.label}</strong>
      <small>열린 업무 {data.open_count ?? 0}건</small>
    </section>
  );
});

const SopWorkstreamNode = memo(function SopWorkstreamNode({ data }: NodeProps<Node<OpsWorkstreamNodeData>>) {
  const previews = Array.isArray(data.preview_items) ? data.preview_items.slice(0, 1) : [];
  const remaining = Math.max(0, Number(data.count || 0) - previews.length);
  return (
    <section className={cx("ops-rf-node ops-workstream-node", nodeRiskClass(data.risk))}>
      <Handle type="target" position={Position.Left} />
      <Handle type="target" position={Position.Right} />
      <Handle type="source" position={Position.Bottom} />
      <div className="ops-node-header">
        <strong>{data.label}</strong>
        <span>{data.count}건</span>
      </div>
      <div className="ops-node-statusline">
        <span>{riskLabel[data.risk || "normal"]}</span>
        <em>{data.status || "진행 중"}</em>
      </div>
      <div className="ops-node-badges">
        {(data.badges || []).slice(0, 3).map((badge) => (
          <em key={badge}>{badge}</em>
        ))}
      </div>
      <div className="ops-node-runs">
        {previews.map((item) => (
          <button
            type="button"
            key={item.run_id}
            className="ops-node-run"
            data-run-id={item.run_id}
            data-run-preview="true"
          >
            <span>{item.occurred_label || "시간 확인"} · {item.target}</span>
            <strong>{item.stage || item.status_line}</strong>
            <small>{item.focus_note || item.status_line}</small>
          </button>
        ))}
        {remaining > 0 && <span className="ops-node-overflow">+{remaining}건은 우측 패널에서 비교</span>}
      </div>
    </section>
  );
});

const SimpleNode = memo(function SimpleNode({ data, type }: NodeProps<Node<OpsSimpleNodeData>>) {
  return (
    <section className={cx("ops-rf-node ops-simple-node", `ops-${type || "simple"}-node`, nodeRiskClass(data.risk))}>
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />
      <div className="ops-node-header">
        <strong>{data.label}</strong>
        {typeof data.count === "number" && <span>{data.count}</span>}
      </div>
      {data.subtitle && <small>{data.subtitle}</small>}
      {data.status && <em>{data.status}</em>}
    </section>
  );
});

function LabeledEdge(props: EdgeProps) {
  const { id, sourceX, sourceY, targetX, targetY, data, markerEnd, selected } = props;
  const midX = (sourceX + targetX) / 2;
  const midY = (sourceY + targetY) / 2;
  const badges = Array.isArray(data?.badges) ? data.badges : [];
  const label = badges.slice(0, 2).join(" · ") || String(data?.label || "연결");
  const displayMode = String(data?.display_mode || "dot");
  const showLabel = selected || displayMode === "label" || displayMode === "expanded";
  return (
    <>
      <path
        id={id}
        className={cx("react-flow__edge-path ops-rf-edge-path", nodeRiskClass(data?.risk))}
        d={`M ${sourceX},${sourceY} C ${sourceX + 80},${sourceY} ${targetX - 80},${targetY} ${targetX},${targetY}`}
        markerEnd={markerEnd}
      />
      <EdgeLabelRenderer>
        <button
          type="button"
          className={cx("ops-rf-edge-label", !showLabel && "dot-only")}
          style={{ transform: `translate(-50%, -50%) translate(${midX}px,${midY}px)` }}
          data-edge-id={id}
          title={label}
          aria-label={label}
        >
          <span>{label}</span>
        </button>
      </EdgeLabelRenderer>
    </>
  );
}

const nodeTypes = {
  personNode: PersonNode,
  sopWorkstreamNode: SopWorkstreamNode,
  sopRunNode: SimpleNode,
  agentNode: SimpleNode,
  agentConversationNode: SimpleNode,
  evidenceNode: SimpleNode,
  sandboxJobNode: SimpleNode,
  decisionNode: SimpleNode,
  reportNode: SimpleNode
};

const edgeTypes = {
  opsLabeled: LabeledEdge
};

function inferLane(node: Node): string {
  const lane = String(node.data?.lane || "");
  if (lane) return lane;
  if (node.type === "personNode") return "person";
  if (node.type === "sopWorkstreamNode") return "sop_workstream";
  if (node.type === "sopRunNode") return "selected_run";
  if (node.type === "evidenceNode") return "evidence";
  if (node.type === "reportNode") return "report";
  if (node.type === "decisionNode") return "decision";
  if (node.type === "agentConversationNode") return "agent_conversation";
  if (node.type === "agentNode" || node.type === "sandboxJobNode") return "agent";
  return "support";
}

function priorityOf(node: Node): number {
  const priority = Number(node.data?.display_priority);
  return Number.isFinite(priority) ? priority : 100;
}

function lanePosition(node: Node, laneIndex: number): { x: number; y: number } {
  const lane = inferLane(node);
  if (lane === "person") return { x: 70, y: 280 };
  if (lane === "sop_workstream") return { x: 310, y: 80 + laneIndex * 220 };
  if (lane === "selected_run") return { x: 620, y: 95 + laneIndex * 150 };
  if (lane === "evidence") return { x: 680, y: 120 };
  if (lane === "report") return { x: 680, y: 320 };
  if (lane === "decision") return { x: 680, y: 520 };
  if (lane === "agent") return { x: 960, y: 155 + laneIndex * 220 };
  if (lane === "agent_conversation") return { x: 1230, y: 150 + laneIndex * 160 };
  return { x: 680, y: 120 + laneIndex * 170 };
}

function layoutNodes(nodes: Node[]): Node[] {
  const laneCounts = new Map<string, number>();
  return [...nodes]
    .sort((left, right) => priorityOf(left) - priorityOf(right))
    .map((node) => {
      const lane = inferLane(node);
      const laneIndex = laneCounts.get(lane) || 0;
      laneCounts.set(lane, laneIndex + 1);
      return {
        ...node,
        position: lanePosition(node, laneIndex),
        draggable: false,
        data: {
          ...node.data,
          lane
        }
      };
    });
}

function normalizeCanvas(payload: OpsCanvasPayload): OpsCanvasPayload {
  const visibleNodes = (payload.nodes || []).filter((node) => {
    if (node.type !== "sopRunNode") return true;
    return node.data?.collapsed === false;
  });
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  return {
    ...payload,
    nodes: layoutNodes(visibleNodes),
    edges: (payload.edges || []).filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)).map((edge) => {
      const badges = Array.isArray(edge.data?.badges) ? edge.data.badges : [];
      const risk = String(edge.data?.risk || "normal");
      const stroke = risk === "high" ? "#dc2626" : risk === "medium" ? "#d97706" : "#2563eb";
      return {
        ...edge,
        type: "opsLabeled",
        data: {
          ...edge.data,
          display_mode: edge.data?.display_mode || "dot"
        },
        style: { stroke, strokeWidth: risk === "high" ? 3.5 : risk === "medium" ? 3 : 2.5 },
        markerEnd: edge.markerEnd || { type: MarkerType.ArrowClosed, width: 18, height: 18, color: stroke },
        animated: Boolean(edge.animated)
      };
    })
  };
}

function formatContextValue(value: unknown): string {
  if (value == null || value === "") return "-";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function FocusQueue({
  items,
  selectedRunId,
  onSelect
}: {
  items: OpsRunPreview[];
  selectedRunId?: string;
  onSelect: (item: OpsRunPreview) => void;
}) {
  return (
    <aside className="ops-focus-queue">
      <div className="ops-side-title">
        <h2>Focus Queue</h2>
        <span>{items.length}건</span>
      </div>
      <div className="ops-filter-chips">
        <button type="button" className="active">전체</button>
        <button type="button">정규 SOP</button>
        <button type="button">Agent</button>
        <button type="button">근거 부족</button>
        <button type="button">승인</button>
      </div>
      <div className="ops-focus-list">
        {items.length ? (
          items.map((item) => (
            <button
              type="button"
              className={cx("ops-focus-item", selectedRunId === item.run_id && "selected")}
              key={item.run_id}
              onClick={() => onSelect(item)}
            >
              <span>{item.occurred_label || "시간 확인"} · {item.target}</span>
              <strong>{item.stage || item.sop_title}</strong>
              <small>{item.focus_note || item.status_line}</small>
            </button>
          ))
        ) : (
          <div className="ops-empty">
            <strong>열린 업무가 없습니다.</strong>
            <p>새 Event, Agent 작업, 근거 요청이 들어오면 표시됩니다.</p>
          </div>
        )}
      </div>
    </aside>
  );
}

function SandboxJobList({
  jobs,
  actionState,
  onAdopt,
  onAttach
}: {
  jobs: SandboxJobSummary[];
  actionState: Record<string, string>;
  onAdopt: (job: SandboxJobSummary) => void;
  onAttach: (job: SandboxJobSummary) => void;
}) {
  if (!jobs.length) {
    return (
      <div className="ops-empty">
        <strong>Sandbox 실행 결과가 없습니다.</strong>
        <p>Agent 또는 Evidence node에서 테스트를 실행하면 계산 근거와 artifact가 여기에 표시됩니다.</p>
      </div>
    );
  }
  return (
    <div className="ops-sandbox-list" data-sandbox-job-list="true">
      {jobs.map((job) => (
        <article className="ops-sandbox-job" key={job.job_id} data-sandbox-job-id={job.job_id}>
          <div className="ops-sandbox-job-head">
            <div>
              <strong>{job.title || job.job_id}</strong>
              <span>{job.execution_mode || "sandbox"} · {job.language || "code"} · {job.latency_ms ? `${job.latency_ms}ms` : "시간 확인"}</span>
            </div>
            <em className={cx(job.status === "completed" && "ready", job.status === "failed" && "failed")}>{job.evidence_state || job.status}</em>
          </div>
          {job.task && <p>{job.task}</p>}
          {job.summary?.output && (
            <section className="ops-sandbox-summary">
              <span>GPT-5.5 검증 요약</span>
              <p>{job.summary.output}</p>
            </section>
          )}
          {job.validation_result?.message && (
            <section className="ops-sandbox-validation">
              <span>검증 결과</span>
              <p>{job.validation_result.message}</p>
            </section>
          )}
          <div className="ops-sandbox-artifacts">
            {(job.artifacts || []).map((artifact) => (
              <a key={`${job.job_id}:${artifact.path}`} href={artifact.artifact_url || "#"} target="_blank" rel="noreferrer">
                <strong>{artifact.path}</strong>
                <small>{artifact.bytes ? `${artifact.bytes} bytes` : "artifact"}</small>
              </a>
            ))}
          </div>
          <details className="ops-sandbox-raw">
            <summary>실행 로그 보기</summary>
            <pre>{job.stdout_preview || "stdout 없음"}</pre>
            {job.stderr_preview && <pre className="stderr">{job.stderr_preview}</pre>}
          </details>
          <div className="ops-sandbox-actions">
            <button type="button" data-sandbox-adopt={job.job_id} onClick={() => onAdopt(job)}>검증 근거로 채택</button>
            <button type="button" data-sandbox-attach={job.job_id} onClick={() => onAttach(job)}>보고서에 반영</button>
          </div>
          {actionState[job.job_id] && <p className="ops-sandbox-action-status">{actionState[job.job_id]}</p>}
        </article>
      ))}
    </div>
  );
}

function ContextDrawer({
  state,
  context,
  sandboxJobs,
  agentConversations,
  selectedConversationId,
  agentMessageDraft,
  agentActionState,
  sandboxActionState,
  loading,
  sandboxLoading,
  onMode,
  onSelectRun,
  onNewAgentConversation,
  onSelectAgentConversation,
  onAgentMessageDraft,
  onSendAgentMessage,
  onIngestAgentConversation,
  onArchiveAgentConversation,
  onAdoptSandboxEvidence,
  onAttachSandboxEvidence
}: {
  state: DrawerState;
  context: SopRunContext | null;
  sandboxJobs: SandboxJobSummary[];
  agentConversations: AgentConversationSummary[];
  selectedConversationId: string;
  agentMessageDraft: string;
  agentActionState: string;
  sandboxActionState: Record<string, string>;
  loading: boolean;
  sandboxLoading: boolean;
  onMode: (mode: DrawerMode) => void;
  onSelectRun: (item: OpsRunPreview) => void;
  onNewAgentConversation: () => void;
  onSelectAgentConversation: (conversationId: string) => void;
  onAgentMessageDraft: (value: string) => void;
  onSendAgentMessage: () => void;
  onIngestAgentConversation: () => void;
  onArchiveAgentConversation: () => void;
  onAdoptSandboxEvidence: (job: SandboxJobSummary) => void;
  onAttachSandboxEvidence: (job: SandboxJobSummary) => void;
}) {
  const run = (context?.run || {}) as Record<string, unknown>;
  const business = context?.business_context || {};
  const decision = context?.decision_packet;
  const evidence = context?.evidence_packets || [];
  const links = context?.report_links || [];
  const focus = context?.focus_points || state.preview?.focus_points || [];
  const visibleSandboxJobs = sandboxJobs.length ? sandboxJobs : state.sandboxJobs || [];
  const workstreamItems = state.workstream?.preview_items || [];
  const selectedConversation = agentConversations.find((item) => item.conversation_id === selectedConversationId) || agentConversations[0];
  const activeMessages = (selectedConversation?.messages || []) as AgentConversationMessage[];

  return (
    <aside className="ops-context-drawer" aria-label="Operations Center 상세">
      <div className="ops-drawer-head">
        <span>{state.mode === "agent" ? "Agent" : state.mode === "evidence" ? "Evidence" : state.mode === "workstream" ? "SOP Workstream" : "SOP Run"}</span>
        <h2>{state.title}</h2>
        {state.subtitle && <p>{state.subtitle}</p>}
      </div>
      <div className="ops-drawer-tabs" role="tablist">
        <button type="button" className={state.mode === "workstream" ? "active" : ""} onClick={() => onMode("workstream")}>요약</button>
        <button type="button" className={state.mode === "run" ? "active" : ""} onClick={() => onMode("run")}>맥락</button>
        <button type="button" className={state.mode === "evidence" ? "active" : ""} onClick={() => onMode("evidence")}>근거</button>
        <button type="button" className={state.mode === "decision" ? "active" : ""} onClick={() => onMode("decision")}>판단</button>
        <button type="button" className={state.mode === "agent" ? "active" : ""} onClick={() => onMode("agent")}>Agent</button>
      </div>
      {loading && <div className="ops-loading">업무 맥락을 불러오는 중입니다.</div>}

      {state.mode === "agent" ? (
        <>
          <section className="ops-drawer-section">
            <h3>내 Agent</h3>
            <p>{state.agent?.description || "선택한 Agent와 대화하고, 필요한 산출물은 BoI Wiki에 저장해 업무 맥락으로 재사용합니다."}</p>
            <div className="ops-focus-points">
              <span>{state.agent?.visibility || "private"}</span>
              <span>사용 {state.agent?.usage_count || 0}회</span>
              <span>대화 {agentConversations.length}건</span>
            </div>
            <div className="ops-agent-quick-actions" aria-label="분석 보고서 Agent 빠른 작업">
              <button
                type="button"
                data-agent-analysis-start="true"
                onClick={() => onAgentMessageDraft("현재 선택한 업무 맥락, 첨부 가능한 BoI, Sandbox artifact, Data Lake source를 기준으로 분석 계획을 세워줘. 실행 전 필요한 근거와 확인 절차도 함께 알려줘.")}
              >
                분석 시작
              </button>
              <button
                type="button"
                data-agent-report-create="true"
                onClick={() => onAgentMessageDraft("현재 분석 근거와 업무 맥락을 바탕으로 시각화가 포함된 보고서 BoI 초안을 만들어줘. 결론, 판단 근거, 한계, 권장 조치를 구분해줘.")}
              >
                보고서 만들기
              </button>
              <button
                type="button"
                data-agent-chart-add="true"
                onClick={() => onAgentMessageDraft("판단에 도움이 되는 차트 후보를 제안하고, 각 차트에 필요한 데이터와 Sandbox에서 생성할 artifact를 알려줘.")}
              >
                차트 추가
              </button>
            </div>
            <div className="ops-agent-source-chips" aria-label="분석 대상">
              <span>현재 SOP/보고서</span>
              <span>Sandbox artifact</span>
              <span>Data Lake source</span>
              <span>BoI 문서</span>
            </div>
            <div className="ops-agent-actions">
              <button type="button" data-agent-new-conversation="true" onClick={onNewAgentConversation}>새 대화</button>
              <button type="button" data-agent-ingest-conversation="true" onClick={onIngestAgentConversation} disabled={!selectedConversation}>BoI Wiki로 저장</button>
              <button type="button" onClick={onArchiveAgentConversation} disabled={!selectedConversation}>대화 보관</button>
            </div>
            {agentActionState && <p className="ops-agent-action-status">{agentActionState}</p>}
          </section>
          <section className="ops-drawer-section">
            <h3>대화 목록</h3>
            <div className="ops-agent-conversation-list" data-agent-conversation-list="true">
              {agentConversations.map((conversation) => (
                <button
                  type="button"
                  key={conversation.conversation_id}
                  className={conversation.conversation_id === selectedConversation?.conversation_id ? "selected" : ""}
                  onClick={() => onSelectAgentConversation(conversation.conversation_id)}
                >
                  <strong>{conversation.title || "Agent 대화"}</strong>
                  <small>{conversation.message_count || 0}건 · {conversation.updated_at || "시간 확인"}</small>
                  {conversation.latest_message && <span>{conversation.latest_message}</span>}
                </button>
              ))}
              {!agentConversations.length && <p>아직 대화가 없습니다. 새 대화를 시작하세요.</p>}
            </div>
          </section>
          <section className="ops-drawer-section">
            <h3>Agent 대화</h3>
            <div className="ops-agent-chat" data-agent-chat="true">
              <div className="ops-agent-messages">
                {activeMessages.map((message, index) => (
                  <article className={cx("ops-agent-message", message.role === "user" && "user")} key={`${message.role}:${message.created_at || index}`}>
                    <span>{message.role === "user" ? "You" : "Agent"}</span>
                    <p>{message.content}</p>
                  </article>
                ))}
                {!activeMessages.length && <p className="ops-agent-empty">질문을 입력하면 이 Agent가 현재 업무 맥락을 기준으로 답합니다.</p>}
              </div>
              <textarea
                value={agentMessageDraft}
                onChange={(event) => onAgentMessageDraft(event.target.value)}
                placeholder="이 Agent에게 요청할 내용을 입력하세요."
                rows={3}
              />
              <button type="button" data-agent-send-message="true" onClick={onSendAgentMessage} disabled={!agentMessageDraft.trim()}>
                Agent에게 보내기
              </button>
            </div>
          </section>
          <section className="ops-drawer-section">
            <h3>업무 연결</h3>
            <p>대화에서 나온 결정 근거나 산출물은 BoI Wiki로 저장한 뒤 SOP, 보고서, Event, Action 연결 후보로 재사용합니다.</p>
          </section>
        </>
      ) : state.mode === "evidence" ? (
        <>
          <section className="ops-drawer-section">
            <h3>Computational Evidence Workspace</h3>
            <p>Sandbox에서 생성된 계산 근거, 표, 보고서 artifact를 확인하고 검증된 결과만 업무 판단 근거로 채택합니다.</p>
            <div className="ops-focus-points">
              <span>source/code/runtime/output 추적</span>
              <span>GPT-5.5 요약</span>
              <span>사용자 확인 후 채택</span>
            </div>
          </section>
          <section className="ops-drawer-section">
            <h3>최근 Sandbox 결과</h3>
            {sandboxLoading ? (
              <div className="ops-loading">Sandbox 결과를 불러오는 중입니다.</div>
            ) : (
              <SandboxJobList
                jobs={visibleSandboxJobs}
                actionState={sandboxActionState}
                onAdopt={onAdoptSandboxEvidence}
                onAttach={onAttachSandboxEvidence}
              />
            )}
          </section>
          <section className="ops-drawer-section">
            <h3>보고서 반영 기준</h3>
            <p>검증된 evidence는 원본 raw data를 본문에 넣지 않고 artifact link, 실행 코드, validation result와 함께 Inbox report에 연결합니다.</p>
          </section>
        </>
      ) : state.mode === "workstream" ? (
        <>
          <section className="ops-drawer-section">
            <h3>요약</h3>
            <p>{state.workstream?.count || 0}건의 열린 업무가 이 SOP에 연결되어 있습니다. Canvas에는 대표 상태만 표시하고, 개별 차이는 아래에서 비교합니다.</p>
            <div className="ops-focus-points">
              <span>{riskLabel[state.workstream?.risk || "normal"]}</span>
              {(state.workstream?.badges || []).slice(0, 4).map((badge) => <span key={badge}>{badge}</span>)}
            </div>
          </section>
          <section className="ops-drawer-section">
            <h3>개별 항목</h3>
            <div className="ops-workstream-items">
              {workstreamItems.map((item) => (
                <button type="button" key={item.run_id} onClick={() => onSelectRun(item)}>
                  <span>{item.occurred_label || "시간 확인"} · {item.target || "대상 확인"}</span>
                  <strong>{item.stage || item.status_line || "단계 확인"}</strong>
                  <small>{item.focus_note || item.business_brief || "확인할 내용을 불러오세요."}</small>
                </button>
              ))}
              {!workstreamItems.length && <p>이 SOP에 연결된 개별 업무가 없습니다.</p>}
            </div>
          </section>
          <section className="ops-drawer-section">
            <h3>특이사항</h3>
            <p>{(state.workstream?.badges || []).length ? "승인, 근거 부족, 지연, Action 실패 같은 집중 항목만 먼저 확인하세요." : "현재 강조할 특이사항은 없습니다."}</p>
          </section>
          <section className="ops-drawer-section">
            <h3>다음 조치</h3>
            <p>개별 항목을 선택하면 현재 단계, 확보 근거, 부족 근거, 승인/반려 버튼을 이 패널에서 바로 확인합니다.</p>
          </section>
        </>
      ) : (
        <>
          <section className="ops-drawer-section">
            <h3>현재 단계</h3>
            <p>{String(run.current_stage_label || context?.stage_state?.label || state.preview?.stage || "단계 확인 필요")}</p>
            <div className="ops-focus-points">
              {(focus.length ? focus : ["특이사항 없음"]).map((item) => <span key={item}>{item}</span>)}
            </div>
          </section>
          <section className="ops-drawer-section">
            <h3>왜 나에게 왔나</h3>
            <p>{decision?.why_assigned || `${state.title}의 현재 단계에서 확인이 필요합니다.`}</p>
          </section>
          <section className="ops-drawer-section">
            <h3>업무 맥락</h3>
            <dl className="ops-context-kv">
              {Object.entries(business).slice(0, 8).map(([key, value]) => (
                <React.Fragment key={key}>
                  <dt>{key}</dt>
                  <dd>{formatContextValue(value)}</dd>
                </React.Fragment>
              ))}
              {!Object.keys(business).length && (
                <>
                  <dt>요약</dt>
                  <dd>{state.preview?.business_brief || state.preview?.target || "업무 맥락 확인 필요"}</dd>
                </>
              )}
            </dl>
          </section>
          <section className="ops-drawer-section">
            <h3>확보 근거 / 부족 근거</h3>
            <div className="ops-evidence-list">
              {evidence.map((item) => (
                <article className={cx("ops-evidence-card", item.state === "missing" && "missing")} key={`${item.kind}:${item.label}`}>
                  <strong>{item.label}</strong>
                  <span>{item.state === "missing" ? item.missing_reason || "확인 필요" : "확보됨"}</span>
                </article>
              ))}
              {!evidence.length && <p>선택한 업무의 근거 목록을 불러온 뒤 표시합니다.</p>}
            </div>
          </section>
          <section className="ops-drawer-section">
            <h3>의사결정 흐름</h3>
            <p>{decision?.recommended_action || state.preview?.focus_note || "검증 보고서 확인 후 승인/반려/보류를 결정하세요."}</p>
            <div className="ops-decision-flow">
              <button type="button">보고서 보기</button>
              <button type="button">승인</button>
              <button type="button">반려</button>
              <button type="button">보류</button>
              <button type="button">추가 근거 요청</button>
            </div>
            <div className="ops-report-links">
              {links.map((link) => link.url && <a key={`${link.label}:${link.url}`} href={link.url}>{link.label}</a>)}
              {state.preview?.url && <a href={state.preview.url}>SOP Lens 열기</a>}
            </div>
          </section>
        </>
      )}
    </aside>
  );
}

function OpsCenter() {
  const bootstrap = useMemo(readBootstrap, []);
  const [canvas, setCanvas] = useState<OpsCanvasPayload | null>(
    bootstrap.initialCanvas ? normalizeCanvas(bootstrap.initialCanvas) : null
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(canvas?.nodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(canvas?.edges || []);
  const [drawer, setDrawer] = useState<DrawerState>({
    mode: "summary",
    title: "BoI Operations Center",
    subtitle: "나에게 들어온 SOP, Agent, Evidence 흐름을 선택하세요."
  });
  const [context, setContext] = useState<SopRunContext | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [sandboxJobs, setSandboxJobs] = useState<SandboxJobSummary[]>([]);
  const [sandboxLoading, setSandboxLoading] = useState(false);
  const [sandboxActionState, setSandboxActionState] = useState<Record<string, string>>({});
  const [agentConversations, setAgentConversations] = useState<AgentConversationSummary[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [agentMessageDraft, setAgentMessageDraft] = useState("");
  const [agentActionState, setAgentActionState] = useState("");

  const fetchSandboxJobs = useCallback(async () => {
    setSandboxLoading(true);
    try {
      const response = await fetch(`/api/agents/sandbox/jobs?employee_id=${encodeURIComponent(bootstrap.employeeId)}&limit=8`, {
        headers: { Accept: "application/json" }
      });
      if (response.ok) {
        const payload = await response.json();
        setSandboxJobs(Array.isArray(payload.items) ? payload.items : []);
      }
    } finally {
      setSandboxLoading(false);
    }
  }, [bootstrap.employeeId]);

  const setSandboxJobStatus = useCallback((jobId: string, message: string) => {
    setSandboxActionState((current) => ({ ...current, [jobId]: message }));
  }, []);

  const adoptSandboxEvidence = useCallback(async (job: SandboxJobSummary) => {
    if (!job.job_id) return;
    setSandboxJobStatus(job.job_id, "검증 근거 채택을 기록하는 중입니다.");
    try {
      const response = await fetch(`/api/agents/sandbox/jobs/${encodeURIComponent(job.job_id)}/adopt-evidence?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          evidence_state: "verified_evidence",
          validation_note: "Operations Center에서 source/code/runtime/output과 artifact를 확인했습니다.",
          source_refs: (job.artifacts || []).map((artifact) => ({ type: "sandbox_artifact", job_id: job.job_id, path: artifact.path })),
          user_confirmed: true
        })
      });
      if (!response.ok) throw new Error(`adopt failed: ${response.status}`);
      setSandboxJobStatus(job.job_id, "검증 근거로 채택했습니다.");
      await fetchSandboxJobs();
    } catch (error) {
      setSandboxJobStatus(job.job_id, `근거 채택 실패: ${String((error as Error).message || error)}`);
    }
  }, [bootstrap.employeeId, fetchSandboxJobs, setSandboxJobStatus]);

  const attachSandboxEvidence = useCallback(async (job: SandboxJobSummary) => {
    if (!job.job_id) return;
    const reportId = context?.report_target?.report_id || drawer.runId || "ops-center-evidence";
    setSandboxJobStatus(job.job_id, "보고서에 근거를 연결하는 중입니다.");
    try {
      const response = await fetch(`/api/inbox/reports/${encodeURIComponent(reportId)}/attach-evidence?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          evidence_refs: [
            {
              type: "sandbox_job",
              id: job.job_id,
              title: job.title,
              artifact_count: (job.artifacts || []).length
            }
          ],
          note: `Operations Center에서 ${job.title || job.job_id} sandbox 결과를 보고서 근거로 연결했습니다.`,
          user_confirmed: true
        })
      });
      if (!response.ok) throw new Error(`attach failed: ${response.status}`);
      setSandboxJobStatus(job.job_id, `보고서 ${reportId}에 연결했습니다.`);
    } catch (error) {
      setSandboxJobStatus(job.job_id, `보고서 반영 실패: ${String((error as Error).message || error)}`);
    }
  }, [bootstrap.employeeId, context?.report_target?.report_id, drawer.runId, setSandboxJobStatus]);

  const selectRun = useCallback(async (item: OpsRunPreview) => {
    setDrawer({
      mode: "run",
      title: item.sop_title || "SOP Run",
      subtitle: `${item.occurred_label || ""} ${item.target || ""}`.trim(),
      runId: item.run_id,
      preview: item
    });
    setContext(null);
    if (!item.run_id) return;
    setContextLoading(true);
    try {
      const response = await fetch(`/api/sop-runs/${encodeURIComponent(item.run_id)}/context?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
        headers: { Accept: "application/json" }
      });
      if (response.ok) {
        setContext((await response.json()) as SopRunContext);
      }
    } finally {
      setContextLoading(false);
    }
  }, [bootstrap.employeeId]);

  const fetchAgentConversations = useCallback(async (agentId: string, nextSelectedId = "") => {
    if (!agentId) return;
    setAgentActionState("대화 목록을 불러오는 중입니다.");
    try {
      const response = await fetch(`/api/agents/${encodeURIComponent(agentId)}/conversations?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
        headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error(`conversation list failed: ${response.status}`);
      const payload = await response.json();
      const items = Array.isArray(payload.items) ? payload.items as AgentConversationSummary[] : [];
      setAgentConversations(items);
      setSelectedConversationId(nextSelectedId || items[0]?.conversation_id || "");
      setAgentActionState("");
    } catch (error) {
      setAgentActionState(`대화 목록을 불러오지 못했습니다: ${String((error as Error).message || error)}`);
    }
  }, [bootstrap.employeeId]);

  const selectAgent = useCallback((agent: OpsAgentNodeData, nodeId: string, selectedConversation = "") => {
    setDrawer({
      mode: "agent",
      title: String(agent.label || agent.title || "Agent"),
      subtitle: String(agent.subtitle || agent.description || "내 상황실에 연결된 Agent"),
      nodeId,
      agent
    });
    setContext(null);
    setAgentConversations(Array.isArray(agent.conversations) ? agent.conversations : []);
    setSelectedConversationId(selectedConversation || (Array.isArray(agent.conversations) ? agent.conversations[0]?.conversation_id || "" : ""));
    setAgentMessageDraft("");
    fetchAgentConversations(String(agent.agent_id || ""), selectedConversation);
  }, [fetchAgentConversations]);

  const createAgentConversation = useCallback(async () => {
    const agentId = String(drawer.agent?.agent_id || "");
    if (!agentId) return;
    setAgentActionState("새 대화를 만드는 중입니다.");
    try {
      const response = await fetch(`/api/agents/${encodeURIComponent(agentId)}/conversations?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ title: "새 Agent 대화", context: { source: "ops_center" } })
      });
      if (!response.ok) throw new Error(`conversation create failed: ${response.status}`);
      const payload = await response.json();
      const conversationId = String(payload.conversation?.conversation_id || "");
      await fetchAgentConversations(agentId, conversationId);
      setAgentActionState("새 대화를 만들었습니다.");
    } catch (error) {
      setAgentActionState(`새 대화 생성 실패: ${String((error as Error).message || error)}`);
    }
  }, [bootstrap.employeeId, drawer.agent?.agent_id, fetchAgentConversations]);

  const sendAgentMessage = useCallback(async () => {
    const agentId = String(drawer.agent?.agent_id || "");
    if (!agentId || !agentMessageDraft.trim()) return;
    let conversationId = selectedConversationId;
    try {
      if (!conversationId) {
        const createResponse = await fetch(`/api/agents/${encodeURIComponent(agentId)}/conversations?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ title: agentMessageDraft.trim().slice(0, 40), context: { source: "ops_center" } })
        });
        if (!createResponse.ok) throw new Error(`conversation create failed: ${createResponse.status}`);
        const created = await createResponse.json();
        conversationId = String(created.conversation?.conversation_id || "");
      }
      setAgentActionState("Agent가 답변하는 중입니다.");
      const response = await fetch(`/api/agents/${encodeURIComponent(agentId)}/conversations/${encodeURIComponent(conversationId)}/messages?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          message: agentMessageDraft.trim(),
          context: { source: "ops_center", node_id: drawer.nodeId }
        })
      });
      if (!response.ok) throw new Error(`message failed: ${response.status}`);
      setAgentMessageDraft("");
      await fetchAgentConversations(agentId, conversationId);
      setAgentActionState("답변을 받았습니다.");
    } catch (error) {
      setAgentActionState(`메시지 전송 실패: ${String((error as Error).message || error)}`);
    }
  }, [agentMessageDraft, bootstrap.employeeId, drawer.agent?.agent_id, drawer.nodeId, fetchAgentConversations, selectedConversationId]);

  const ingestAgentConversation = useCallback(async () => {
    const conversationId = selectedConversationId || agentConversations[0]?.conversation_id || "";
    if (!conversationId) return;
    setAgentActionState("대화를 BoI Wiki에 저장하는 중입니다.");
    try {
      const response = await fetch(`/api/agents/conversations/${encodeURIComponent(conversationId)}/ingest-to-boi?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          title: drawer.title ? `${drawer.title} 대화 기록` : "Agent 대화 기록",
          visibility: "private",
          user_confirmed: true
        })
      });
      if (!response.ok) throw new Error(`ingest failed: ${response.status}`);
      const payload = await response.json();
      setAgentActionState(payload.doc_url ? `BoI Wiki에 저장했습니다: ${payload.doc_url}` : "BoI Wiki에 저장했습니다.");
    } catch (error) {
      setAgentActionState(`BoI 저장 실패: ${String((error as Error).message || error)}`);
    }
  }, [agentConversations, bootstrap.employeeId, drawer.title, selectedConversationId]);

  const archiveAgentConversation = useCallback(async () => {
    const agentId = String(drawer.agent?.agent_id || "");
    const conversationId = selectedConversationId || agentConversations[0]?.conversation_id || "";
    if (!agentId || !conversationId) return;
    setAgentActionState("대화를 보관하는 중입니다.");
    try {
      const response = await fetch(`/api/agents/${encodeURIComponent(agentId)}/conversations/${encodeURIComponent(conversationId)}/archive?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ user_confirmed: true })
      });
      if (!response.ok) throw new Error(`archive failed: ${response.status}`);
      await fetchAgentConversations(agentId);
      setAgentActionState("대화를 보관했습니다.");
    } catch (error) {
      setAgentActionState(`대화 보관 실패: ${String((error as Error).message || error)}`);
    }
  }, [agentConversations, bootstrap.employeeId, drawer.agent?.agent_id, fetchAgentConversations, selectedConversationId]);

  const fetchCanvas = useCallback(async () => {
    const response = await fetch(`/api/ops/canvas?employee_id=${encodeURIComponent(bootstrap.employeeId)}`, {
      headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error(`ops canvas failed: ${response.status}`);
    const nextCanvas = normalizeCanvas((await response.json()) as OpsCanvasPayload);
    setCanvas(nextCanvas);
    setNodes(nextCanvas.nodes);
    setEdges(nextCanvas.edges);
  }, [bootstrap.employeeId, setEdges, setNodes]);

  useEffect(() => {
    fetchCanvas().catch((_error) => {
      // Initial bootstrap still keeps the page useful; health UI can expose failures separately.
    });
  }, [fetchCanvas]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.type === "sopWorkstreamNode") {
      const workstream = node.data as OpsWorkstreamNodeData;
      setDrawer({
        mode: "workstream",
        title: String(workstream.label || "SOP Workstream"),
        subtitle: `${workstream.count || 0}건 · ${riskLabel[workstream.risk || "normal"]}`,
        nodeId: node.id,
        workstream
      });
      setContext(null);
      return;
    }
    if (node.type === "agentNode") {
      selectAgent(node.data as OpsAgentNodeData, node.id);
      return;
    }
    if (node.type === "agentConversationNode") {
      const agentId = String(node.data?.agent_id || "");
      const sourceAgent = (canvas?.nodes || []).find((candidate) => candidate.type === "agentNode" && String(candidate.data?.agent_id || "") === agentId);
      if (sourceAgent) {
        selectAgent(sourceAgent.data as OpsAgentNodeData, sourceAgent.id, String(node.data?.conversation_id || ""));
      }
      return;
    }
    if (node.type === "evidenceNode" || node.type === "sandboxJobNode") {
      const latestJobs = Array.isArray(node.data?.latest_jobs) ? node.data.latest_jobs as SandboxJobSummary[] : [];
      setDrawer({
        mode: "evidence",
        title: String(node.data?.label || "Computational Evidence"),
        subtitle: String(node.data?.subtitle || "Sandbox 결과와 검증 근거"),
        nodeId: node.id,
        sandboxJobs: latestJobs
      });
      setContext(null);
      fetchSandboxJobs();
      return;
    }
    setDrawer({
      mode: node.type === "decisionNode" ? "decision" : "summary",
      title: String(node.data?.label || "상세"),
      subtitle: String(node.data?.subtitle || ""),
      nodeId: node.id
    });
  }, [canvas?.nodes, fetchSandboxJobs, selectAgent]);

  const onPaneClick = useCallback((event: React.MouseEvent) => {
    const target = event.target as HTMLElement;
    const runButton = target.closest("[data-run-preview]") as HTMLElement | null;
    if (runButton?.dataset.runId && canvas) {
      const allPreviews = [
        ...(canvas.focus_queue || []),
        ...(canvas.nodes || []).flatMap((node) => (node.data?.preview_items || []) as OpsRunPreview[])
      ];
      const item = allPreviews.find((preview) => preview.run_id === runButton.dataset.runId);
      if (item) selectRun(item);
    }
  }, [canvas, selectRun]);

  const changeDrawerMode = useCallback((mode: DrawerMode) => {
    if (mode === "evidence") {
      fetchSandboxJobs();
    }
    setDrawer((current) => ({ ...current, mode }));
  }, [fetchSandboxJobs]);

  const summary = canvas?.summary || { open_count: 0, approval_required: 0, missing_evidence: 0, delay_risk: 0 };
  const selectedRunId = drawer.runId || canvas?.selected_run_id;

  return (
    <div className="ops-center-shell">
      <section className="ops-center-topbar">
        <div>
          <span>BoI Operations Center</span>
          <h1>{bootstrap.employeeId} 중심 업무 상황실</h1>
        </div>
        <div className="ops-center-metrics">
          <strong>열린 업무 {summary.open_count}</strong>
          <strong>승인 필요 {summary.approval_required}</strong>
          <strong>근거 부족 {summary.missing_evidence}</strong>
          <strong>지연 위험 {summary.delay_risk}</strong>
          <strong>Agent 작업 {summary.agent_jobs || 0}</strong>
        </div>
      </section>

      <section className="ops-center-layout">
        <FocusQueue
          items={canvas?.focus_queue || []}
          selectedRunId={selectedRunId}
          onSelect={selectRun}
        />
        <section className="ops-flow-panel" onClick={onPaneClick}>
          <ReactFlowProvider>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              fitView
              fitViewOptions={{ padding: 0.12, minZoom: 0.72, maxZoom: 1.05 }}
              minZoom={0.55}
              maxZoom={1.4}
              nodesDraggable={false}
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={24} size={1} color="#dbe5f2" />
              <Controls position="bottom-left" />
              <MiniMap
                position="bottom-right"
                pannable
                zoomable
                nodeColor={(node) => node.type === "personNode" ? "#111827" : node.type === "agentNode" ? "#7c3aed" : nodeRiskClass(node.data?.risk).includes("high") ? "#ef4444" : "#2563eb"}
              />
              <Panel position="top-left" className="ops-flow-panel-toolbar">
                <button type="button" className="active">Map</button>
                <button type="button">Queue</button>
                <button type="button">Table</button>
                <button type="button" onClick={() => fetchCanvas()}>새로고침</button>
              </Panel>
            </ReactFlow>
          </ReactFlowProvider>
        </section>
        <ContextDrawer
          state={drawer}
          context={context}
          sandboxJobs={sandboxJobs}
          agentConversations={agentConversations}
          selectedConversationId={selectedConversationId}
          agentMessageDraft={agentMessageDraft}
          agentActionState={agentActionState}
          sandboxActionState={sandboxActionState}
          loading={contextLoading}
          sandboxLoading={sandboxLoading}
          onMode={changeDrawerMode}
          onSelectRun={selectRun}
          onNewAgentConversation={createAgentConversation}
          onSelectAgentConversation={setSelectedConversationId}
          onAgentMessageDraft={setAgentMessageDraft}
          onSendAgentMessage={sendAgentMessage}
          onIngestAgentConversation={ingestAgentConversation}
          onArchiveAgentConversation={archiveAgentConversation}
          onAdoptSandboxEvidence={adoptSandboxEvidence}
          onAttachSandboxEvidence={attachSandboxEvidence}
        />
      </section>
      <section className="ops-timeline-strip">
        <strong>최근 활동</strong>
        <span>보고서, 승인, 근거 채택, Agent 작업은 이 영역에서 시간순으로 이어집니다.</span>
        <small>performance: {String(canvas?.performance?.source || "loading")}</small>
      </section>
    </div>
  );
}

createRoot(document.getElementById("boi-ops-center") as HTMLElement).render(<OpsCenter />);
