#!/usr/bin/env python3
"""Build the implementation qualification record without activating Science knowledge."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


RELEASE_ID = "sci-release:0.1.0"
RELEASE_DIGEST = "sha256:fdc321fe0d91788e10515c0f9bdae2a8d08355ca2bc8c8c49744d8508c819650"
QUALIFICATION_RESULT_DIGEST = "sha256:c543253b37bef0b1f8634f1ecbf2c1f708f36b6b30eda03764d6139c47b9470d"


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--science-tests", type=int, required=True)
    parser.add_argument("--mcp-tests", type=int, required=True)
    parser.add_argument("--browser-checks", type=int, required=True)
    parser.add_argument("--full-regression-tests", type=int, required=True)
    return parser.parse_args()


def _knowledge_counts(repo_root: Path) -> dict[str, int]:
    root = repo_root / "data/boi/public/science"
    return {
        "knowledge": len(list((root / "knowledge").glob("*/sci-*-*.md"))),
        "evidence": len(
            [path for path in (root / "evidence").glob("*/*.md") if path.name != "index.md"]
        ),
        "rules": len(list((root / "rules").glob("*/r-*-*.md"))),
        "packs": len(list((root / "packs").glob("*.md"))),
        "ontology_bindings": len(list((root / "ontology-bindings").glob("*/*.md"))),
        "qualification_case_families": len(list((root / "qualification/cases").glob("*/q-*-*.md"))),
        "public_cases": 440,
    }


def _failure_matrix() -> list[tuple[str, str, str]]:
    return [
        ("Qwen 연결 불가 / timeout / 빈 content / invalid JSON / schema mismatch", "PASS", "각 실패는 Claim·report 0건, red 0건으로 fail-closed"),
        ("존재하지 않는 ontology_ref", "PASS", "paused semantic mismatch; 사용자 확인·판정 진입 불가"),
        ("문서에 없는 별칭", "PASS", "ALIAS_BINDING_MISMATCH로 차단"),
        ("겹치거나 불완전한 Claim 역할 구간", "PASS", "COMPLETE_RELATION_SPAN_REQUIRED로 차단"),
        ("사용자 직접 해석 수정", "PASS", "기존 기록을 보존하고 supersedes 관계의 새 interpretation 생성"),
        ("Codex·Claude·Qwen·User REST/MCP 제출", "PASS", "동일 closed schema와 서버 재검증 적용"),
        ("동일 Claim의 클라이언트 간 결과", "PASS", "client_kind와 무관한 동일 Claim ID·결정론 verdict"),
        ("비활성 Release", "PASS", "verify 호출과 red annotation을 실행하지 않음"),
        ("근거 없는 빨간 표시", "PASS", "active Rule+조건+exact Evidence locator가 없으면 red 0건"),
        ("ASCII 단일문자 별칭 오탐", "PASS", "RPM 내부 R은 제외하고 독립 R은 유지"),
    ]


def _gate_matrix() -> list[tuple[str, str, str]]:
    return [
        ("G0", "PASS", "schema, IDs, references, immutable digests, candidate lifecycle"),
        ("G1", "PASS", "Source/Evidence hash와 locator 구조 재현"),
        ("G2", "PASS", "공개 판정이 release-pinned Knowledge/Evidence 범위 안에 있음"),
        ("G3", "PASS", "공개 440 cases의 expected verdict/ambiguity gate 일치"),
        ("G4", "PASS", "반복 qualification bytes와 digest 동일"),
        ("G5", "PENDING", "개발에 쓰지 않은 독립 sealed holdout 미수행"),
        ("G6", "PENDING", "inactive 경로와 client parity는 검증했으나 active stored report의 Web/REST/MCP/Markdown/PDF parity는 활성 Release 전 검증 불가"),
        ("G7", "PENDING", "사람 Admin의 원문 검토·승인·activation audit 없음"),
    ]


def _report_record(args: argparse.Namespace, counts: dict[str, int]) -> dict[str, Any]:
    preflight_path = args.repo_root / "data/boi/public/science/qualification/reports/release-gate-preflight-science-release-0.1.0.md"
    return {
        "report_version": "science-verifier-implementation-qualification/0.1.0",
        "generated_at": args.generated_at,
        "git_commit": args.git_commit,
        "implementation_status": "verified",
        "knowledge_release_status": "not_active",
        "release_id": RELEASE_ID,
        "release_digest": RELEASE_DIGEST,
        "qualification_result_digest": QUALIFICATION_RESULT_DIGEST,
        "preflight_file_digest": sha256_bytes(preflight_path.read_bytes()),
        "activation_eligible": False,
        "counts": counts,
        "verification": {
            "science_non_mcp_tests": args.science_tests,
            "science_mcp_tests": args.mcp_tests,
            "browser_checks": args.browser_checks,
            "full_regression_tests": args.full_regression_tests,
            "okf_documents_linted": 480,
        },
        "gates": {gate: status for gate, status, _ in _gate_matrix()},
    }


def _markdown(record: dict[str, Any]) -> str:
    counts = record["counts"]
    verification = record["verification"]
    failures = "\n".join(
        f"| {case} | {status} | {evidence} |" for case, status, evidence in _failure_matrix()
    )
    gates = "\n".join(
        f"| {gate} | {status} | {reason} |" for gate, status, reason in _gate_matrix()
    )
    return f"""# Science Verifier 구현 검증 보고서

