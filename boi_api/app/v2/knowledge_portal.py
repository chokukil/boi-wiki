"""Wiki presentation of authorized knowledge, packages and work.

The caller owns discovery and authorization. This module never fetches content,
runs an agent, changes review state, or treats a display label as authority.
"""
from __future__ import annotations

import base64
import hashlib
from collections import OrderedDict
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit


TABS = (("knowledge", "지식"), ("work", "내 작업"), ("inbox", "피드백 Inbox"), ("packages", "도메인 도구"))
STATUS_LABELS = {
    "published": "게시됨",
    "awaiting_confirmation": "전송 전 확인", "receiving": "전송 확인됨 · 상세에서 진행 확인",
    "PROVISIONAL": "검토 중인 지식", "candidate": "의미 후보", "pending": "검토 대기",
    "draft": "초안", "stored_without_review": "원문 연결 · 검토 대기",
    "unresolved_intake_review": "확인이 필요한 항목 있음", "available": "시작 가능",
    "claimed": "작업 준비 중", "running": "진행 중", "completed": "작업 단계 완료",
    "failed": "실패한 단계 있음", "unknown": "실행 결과 확인 필요",
    "outcome_unknown": "실행 결과 확인 필요", "blocked": "다음 작업 확인 필요",
    "ready": "사용 가능", "unsupported": "현재 지원되지 않음", "paused": "일시 중지",
    "cancelled": "중단됨", "pending_review": "검토 대기", "partial": "일부 완료",
    "waiting_external_agent": "외부 에이전트 작업 대기", "needs_attention": "확인이 필요한 항목 있음",
    "outputs_recorded": "결과 저장됨 · 의미 검토 별도", "stopped": "중단됨",
    "awaiting_external_result": "외부 에이전트 결과 대기", "produced": "결과 저장됨",
    "unresolved": "미해결", "not_configured": "연결 설정 필요",
    "supported": "정의된 작업 지원", "bounded": "지원 범위 제한",
}
KIND_LABELS = {
    "definition": "정의와 주장", "source": "원문", "profile": "의미 규격",
    "harness": "작업 절차", "skill": "에이전트 지침", "tool": "검증 도구",
    "composition": "답변 초안", "answer": "저장 답변", "formula": "계산식",
    "process": "공정", "svid": "SVID", "package": "도메인 도구",
}
COVERAGE_LABELS = (
    ("source_rows", "보존한 원문 항목"), ("meaning_candidates", "해석한 항목"),
    ("reviewed", "근거 검토한 항목"), ("explainable", "설명에 사용 가능"),
    ("executable", "계산에 사용 가능"), ("remaining", "남은 항목"),
    ("source_field_count", "보존한 원문 필드"), ("unit_count", "작업 묶음"),
    ("asset_reference_count", "저장된 결과 참조"),
)
OPERATION_LABELS = {"create": "새 지식", "reuse": "기존 지식 재사용", "revise": "지식 개정",
                    "conflict": "상충하는 해석", "unresolved": "미해결"}
PACKAGE_OPERATION_LABELS = {
    "source_preservation": "원문 보존", "meaning_proposal": "의미 제안", "task_resume": "작업 이어가기",
    "native_answer": "근거가 연결된 답변", "source_interpretation": "원문 해석", "definition_reuse": "정의 재사용",
    "source_review": "원문 검토", "descriptor_revision": "파라미터 설명 개정", "meaning_link_revision": "의미 관계 개정",
    "scoped_review": "범위를 정한 검토", "formula_preview": "계산 가능 여부 확인", "connection_discovery": "데이터 연결 찾기",
    "logical_plan": "논리 조회 계획", "native_query": "지원되는 조회 실행", "protected_result": "권한에 따른 결과 조회",
    "knowledge_reuse": "지식 재사용", "source_comparison": "원문 비교", "qualification_discovery": "검증 방법 확인",
}


def _text(value):
    return str(value) if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""


def _internal_url(value):
    """Navigation accepts only an actual application-relative link."""
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        return None
    if "\\" in value or any(ord(char) < 32 for char in value):
        return None
    parsed = urlsplit(value)
    return value if not parsed.scheme and not parsed.netloc else None


def _revision(value):
    if isinstance(value, dict):
        return _text(value.get("ref")), _text(value.get("revision_digest"))
    return _text(value), ""


