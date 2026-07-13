import { Catalog, MessageProcessor, type SurfaceModel } from "@a2ui/web_core/v0_9";
import { A2uiController, A2uiLitElement, A2uiSurface, basicCatalog, type LitComponentApi } from "@a2ui/lit/v0_9";
import { css, html, nothing, type PropertyValues } from "lit";
import { unsafeHTML } from "lit/directives/unsafe-html.js";
import { z } from "zod";

const protocolVersion = "0.9.1";
const messageVersion = "v0.9";
const compatibilityCatalogId = "boi-a2ui/v1";
const catalogId = "/api/v2/a2ui/catalogs/boi/v1";
const componentNames = [
  "Answer", "CitationList", "EvidencePicker", "WorkRecordForm", "DecisionSummary",
  "TaskStatus", "Timeline", "DataTable", "MermaidArtifact", "OntologyExplorer",
  "ActionPreview", "Confirmation", "RelatedQuestions",
] as const;
const componentSet = new Set<string>(componentNames);
const legacy = (window as unknown as { BoiA2UI?: LegacyRenderer }).BoiA2UI;

class BoiRuntimeSurface extends A2uiSurface {
  createRenderRoot() { return this; }
}
if (!customElements.get("boi-a2ui-runtime-surface")) {
  customElements.define("boi-a2ui-runtime-surface", BoiRuntimeSurface);
}

type LegacySurface = {
  surface_id: string;
  protocol_version: string;
  catalog_id: string;
  canonical_catalog_id?: string;
  components: Array<{ id: string; component: string; props?: Record<string, unknown> }>;
  messages?: Array<Record<string, unknown>>;
  events?: unknown[];
};
type LegacyRenderer = {
  validate?: (surface: LegacySurface) => LegacySurface | null;
  hydrate?: (surface: LegacySurface, root?: ParentNode) => boolean;
  ontologyExplorerMarkup?: () => string;
};

const broadSchema = z.object({}).passthrough();