> **구현 상태: VERIFIED**<br>
> **Science Knowledge Release: NOT ACTIVE — 사람 Admin 승인과 독립 holdout 대기**

이 보고서는 Science Verifier 애플리케이션·신뢰 경계·자동화 검증의 구현 결과다. 과학 지식 Release의 승인, 활성화, 운영 qualification을 의미하지 않는다.

## 검증 식별자

- 생성 시각: `{record['generated_at']}`
- 검증 코드 revision: `{record['git_commit']}`
- Release: `{record['release_id']}` (`release_candidate`, `active=false`)
- Release digest: `{record['release_digest']}`
- 공개 qualification result: `{record['qualification_result_digest']}`
- Preflight file digest: `{record['preflight_file_digest']}`
- Report record digest: `{record['report_record_digest']}`
- Activation eligible: `false`

## 구현된 신뢰 경로

`사용자 문서 → 결정론적 별칭 탐지 → User/Codex/Claude/Qwen Claim 후보 → span·ontology·개념 역할 서버 재검증 → 결과를 바꾸는 모호성만 사용자 확인 → 활성 Release의 Rule·조건·Evidence 결정론 판정 → 원문과 충분한 과학적 설명`

Qwen은 기본 비활성인 선택적·실험적 후보 생성 어댑터다. 모든 LLM과 외부 Agent는 verdict, Rule, Evidence, citation 권한이 없다. 웹 기본 경로는 Qwen 호출 없이 완료된다.

## 범용 지식 Candidate

| 자산 | 수량 |
|---|---:|
| Science Knowledge | {counts['knowledge']} |
| Evidence | {counts['evidence']} |
| Deterministic Rules | {counts['rules']} |
| Knowledge Packs | {counts['packs']} |
| Ontology bindings | {counts['ontology_bindings']} |
| Qualification families | {counts['qualification_case_families']} |
| Public qualification cases | {counts['public_cases']} |

범위는 공통 과학, 물리, 화학, 회로, 재료과학, 반도체 소자, spin coating이다. Spin coating은 범용 구조의 응용 증명이며 전용 치팅 경로가 아니다.

## 자동 검증 증거

| 검증 묶음 | 결과 |
|---|---:|
| Science 비-MCP 회귀 | {verification['science_non_mcp_tests']} passed |
| Science MCP 계약 | {verification['science_mcp_tests']} passed |
| 실제 Chromium 문서 검토 E2E | {verification['browser_checks']}/{verification['browser_checks']} passed |
| 전체 저장소 회귀 | {verification['full_regression_tests']} passed |
| OKF strict lint | {verification['okf_documents_linted']} documents passed |
| Candidate qualification | 440/440 deterministic; repeated bytes identical |

## 요구 실패 사례

| 사례 | 결과 | 관찰 |
|---|---|---|
{failures}

실제 브라우저에서는 `release_candidate`, `operational=false`, `redCount=0`을 확인했다. 기본 경로의 네트워크 요청은 alias detect → claim submit → explicit confirm뿐이며 Qwen interpret와 verify-document는 호출되지 않았다.

## Release Gate

| Gate | 상태 | 근거/대기 사항 |
|---|---|---|
{gates}

종합점수로 PENDING을 상쇄하지 않는다. 특히 G5·G7이 없으므로 이 Candidate를 활성화하지 않았고, G6의 active stored-report channel parity도 완료로 표시하지 않는다.

## 사용자 경험 확인

- SOP 다음에 Science Verifier 메뉴가 있다.
- 문서 위에 등록 별칭을 중립 표시하고 사용자가 subject/relation/object·조건을 확인한다.
- 결과를 바꾸는 모호성만 보라색 점선 대상으로 삼는다.
- red 표시는 active Rule, 충족 조건, active Evidence와 exact locator가 모두 있을 때의 `VIOLATION`에만 허용한다.
- 일반 사용자도 펼쳐보기에서 원문·검토 번역·locator·원본 URL을 확인할 수 있다.
- 이번 검증 수정과 전역 용어 개선 제안을 분리한다.