def _revision_url(row):
    explicit = _internal_url(row.get("url") or row.get("ui_url") or row.get("result_url"))
    if explicit:
        return explicit
    ref, digest = _revision(row.get("revision"))
    token = digest.removeprefix("sha256:")
    if (row.get("kind") == "definition" and len(token) == 64
            and all(c in "0123456789abcdef" for c in token)
            and ref == "KnowledgeRevision:sha256:" + token):
        return ("/knowledge/records/" if row.get('status')=='published' else "/native-definitions/") + token
    return None


def _items(values):
    if isinstance(values, dict):
        values = values.get("items", [])
    return [value for value in values or () if isinstance(value, dict)]


def _limits(row):
    values = row.get("limitations") or ()
    if isinstance(values, str):
        values = [values]
    values = [_text(value) for value in values if _text(value)]
    coverage = row.get("coverage")
    if isinstance(coverage, dict):
        for key, expected, label in (
            ("semantic_review", "not_verified", "저장된 결과의 의미는 아직 검증되지 않았습니다."),
            ("scientific_truth", "not_established", "과학적 사실 여부는 별도 검토가 필요합니다."),
            ("computation_admission", "requires_native_execution_checks", "계산에는 단위, 역할, 데이터 연결 검증이 필요합니다."),
        ):
            if coverage.get(key) == expected:
                values.append(label)
    return values


def _work_results(row):
    results = []
    for value in _items(row.get("result_refs")):
        ref, _ = _revision(value.get("revision"))
        results.append({"label": OPERATION_LABELS.get(value.get("operation"), "저장된 결과"),
                        "reason": _text(value.get("reason")), "revision": ref,
                        "control": _control(row, asset_revisions=[value['revision']]) if ref else None,
                        "url": _revision_url({**value, "kind": "definition"})})
    return results


def _next_action(row):
    if row.get("contract_version") == "boi/knowledge-work@1":
        if row.get("active_attempt_ref"):
            return "외부 에이전트에서 예약된 실행 결과를 확인합니다. 같은 실행을 새로 시작하지 않습니다."
        if row.get("status") == "waiting_external_agent":
            return "외부 에이전트에서 이 작업을 이어갑니다."
        return "저장된 결과와 아직 확인하지 못한 범위를 살펴봅니다."
    return _text(row.get("next_action"))


def _control(row, *, unit_ids=(), asset_revisions=()):
    task_ref = _text(row.get('task_ref'))
    revision = row.get('revision')
    if not task_ref or type(revision) is not int or revision < 1:
        return None
    return {'task_ref': task_ref, 'expected_revision': revision,
            'unit_ids': list(unit_ids), 'asset_revisions': list(asset_revisions),
            'can_stop': row.get('status') != 'stopped'}


def _card(row):
    ref, digest = _revision(row.get("revision"))
    manifest = row.get("manifest") if isinstance(row.get("manifest"), dict) else {}
    status = _text(row.get("status") or row.get("capability_status") or manifest.get("capability_status"))
    operations = manifest.get("supported_operations", ())
    return {
        "title": _text(row.get("title") or row.get("name") or row.get("display_name") or manifest.get("display_name") or row.get("logical_id") or row.get("id") or ref) or "제목 없는 기록",
        "description": _text(row.get("description") or row.get("purpose") or manifest.get("description")),
        "snippet": _text(row.get("snippet")),
        "kind": KIND_LABELS.get(row.get("kind"), _text(row.get("kind"))),
        "domain": _text(row.get("domain")), "status": STATUS_LABELS.get(status, status),
        "url": _revision_url(row), "revision": ref, "revision_digest": digest,
        "limitations": _limits(row) + ([_text(manifest["capability_basis"])] if manifest.get("capability_basis") else []),
        "version": _text(row.get("version") or manifest.get("version") or manifest.get("kit_version")),
        "operations": [PACKAGE_OPERATION_LABELS.get(value, value) for value in operations if isinstance(value, str)]
                      if isinstance(operations, (list, tuple)) else [],
        "source_name": _text(row.get("source_name") or row.get("file_name")),
        "coverage": coverage_items(row.get("coverage")),
        "next_action": _next_action(row), "results": _work_results(row),
        "control": _control(row),
        "run_id": _text(row.get("run_id") or row.get("task_run_id") or row.get("task_ref")),
    }


