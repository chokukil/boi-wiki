#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any


FORBIDDEN_VISIBLE_PATTERNS = [
    r"서로\s*다른\s*trace",
    r"\btrace\b",
    r"같은\s*Action",
    r"source_ids?",
    r"\b(?:event|action|boi|case):",
    r"\b(?:evt|act)-[A-Za-z0-9:_-]+",
    r"라우팅",
    r"처리\s*중",
    r"WorkflowDefinition",
    r"SOP,\s*실행\s*현황,\s*원본\s*기록",
]

REQUIRED_REPORT_SECTIONS = [
    "결론",
    "업무 맥락",
    "이전 단계 이력",
    "판단 준비도",
    "개별 비교",
    "판단 근거",
    "조치",
]


def visible_text_for_group(group: dict[str, Any]) -> str:
    narrative = group.get("group_narrative") if isinstance(group.get("group_narrative"), dict) else {}
    display = group.get("display") if isinstance(group.get("display"), dict) else {}
    chunks = [
        str(narrative.get("summary") or ""),
        str(narrative.get("priority_note") or ""),
        str(display.get("why_it_matters") or ""),
        str(display.get("next_action") or ""),
    ]
    for item in group.get("preview_items") or []:
        if not isinstance(item, dict):
            continue
        brief = item.get("brief") if isinstance(item.get("brief"), dict) else {}
        chunks.append(str(brief.get("unique_context") or ""))
        chunks.append(str(brief.get("next_check") or ""))
    return " ".join(chunks)


def normalized_key(value: str) -> str:
    return re.sub(r"[\s,.·:;/_-]+", "", value.strip().lower())[:90]


def check_group(group: dict[str, Any], *, require_multi_group_ready: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    count = int(group.get("count") or 0)
    narrative = group.get("group_narrative") if isinstance(group.get("group_narrative"), dict) else {}
    narrative_ready = narrative.get("state") == "ready" and narrative.get("narrative_quality") == "ready"
    if count > 1 or require_multi_group_ready:
        if not narrative_ready:
            message = f"{group.get('group_id')}: group narrative is not ready"
            if require_multi_group_ready:
                errors.append(message)
            else:
                warnings.append(message)
        if not str(narrative.get("summary") or "").strip():
            message = f"{group.get('group_id')}: group narrative summary is empty"
            if require_multi_group_ready:
                errors.append(message)
            else:
                warnings.append(message)
    text = visible_text_for_group(group)
    for pattern in FORBIDDEN_VISIBLE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            errors.append(f"{group.get('group_id')}: forbidden visible term matched {pattern!r}")
    preview_contexts: list[str] = []
    if not narrative_ready:
        return errors, warnings
    for item in group.get("preview_items") or []:
        if not isinstance(item, dict):
            continue
        brief = item.get("brief") if isinstance(item.get("brief"), dict) else {}
        unique_context = str(brief.get("unique_context") or "").strip()
        next_check = str(brief.get("next_check") or "").strip()
        if count > 1 and not unique_context:
            errors.append(f"{group.get('group_id')}: preview item is missing unique_context")
        if count > 1 and not next_check:
            errors.append(f"{group.get('group_id')}: preview item is missing next_check")
        if unique_context:
            preview_contexts.append(unique_context)
    keys = [normalized_key(value) for value in preview_contexts if normalized_key(value)]
    if len(keys) >= 2 and len(set(keys)) != len(keys):
        errors.append(f"{group.get('group_id')}: preview item contexts are repetitive")
    return errors, warnings


def fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def absolute_url(base_url: str, url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    return base_url.rstrip("/") + "/" + url.lstrip("/")


def html_to_visible_text(html: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def report_urls_from_inbox(body: dict[str, Any], *, limit: int) -> list[str]:
    urls: list[str] = []
    for entry in body.get("items") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("report_state") != "ready":
            continue
        url = str(entry.get("report_boi_url") or "")
        label = str(((entry.get("report_boi_link") or {}) if isinstance(entry.get("report_boi_link"), dict) else {}).get("label") or "")
        if url and (not label or label == "검증된 보고서 BoI"):
            urls.append(url)
        if len(urls) >= limit:
            return list(dict.fromkeys(urls))
    return list(dict.fromkeys(urls))


def check_report_document(url: str, html: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    visible = html_to_visible_text(html)
    for pattern in FORBIDDEN_VISIBLE_PATTERNS:
        if re.search(pattern, visible, flags=re.IGNORECASE):
            errors.append(f"{url}: forbidden visible term matched {pattern!r}")
    for pattern in (r"\btrace-[A-Za-z0-9_.:-]+", r"\bact-[A-Za-z0-9_.:-]+", r"source_id", r"\bschema\b"):
        if re.search(pattern, visible, flags=re.IGNORECASE):
            errors.append(f"{url}: forbidden report document term matched {pattern!r}")
    for section in REQUIRED_REPORT_SECTIONS:
        if section not in visible:
            errors.append(f"{url}: report document is missing required section {section!r}")
    if "검증된 보고서 BoI" not in visible:
        warnings.append(f"{url}: report document does not show 검증된 보고서 BoI label")
    return errors, warnings


def report_sample_errors(checked_ready_reports: int, *, require_ready_report: bool) -> list[str]:
    if require_ready_report and checked_ready_reports <= 0:
        return ["no ready report documents were checked"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check BoI Inbox group narrative and report quality.")
    parser.add_argument("--base-url", default="http://localhost:28000")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--report-sample-limit", type=int, default=5)
    parser.add_argument("--require-multi-group-ready", "--strict-ready", action="store_true", default=False)
    parser.add_argument("--require-ready-report", action="store_true", default=False)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    query = urllib.parse.urlencode(
        {
            "employee_id": args.employee_id,
            "include_context": "compact",
            "limit": str(args.limit),
        }
    )
    url = args.base_url.rstrip("/") + "/api/inbox?" + query
    body = fetch_json(url)
    groups = [group for group in body.get("groups") or [] if isinstance(group, dict)]
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for group in groups:
        if int(group.get("count") or 0) <= 1:
            continue
        checked += 1
        group_errors, group_warnings = check_group(group, require_multi_group_ready=args.require_multi_group_ready)
        errors.extend(group_errors)
        warnings.extend(group_warnings)
    checked_ready_reports = 0
    for report_url in report_urls_from_inbox(body, limit=max(0, args.report_sample_limit)):
        checked_ready_reports += 1
        report_errors, report_warnings = check_report_document(
            absolute_url(args.base_url, report_url),
            fetch_text(absolute_url(args.base_url, report_url)),
        )
        errors.extend(report_errors)
        warnings.extend(report_warnings)
    errors.extend(report_sample_errors(checked_ready_reports, require_ready_report=args.require_ready_report))
    if checked_ready_reports <= 0 and not args.require_ready_report:
        warnings.append("no ready report documents were checked")
    result = {
        "ok": not errors,
        "url": url,
        "checked_multi_groups": checked,
        "checked_ready_reports": checked_ready_reports,
        "require_ready_report": args.require_ready_report,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.summary else None))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