function text(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function safeInternalUrl(value: unknown): string {
  const target = text(value);
  return target.startsWith("/") || target.startsWith("#") ? target : "";
}

class BoiSurfaceElement extends A2uiLitElement<any> {
  static styles = css`:host { display: grid; gap: 12px; min-width: 0; }`;
  protected createController() { return new A2uiController(this, boiSurfaceApi as any); }
  createRenderRoot() { return this; }
  render() {
    const children = Array.isArray(this.controller.props?.children) ? this.controller.props.children : [];
    return html`${children.map((child: string) => this.renderNode(child))}`;
  }
}
if (!customElements.get("boi-a2ui-surface")) customElements.define("boi-a2ui-surface", BoiSurfaceElement);
const boiSurfaceApi: LitComponentApi = { name: "BoiSurface", tagName: "boi-a2ui-surface", schema: broadSchema };

class BoiResultElement extends A2uiLitElement<any> {
  static componentName = "Answer";
  static styles = css`:host { display: block; min-width: 0; }`;
  protected createController() { return new A2uiController(this, componentApis.get((this.constructor as typeof BoiResultElement).componentName)! as any); }
  createRenderRoot() { return this; }

  private updateData(name: string, value: string) {
    this.context.dataContext.surface.dataModel.set(`/workRecord/${name}`, value);
  }

  private dispatch(name: string, detail: Record<string, unknown>) {
    void this.context.dataContext.surface.dispatchAction({ name, context: detail }, this.context.componentModel.id);
    this.dispatchEvent(new CustomEvent(name === "confirm" ? "boi:a2ui-confirm-request" : "boi:a2ui-question", {
      bubbles: true,
      composed: true,
      detail,
    }));
  }

  protected updated(_changes: PropertyValues) {
    const name = (this.constructor as typeof BoiResultElement).componentName;
    this.dataset.a2uiComponent = name;
    this.dataset.a2uiComponentId = String(this.context.componentModel.id || "");
    if (!["Timeline", "DataTable", "MermaidArtifact", "OntologyExplorer", "ActionPreview"].includes(name)) return;
    const mount = this.querySelector<HTMLElement>("[data-a2ui-domain-mount]");
    if (!mount || mount.dataset.hydrated === "true" || !legacy?.hydrate) return;
    mount.dataset.hydrated = "true";
    const props = this.controller.props || {};
    legacy.hydrate({
      surface_id: `domain-${this.context.componentModel.id}`,
      protocol_version: protocolVersion,
      catalog_id: compatibilityCatalogId,
      components: [{ id: this.context.componentModel.id, component: name, props }],
      events: [],
    }, this);
  }

  render() {
    const name = (this.constructor as typeof BoiResultElement).componentName;
    const props = this.controller.props || {};
    if (name === "Answer") {
      const displayHtml = text(props.displayHtml);
      return html`<article class="a2ui-answer"><h3>${text(props.summary)}</h3><div class="a2ui-answer-body">${displayHtml ? unsafeHTML(displayHtml) : html`<p>${text(props.markdown) || text(props.summary)}</p>`}</div></article>`;
    }
    if (name === "CitationList") return html`<ol class="a2ui-citations">${(props.items || []).map((item: any, index: number) => {
      const href = safeInternalUrl(item.target_url || item.resolved_source?.canonical_url);
      return html`<li>${href ? html`<a href=${href}>${text(item.title) || `근거 ${index + 1}`}</a>` : html`<span>${text(item.title) || `근거 ${index + 1}`}</span>`}</li>`;
    })}</ol>`;
    if (name === "RelatedQuestions") return html`<div class="a2ui-related-questions">${(props.items || []).slice(0, 3).map((item: any) => html`<button type="button" class="button secondary" @click=${() => this.dispatch("question", item)}>${text(item.label || item.question)}</button>`)}</div>`;
    if (name === "DecisionSummary") return html`<article class="a2ui-decision-summary"><h3>${text(props.summary) || "판단 결과"}</h3><ul>${(props.items || []).map((item: any) => html`<li><strong>${text(item.label || item.summary)}</strong><span>${text(item.value)}</span></li>`)}</ul></article>`;
    if (name === "TaskStatus") return html`<article class="a2ui-task-status"><h3>${text(props.title) || "현재 Task"}</h3><p>${text(props.completion?.status_label || props.executionMode || "진행 중")}</p></article>`;
    if (name === "EvidencePicker") return html`<div class="a2ui-evidence-picker">${(props.items || []).map((item: any) => html`<section class=${item.available ? "available" : ""}><span>${text(item.status_label) || (item.available ? "확보됨" : "확인 필요")}</span><h3>${text(item.label) || "확인 자료"}</h3></section>`)}</div>`;
    if (name === "WorkRecordForm") {
      const submit = props.submit || {};
      const action = safeInternalUrl(submit.action);
      return html`<form class="a2ui-work-record-form" method=${text(submit.method || "POST")} action=${action || nothing} @submit=${(event: Event) => { if (!action) event.preventDefault(); }}>
        ${Object.entries(submit.hidden || {}).map(([fieldName, value]) => html`<input type="hidden" name=${fieldName} value=${text(value)} />`)}
        ${(props.fields || []).map((field: any) => html`<label>${text(field.label || field.name)}${field.control === "textarea" ? html`<textarea name=${text(field.name)} rows=${Number(field.rows || 3)} ?required=${Boolean(field.required)} placeholder=${text(field.placeholder)} @input=${(event: Event) => this.updateData(text(field.name), (event.target as HTMLTextAreaElement).value)}></textarea>` : html`<input name=${text(field.name)} ?required=${Boolean(field.required)} placeholder=${text(field.placeholder)} @input=${(event: Event) => this.updateData(text(field.name), (event.target as HTMLInputElement).value)} />`}</label>`)}
        ${action ? html`<button type="submit" class="button primary">${text(submit.label) || "업무 기록 저장"}</button>` : nothing}
      </form>`;
    }
    if (name === "Confirmation") return html`<article class="a2ui-confirmation"><h3>${text(props.title) || "실행 전 확인"}</h3><p>${text(props.message)}</p><button type="button" class="button primary" @click=${() => this.dispatch("confirm", { plan_ref: props.plan_ref })}>확인하고 계속</button></article>`;
    return html`<div data-a2ui-domain-mount=${name} data-a2ui-mount=${name}></div>`;
  }
}

const componentApis = new Map<string, LitComponentApi>();
for (const name of componentNames) {
  const tagName = `boi-a2ui-${name.replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase()}`;
  const api: LitComponentApi = { name, tagName, schema: broadSchema };
  componentApis.set(name, api);
  if (!customElements.get(tagName)) {
    class NamedResultElement extends BoiResultElement { static componentName = name; }
    customElements.define(tagName, NamedResultElement);
  }
}

const catalog = new Catalog<LitComponentApi>(catalogId, [boiSurfaceApi, ...componentApis.values(), ...basicCatalog.components.values()]);
const processor = new MessageProcessor<LitComponentApi>([catalog]);

function validate(surface: LegacySurface): LegacySurface | null {
  if (!surface || surface.protocol_version !== protocolVersion || !Array.isArray(surface.components) || (surface.events || []).length) return null;
  const ids = new Set<string>();
  for (const item of surface.components) {
    if (!item?.id || ids.has(item.id) || !componentSet.has(item.component)) return null;
    ids.add(item.id);
  }
  const messages = Array.isArray(surface.messages) ? surface.messages : [];
  if (messages.length && messages.some((message) => message.version !== messageVersion)) return null;
  return surface;
}

function legacyToMessages(surface: LegacySurface): Array<Record<string, any>> {
  if (surface.messages?.length) return surface.messages;
  const components = [
    { id: "root", component: "BoiSurface", children: surface.components.map((item) => item.id) },
    ...surface.components.map((item) => ({ id: item.id, component: item.component, ...(item.props || {}) })),
  ];
  return [
    { version: messageVersion, createSurface: { surfaceId: surface.surface_id, catalogId, sendDataModel: true } },
    { version: messageVersion, updateComponents: { surfaceId: surface.surface_id, components } },
    { version: messageVersion, updateDataModel: { surfaceId: surface.surface_id, path: "/", value: { surface: { id: surface.surface_id }, workRecord: {} } } },
  ];
}

function processSurface(surface: LegacySurface): SurfaceModel<LitComponentApi> | null {
  const trusted = validate(surface);
  if (!trusted) return null;
  const existing = processor.model.getSurface(trusted.surface_id);
  if (existing) processor.model.deleteSurface(trusted.surface_id);
  try {
    processor.processMessages(legacyToMessages(trusted) as any);
    return processor.model.getSurface(trusted.surface_id) || null;
  } catch (error) {
    console.error("BoI dynamic surface validation failed", error);
    return null;
  }
}

function hydrate(surface: LegacySurface, root: ParentNode = document): boolean {
  const model = processSurface(surface);
  if (!model) return legacy?.hydrate?.(surface, root) || false;
  const taskRoot = root instanceof HTMLElement && root.matches(".task-console-page") ? root : null;
  if (taskRoot) {
    const fallbackAnchor = taskRoot.querySelector<HTMLElement>(".task-console-work-record");
    if (!fallbackAnchor) return false;
    taskRoot.querySelectorAll("[data-boi-a2ui-official]").forEach((item) => item.remove());
    const host = document.createElement("section");
    host.dataset.boiA2uiOfficial = surface.surface_id;
    host.className = "task-console-section boi-a2ui-official-surface task-console-dynamic-work";
    const element = document.createElement("boi-a2ui-runtime-surface") as A2uiSurface;
    element.surface = model;
    host.appendChild(element);
    fallbackAnchor.before(host);
    [
      taskRoot.querySelector<HTMLElement>(".task-console-summary"),
      fallbackAnchor,
      taskRoot.querySelector<HTMLElement>(".task-console-required-evidence"),
    ].forEach((item) => {
      if (!item) return;
      item.hidden = true;
      item.dataset.a2uiFallbackHidden = "true";
    });
    taskRoot.dataset.a2uiRuntime = "official-v0.9";
    return true;
  }
  if (!(root instanceof HTMLElement)) return false;
  root.querySelectorAll("[data-boi-a2ui-official]").forEach((item) => item.remove());
  const host = document.createElement("div");
  host.dataset.boiA2uiOfficial = surface.surface_id;
  host.className = "boi-a2ui-official-surface";
  const element = document.createElement("boi-a2ui-runtime-surface") as A2uiSurface;
  element.surface = model;
  host.appendChild(element);
  root.appendChild(host);
  root instanceof HTMLElement && (root.dataset.a2uiRuntime = "official-v0.9");
  return true;
}

async function hydrateStored(root: HTMLElement): Promise<boolean> {
  const surfaceRef = root.dataset.a2uiSurfaceRef;
  if (!surfaceRef) return false;
  const employeeId = new URL(window.location.href).searchParams.get("employee_id") || "100001";
  try {
    const response = await fetch(`/api/v2/a2ui-surfaces/${encodeURIComponent(surfaceRef)}?employee_id=${encodeURIComponent(employeeId)}`, { headers: { Accept: "application/json" } });
    return response.ok ? hydrate(await response.json(), root) : false;
  } catch (_error) {
    return false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll<HTMLElement>("[data-a2ui-surface-ref]").forEach((root) => void hydrateStored(root));
});

(window as unknown as { BoiA2UI: Record<string, unknown> }).BoiA2UI = {
  validate,
  hydrate,
  hydrateStored,
  ontologyExplorerMarkup: legacy?.ontologyExplorerMarkup,
  catalogId: compatibilityCatalogId,
  canonicalCatalogId: catalogId,
  protocolVersion,
  messageVersion,
  processor,
};