def coverage_items(coverage):
    if not isinstance(coverage, dict):
        return []
    items = [{"label": label, "value": coverage[key]} for key, label in COVERAGE_LABELS
             if type(coverage.get(key)) is int and coverage[key] >= 0]
    states = coverage.get("unit_states")
    if isinstance(states, dict):
        items.extend({"label": "작업 · " + STATUS_LABELS.get(key, str(key)), "value": value}
                     for key, value in states.items() if type(value) is int and value >= 0)
    return items


def group_work_exceptions(work):
    """Group reported failures by their declared phase/code, without hiding rows."""
    groups = OrderedDict()
    for row in _items(work):
        units = {_text(unit.get("unit_id")): unit for unit in _items(row.get("units"))}
        exceptions = row.get("exceptions", ())
        if not isinstance(exceptions, (list, tuple)):
            continue
        for exception in exceptions:
            if not isinstance(exception, dict):
                continue
            phase = _text(exception.get("phase") or exception.get("stage"))
            code = _text(exception.get("reason_code") or exception.get("code") or exception.get("status"))
            key = (phase, code)
            group = groups.setdefault(key, {
                "phase": phase, "code": code, "items": [],
                "title": _text(exception.get("title")) or STATUS_LABELS.get(code, "확인이 필요한 항목"),
            })
            unit = units.get(_text(exception.get("unit_id")), {})
            locators = unit.get("record_locators", ())
            source = _text(exception.get("source_name") or exception.get("record_locator"))
            if not source and isinstance(locators, (list, tuple)):
                source = ", ".join(_text(locator) for locator in locators if _text(locator))
            group["items"].append({
                "message": _text(exception.get("message") or exception.get("reason")) or code,
                "source": source,
                "run_title": _text(row.get("title") or row.get("run_id") or row.get("task_run_id") or row.get("task_ref")),
                "url": _internal_url(exception.get("url")) or _revision_url(row),
                "next_action": _text(exception.get("next_action")),
                "control": _control(row, unit_ids=[exception['unit_id']]) if exception.get('unit_id') in units else None,
            })
    return list(groups.values())


def group_supervision_events(events):
    groups = OrderedDict()
    causes = {'source': '원문 정정', 'interpretation': '의미 해석 정정', 'coverage': '누락 범위 확인', 'other': '기타 정정'}
    scopes = {'task': '작업 전체', 'units': '선택한 원문 묶음', 'assets': '선택한 지식 개정', 'units_and_assets': '원문 묶음과 지식 개정'}
    for event in _items(events):
        if event.get('state') != 'pending':
            continue
        impact = event.get('impact') if isinstance(event.get('impact'), dict) else {}
        cause, scope = _text(event.get('cause_code')), _text(impact.get('target_scope'))
        group = groups.setdefault((cause, scope), {'cause': causes.get(cause, cause), 'scope': scopes.get(scope, scope), 'items': []})
        control = _control({'task_ref': event.get('task_ref'), 'revision': event.get('task_revision')})
        if control:
            control['event_ref'] = event.get('event_ref')
        group['items'].append({'reason': _text(event.get('reason')), 'control': control,
            'unit_count': impact.get('selected_unit_count') if type(impact.get('selected_unit_count')) is int else None,
            'asset_count': impact.get('selected_asset_count') if type(impact.get('selected_asset_count')) is int else None,
            'event_ref': _revision(event.get('event_ref'))[0]})
    return list(groups.values())