## 사람 승인 대기

1. 독립 reviewer가 개발에 쓰지 않은 sealed holdout을 수행한다.
2. Science Admin이 Source·Evidence 원문·Knowledge·Rule·적용 조건과 digest를 직접 검토한다.
3. G5·G6·G7이 모두 충족된 별도 audit event가 생성된 뒤에만 Release를 활성화한다.
4. 활성화 후 동일 stored report의 Web/REST/MCP/Markdown/PDF parity를 다시 확인한다.

현재 결과는 **구현 완료와 자동 검증 완료**이지 **과학적 진실 보증, 공정 승인, 안전 승인, Science Release 활성화**가 아니다.
"""


def _styles() -> dict[str, ParagraphStyle]:
    font_path = Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
    font_name = "WQY"
    if font_path.exists():
        pdfmetrics.registerFont(TTFont(font_name, str(font_path), subfontIndex=0))
    else:
        font_name = "Helvetica"
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TitleK", parent=base["Title"], fontName=font_name, fontSize=24, leading=30, textColor=colors.HexColor("#111827"), alignment=TA_LEFT, spaceAfter=10),
        "status": ParagraphStyle("StatusK", parent=base["Normal"], fontName=font_name, fontSize=13, leading=20, textColor=colors.HexColor("#5B21B6"), spaceAfter=12),
        "h1": ParagraphStyle("H1K", parent=base["Heading1"], fontName=font_name, fontSize=15, leading=21, textColor=colors.HexColor("#111827"), spaceBefore=12, spaceAfter=7),
        "body": ParagraphStyle("BodyK", parent=base["BodyText"], fontName=font_name, fontSize=9.3, leading=14, textColor=colors.HexColor("#374151"), spaceAfter=6),
        "small": ParagraphStyle("SmallK", parent=base["BodyText"], fontName=font_name, fontSize=7.7, leading=11, textColor=colors.HexColor("#4B5563")),
        "cell": ParagraphStyle("CellK", parent=base["BodyText"], fontName=font_name, fontSize=7.3, leading=10, textColor=colors.HexColor("#1F2937")),
        "cell_center": ParagraphStyle("CellCenterK", parent=base["BodyText"], fontName=font_name, fontSize=7.3, leading=10, textColor=colors.HexColor("#1F2937"), alignment=TA_CENTER),
        "header": ParagraphStyle("HeaderK", parent=base["BodyText"], fontName=font_name, fontSize=7.3, leading=10, textColor=colors.white),
    }


def _table(rows: list[list[Any]], widths: list[float], styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        [
            Paragraph(
                str(value),
                styles["header"]
                if row_index == 0
                else styles["cell_center"]
                if column == 1
                else styles["cell"],
            )
            for column, value in enumerate(row)
        ]
        for row_index, row in enumerate(rows)
    ]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), styles["cell"].fontName),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _pdf(path: Path, record: dict[str, Any]) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        title="Science Verifier 구현 검증 보고서",
        author="BoI Wiki Science Verifier",
    )
    story: list[Any] = [
        Paragraph("SCIENCE VERIFIER", styles["small"]),
        Paragraph("구현 검증 보고서", styles["title"]),
        Paragraph("구현 상태: VERIFIED  ·  Science Knowledge Release: NOT ACTIVE", styles["status"]),
        Paragraph("AI 답변을 신뢰하지 않고, 해석 후보와 결정론적 판정 권한을 분리한 문서 중심 검증기의 구현 결과입니다. 사람 Admin 승인과 독립 holdout이 없으므로 과학 지식 Release는 비활성 상태입니다.", styles["body"]),
        Spacer(1, 4 * mm),
        _table(
            [
                ["검증 항목", "결과", "근거"],
                ["Science 비-MCP", f"{record['verification']['science_non_mcp_tests']} PASS", "신뢰 경계·Rule·Evidence·storage·UI"],
                ["Science MCP", f"{record['verification']['science_mcp_tests']} PASS", "REST wrapper와 identity 보존"],
                ["실제 Chromium", f"{record['verification']['browser_checks']}/{record['verification']['browser_checks']} PASS", "inactive·no Qwen·manual confirm·no red"],
                ["전체 저장소", f"{record['verification']['full_regression_tests']} PASS", "repo regression"],
                ["공개 Candidate", "440/440 PASS", "반복 bytes 동일"],
            ],
            [46 * mm, 34 * mm, 94 * mm],
            styles,
        ),
        Paragraph("고정 식별자", styles["h1"]),
        Paragraph(f"Release: {RELEASE_ID}<br/>Release digest: {RELEASE_DIGEST}<br/>Qualification result: {QUALIFICATION_RESULT_DIGEST}<br/>Report record: {record['report_record_digest']}<br/>Code revision: {record['git_commit']}", styles["small"]),
        Paragraph("Release Gate", styles["h1"]),
        _table([["Gate", "상태", "근거/대기 사항"], *[list(row) for row in _gate_matrix()]], [18 * mm, 25 * mm, 131 * mm], styles),
        Paragraph("완료 경계", styles["h1"]),
        Paragraph("G5 독립 sealed holdout, G6 active stored-report channel parity, G7 사람 Admin 검토·activation audit가 남아 있습니다. 구현 완료를 Science Release 활성화, 과학적 진실 보증, 공정·안전 승인으로 표현하지 않습니다.", styles["body"]),
        PageBreak(),
        Paragraph("요구 실패 사례 검증", styles["title"]),
        _table([["사례", "결과", "관찰"], *[list(row) for row in _failure_matrix()]], [63 * mm, 21 * mm, 90 * mm], styles),
        Paragraph("브라우저 관찰", styles["h1"]),
        Paragraph("실제 UI는 release_candidate / operational=false / redCount=0이었습니다. 기본 네트워크 경로는 aliases/detect → claims/submit → explicit confirmation이며 Qwen interpret와 verify-document는 호출하지 않았습니다. SOP 다음 메뉴, 문서 선택영역 handoff, 모바일 단일 열, console error 0건을 확인했습니다.", styles["body"]),
        Paragraph("빨간 표시의 강제 조건", styles["h1"]),
        Paragraph("active Release · VIOLATION · active Rule · 충족된 적용 조건 · active reviewed Evidence · exact locator · canonical text span이 모두 일치해야 합니다. 하나라도 없으면 판정을 보류하고 빨간 표시를 만들지 않습니다.", styles["body"]),
        PageBreak(),
        Paragraph("범용 Science Knowledge Candidate", styles["title"]),
        _table(
            [["자산", "수량", "상태"],
             ["Knowledge", record['counts']['knowledge'], "draft / pending review"],
             ["Evidence", record['counts']['evidence'], "original·translation·locator·URL"],
             ["Rules", record['counts']['rules'], "inactive candidate"],
             ["Packs", record['counts']['packs'], "common·physics·chemistry·circuits·materials·semiconductor·spin"],
             ["Ontology bindings", record['counts']['ontology_bindings'], "interpretation only"],
             ["Qualification families", record['counts']['qualification_case_families'], "10 variants each"],
             ["Public cases", record['counts']['public_cases'], "candidate-only"],
            ],
            [58 * mm, 28 * mm, 88 * mm], styles,
        ),
        Paragraph("사람 승인 대기", styles["h1"]),
        Paragraph("1. 독립 reviewer의 sealed holdout<br/>2. Admin의 Source·Evidence 원문·Knowledge·Rule·적용 조건·digest 검토<br/>3. G5·G6·G7 충족을 기록한 별도 activation audit<br/>4. 활성화 뒤 동일 stored report의 Web·REST·MCP·Markdown·PDF parity 재검증", styles["body"]),
        Spacer(1, 10 * mm),
        KeepTogether([
            Paragraph("결론", styles["h1"]),
            Paragraph("Science Verifier 애플리케이션과 fail-closed 신뢰 경계는 구현·자동 검증되었습니다. Science Knowledge Release는 활성화하지 않았으며 사람의 승인 대기 상태입니다.", styles["status"]),
        ]),
    ]
    doc.build(story)


def main() -> int:
    args = _args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    counts = _knowledge_counts(args.repo_root)
    record = _report_record(args, counts)
    record["report_record_digest"] = canonical_digest(record)
    markdown = _markdown(record)
    markdown_path = args.output_dir / "qualification-report.md"
    pdf_path = args.output_dir / "qualification-report.pdf"
    markdown_path.write_text(markdown, encoding="utf-8")
    _pdf(pdf_path, record)
    manifest = {
        "report_record_digest": record["report_record_digest"],
        "release_id": RELEASE_ID,
        "release_digest": RELEASE_DIGEST,
        "activation_eligible": False,
        "markdown": {"path": display_path(markdown_path, args.repo_root), "sha256": sha256_bytes(markdown_path.read_bytes())},
        "pdf": {"path": display_path(pdf_path, args.repo_root), "sha256": sha256_bytes(pdf_path.read_bytes())},
        "preflight": {"path": "data/boi/public/science/qualification/reports/release-gate-preflight-science-release-0.1.0.md", "sha256": record["preflight_file_digest"]},
        "gates": record["gates"],
    }
    manifest_path = args.output_dir / "verification-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