def portal_context(*, knowledge=(), packages=(), work=(), active_tab="knowledge", query="",
                   coverage=None, next_cursor=None, portal_url="/knowledge", package_capabilities=None,
                   supervision=(), supervision_enabled=False, bundle_next_url=None,scope='legacy',team=None,scope_options=(),text_search=None,
                   feedback=(), feedback_next_url=None):
    if active_tab not in {tab for tab, _ in TABS}:
        raise ValueError("KNOWLEDGE_PORTAL_TAB_INVALID")
    portal_url = _internal_url(portal_url)
    if not portal_url:
        raise ValueError("KNOWLEDGE_PORTAL_URL_INVALID")
    collections = {"knowledge": _items(knowledge), "packages": _items(packages), "work": _items(work), "inbox":[]}
    from .knowledge_published_view import render_feedback_inbox
    return {
        "active_tab": active_tab, "query": query, "portal_url": portal_url,
        "scope":scope,"team":team,"scope_options":scope_options,
        "text_search":text_search,
        "feedback_html":render_feedback_inbox(feedback) if active_tab=='inbox' else '',
        "feedback_next_url":_internal_url(feedback_next_url),
        "bundle_next_url":_internal_url(bundle_next_url),
        "tabs": [{"id": tab, "label": label, "url": portal_url + "?" + urlencode({"tab": tab}),
                  "active": tab == active_tab} for tab, label in TABS],
        "cards": [_card(row) for row in collections[active_tab]],
        "coverage": coverage_items(coverage), "exceptions": group_work_exceptions(work),
        "supervision_groups": group_supervision_events(supervision),
        "supervision_enabled": bool(supervision_enabled) and active_tab == 'work',
        "package_capabilities": {
            "available": package_capabilities.get("available") is True,
            "reason_code": _text(package_capabilities.get("reason_code")),
            "scope": _text(package_capabilities.get("qualification_scope")),
        } if isinstance(package_capabilities, dict) else None,
        "next_url": (portal_url + "?" + urlencode({"tab": active_tab, "q": query, "cursor": next_cursor,
                     'scope':scope,**({'team':team} if team else {})})
                     if isinstance(next_cursor, str) and next_cursor else None),
    }


class _ScriptHashes(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.parts = []
        self.hashes = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            if any(key == "src" for key, _ in attrs):
                raise ValueError("KNOWLEDGE_RECORD_EXTERNAL_SCRIPT_FORBIDDEN")
            self.active = True
            self.parts = []

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            self.hashes.append("'sha256-" + base64.b64encode(
                hashlib.sha256("".join(self.parts).encode()).digest()).decode() + "'")
            self.active = False


def portal_csp(fragment="", *, connect=False):
    scripts = _ScriptHashes()
    scripts.feed(fragment)
    return ("default-src 'none'; style-src 'self' 'unsafe-inline'; script-src "
            + (" ".join(dict.fromkeys(scripts.hashes)) if scripts.hashes else "'none'")
            + ("; connect-src 'self'" if connect else "")
            + "; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")


def _shell(shell_context_factory, request, principal, title, description=""):
    shell = shell_context_factory(request, principal.employee_id, active_nav="library", title=title,
                                  description=description, hide_pet_agent=True, mermaid_renderer_in_head=True)
    # The protected reader has already authenticated this principal. A legacy
    # directory cache or demo-user list is presentation data, not that identity.
    shell = {**shell, "employee_id": principal.employee_id}
    for field in ("display_name", "teams", "roles"):
        if hasattr(principal, field):
            shell[field] = getattr(principal, field)
    source = getattr(principal, "auth_source", None)
    shell["can_switch_identity"] = bool(shell.get("dev_mode") and source in (None, "dev"))
    if source in ("pat", "service_token"):
        shell.update(identity_auth_label="PAT" if source == "pat" else "Token", sso_active=False)
    if shell["can_switch_identity"]:
        users = list(shell.get("dev_users", []))
        if not any(user["employee_id"] == principal.employee_id for user in users):
            users.append({"employee_id": principal.employee_id, "label": principal.employee_id})
        shell["dev_users"] = users
    # Explicitly avoid bringing the in-page model/chat surface into the portal.
    return {**shell, "hide_pet_agent": True, "mermaid_renderer_in_head": True}


def render_knowledge_portal(templates, request, shell_context_factory, principal, **values):
    if 'supervision_enabled' not in values:
        from fastapi import HTTPException
        from .auth import require_scope
        try:
            require_scope(principal, 'boi.draft')
            values['supervision_enabled'] = True
        except (HTTPException, AttributeError):
            values['supervision_enabled'] = False
    context = portal_context(**values)
    script = SUPERVISION_SCRIPT if context['supervision_enabled'] else ''
    return templates.TemplateResponse("knowledge_portal.html", {
        "request": request, "employee_id": principal.employee_id,
        "shell": _shell(shell_context_factory, request, principal, "지식 자산", "원문에서 지식으로, 지식에서 업무로 이어집니다."),
        "portal": context, 'supervision_script': script,
    }, headers={"Cache-Control": "private, no-store", "Content-Security-Policy": portal_csp(script, connect=bool(script))})


def render_knowledge_record(templates, request, shell_context_factory, principal, *, title,
                            fragment, kind="definition", return_url=None, connect=False):
    """Wrap only a trusted, already sanitized native renderer's fragment."""
    relative_return = _internal_url(return_url)
    if not relative_return and isinstance(return_url, str):
        parsed, origin = urlsplit(return_url), urlsplit(str(request.url))
        if parsed.scheme == origin.scheme and parsed.netloc == origin.netloc:
            relative_return = _internal_url(parsed._replace(scheme="", netloc="").geturl())
    return templates.TemplateResponse("knowledge_portal_record.html", {
        "request": request, "employee_id": principal.employee_id,
        "shell": _shell(shell_context_factory, request, principal, title),
        "record_title": title, "record_kind": KIND_LABELS.get(kind, kind),
        "record_fragment": fragment, "return_url": relative_return,
    }, headers={"Cache-Control": "private, no-store", "Content-Security-Policy": portal_csp(fragment,connect=connect)})


SUPERVISION_SCRIPT = '''<script>
document.addEventListener('submit', async event => {
  const form = event.target;
  if (!form.matches('[data-knowledge-supervision]')) return;
  event.preventDefault();
  const status = form.querySelector('[role="status"]');
  const data = new FormData(form);
  const operation = data.get('operation');
  const request = {task_ref: form.dataset.taskRef, expected_revision: Number(data.get('expected_revision')),
    reason: data.get('reason'), idempotency_key: form.dataset.requestId || (crypto.randomUUID ? crypto.randomUUID() :
      Array.from(crypto.getRandomValues(new Uint8Array(16)), value => value.toString(16).padStart(2, '0')).join(''))};
  if (operation === 'correct') {
    request.unit_ids = JSON.parse(data.get('unit_ids') || '[]');
    request.asset_revisions = JSON.parse(data.get('asset_revisions') || '[]');
    request.cause_code = data.get('cause_code');
  }
  if (operation === 'resolve') request.event_ref = JSON.parse(data.get('event_ref'));
  const body = JSON.stringify({operation, request});
  if (form.dataset.pendingBody && form.dataset.pendingBody !== body) {
    status.textContent = '이전 요청의 결과가 확인되지 않았습니다. 같은 내용으로 상태를 확인해 주세요.';
    return;
  }
  form.dataset.requestId = request.idempotency_key;
  form.dataset.pendingBody = body;
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  status.textContent = '요청을 기록하고 있습니다.';
  try {
    const response = await fetch('/api/v2/knowledge-supervision', {
      method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-Requested-With': 'BoI-Wiki'}, body});
    const result = await response.json();
    if (!response.ok) {
      if (response.status < 500) { delete form.dataset.pendingBody; delete form.dataset.requestId; }
      throw new Error(result.detail?.reason_code || result.detail?.reason || '요청을 기록하지 못했습니다. 현재 작업 상태를 확인해 주세요.');
    }
    for (const other of document.querySelectorAll('[data-knowledge-supervision]')) {
      if (other.dataset.taskRef === request.task_ref && result.task_revision && !other.dataset.pendingBody)
        other.elements.expected_revision.value = result.task_revision;
    }
    status.textContent = operation === 'stop' ? '중단 요청을 기록했습니다. 진행 중인 실행 결과는 보존됩니다.' :
      operation === 'resolve' ? '처리 보고를 기록했습니다. 의미 검증 상태는 바뀌지 않습니다.' :
      '정정 요청을 기록했습니다. 외부 에이전트가 원래 기록과 함께 확인합니다.';
    const refresh = document.createElement('a');
    refresh.href = '/knowledge?tab=work';
    refresh.textContent = ' 현재 작업 상태 보기';
    status.append(refresh);
    if (operation === 'stop') {
      const label = form.closest('.knowledge-card')?.querySelector('[data-record-status]');
      if (label) label.textContent = '중단됨';
    }
    if (operation === 'resolve') {
      const heading = form.closest('section.knowledge-exceptions')?.querySelector('h2');
      if (heading) heading.textContent = '정정 요청과 처리 보고';
    }
    form.dataset.pendingBody = '';
  } catch (error) {
    status.textContent = error.message || '요청 결과를 확인하지 못했습니다. 같은 내용으로 다시 확인할 수 있습니다.';
    button.disabled = false;
  }
});
</script>'''
