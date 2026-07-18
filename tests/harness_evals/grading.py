from __future__ import annotations

"""하네스 eval 채점기(evaluator) — 판정 기준의 단일 정본.

생성자/평가자 분리(계획서 §4.5): 결과물을 만드는 코드(boi_api.app.share, 웹 라우트,
MCP 도구)와 결과물을 채점하는 이 모듈을 분리해 자기평가 편향을 피한다.
모든 함수는 부수효과 없는 순수 채점 함수로, 실패 목록(list[str])을 반환한다.
테스트는 이 목록이 비어 있는지만 단언하고, 채점 로직을 테스트 파일에 두지 않는다.
"""

from pathlib import Path
from typing import Mapping

from boi_api.app import harness_meta
from boi_api.app.okf import (
    file_sha256,
    lint_html_file,
    lint_markdown_file,
    parse_html_profile,
    validate_boi_profile_metadata,
    validate_boi_profile_path_acl,
    split_frontmatter,
)

# 계획서 §4.3(원본 3종) + §10 P0-5(frame-ancestors/Referrer-Policy 보강)에서
# 확정된 raw 서빙 보안 헤더 (정확히 이 값이어야 한다).
RAW_SECURITY_HEADERS = {
    "content-security-policy": "sandbox allow-scripts; frame-ancestors 'self'",
    "x-content-type-options": "nosniff",
    "cross-origin-resource-policy": "same-site",
    "referrer-policy": "no-referrer",
}
CARD_REQUIRED_SECTIONS = ("# Summary", "# 링크", "# 출처", "# Citations")


def grade_html_share(
    *,
    data_root: Path,
    stored_path: Path,
    viewer_html: str,
    raw_headers: Mapping[str, str],
) -> list[str]:
    """Eval A: 게시된 공유 HTML 산출물을 하드 기준으로 채점한다."""
    if not stored_path.exists():
        return [f"stored html file does not exist: {stored_path}"]
    failures: list[str] = []
    stored_text = stored_path.read_text(encoding="utf-8")
    profile_count = stored_text.count('id="boi-profile"')
    if profile_count != 1:
        failures.append(f"stored html must contain exactly one boi-profile block, found {profile_count}")
    profile = parse_html_profile(stored_text)
    if profile is None:
        failures.append("stored html has no parseable BoI HTML Profile JSON-LD block")
    else:
        boi_profile = profile.get("boiProfile")
        if not isinstance(boi_profile, dict):
            failures.append("BoI HTML Profile JSON-LD must contain a boiProfile object")
        else:
            failures.extend(f"boiProfile: {error}" for error in validate_boi_profile_metadata(boi_profile))
            failures.extend(
                f"boiProfile path/acl: {error}"
                for error in validate_boi_profile_path_acl(boi_profile, stored_path, Path(data_root))
            )
    card_path = stored_path.with_suffix(".md")
    if not card_path.exists():
        failures.append(f"knowledge card does not exist: {card_path.name}")
    html_errors, _html_warnings = lint_html_file(stored_path, boi_root=Path(data_root))
    failures.extend(f"okf html lint: {error}" for error in html_errors)
    if 'sandbox="allow-scripts"' not in viewer_html:
        failures.append('viewer must embed the shared document with sandbox="allow-scripts"')
    if "allow-same-origin" in viewer_html:
        failures.append("viewer must never grant allow-same-origin (업로드 HTML의 세션 탈취 경로)")
    normalized_headers = {str(key).lower(): str(value) for key, value in raw_headers.items()}
    for header, expected in RAW_SECURITY_HEADERS.items():
        actual = normalized_headers.get(header)
        if actual != expected:
            failures.append(f"raw response header {header} must be {expected!r}, got {actual!r}")
    return failures


def grade_confirmed_write_refusal(refusal: BaseException | None) -> list[str]:
    """Eval A(경계): user_confirmed 없는 MCP 쓰기 호출은 API 호출 전에 거부되어야 한다."""
    if refusal is None:
        return ["unconfirmed html_share_publish must be refused before any API call"]
    if "user_confirmed=true" not in str(refusal):
        return [f"refusal message must mention user_confirmed=true, got {refusal!r}"]
    return []


def grade_okf_doc(*, card_path: Path, data_root: Path, html_path: Path) -> list[str]:
    """Eval B: 지식 카드가 OKF/BoI Profile 계약을 지키는지 채점한다."""
    if not card_path.exists():
        return [f"knowledge card does not exist: {card_path}"]
    metadata, body = split_frontmatter(card_path.read_text(encoding="utf-8"))
    if not metadata:
        return ["knowledge card is missing YAML frontmatter"]
    failures: list[str] = []
    # 12개 REQUIRED_FIELDS + enum + (public이면) source_refs/reviewer 요건을 함께 검증한다.
    failures.extend(validate_boi_profile_metadata(metadata))
    failures.extend(validate_boi_profile_path_acl(metadata, card_path, Path(data_root)))
    refs = [ref for ref in metadata.get("source_refs") or [] if isinstance(ref, dict)]
    html_refs = [ref for ref in refs if str(ref.get("type") or "") == "html_artifact"]
    if not html_refs:
        failures.append("knowledge card must carry an html_artifact source_ref")
    elif not html_path.exists():
        failures.append(f"html artifact for the card does not exist: {html_path}")
    elif str(html_refs[0].get("sha256") or "") != file_sha256(html_path):
        failures.append("html_artifact source_ref sha256 does not match the stored html file")
    review = metadata.get("review")
    if not isinstance(review, dict) or not review.get("reviewer"):
        failures.append("knowledge card must carry a review block with a reviewer")
    for section in CARD_REQUIRED_SECTIONS:
        if section not in body:
            failures.append(f"knowledge card body is missing required section: {section}")
    return failures


def grade_harness_meta(repo_root: Path, data_root: Path) -> list[str]:
    """Eval C: manifest/CHANGELOG 일관성 + 서빙 하네스 문서의 lint/참조 무결성."""
    failures: list[str] = []
    failures.extend(harness_meta.harness_manifest_issues(repo_root, data_root))
    failures.extend(harness_meta.changelog_covers_manifest(repo_root))
    served_dir = Path(data_root) / "public" / "harness"
    if not served_dir.is_dir():
        failures.append(f"served harness directory is missing: {served_dir}")
        return failures
    for path in sorted(served_dir.glob("*.md")):
        errors, _edges = lint_markdown_file(path, boi_root=Path(data_root))
        failures.extend(f"{path.name}: {error}" for error in errors)
    for name in ("overview.md", "index.md"):
        entry_path = served_dir / name
        text = entry_path.read_text(encoding="utf-8") if entry_path.exists() else ""
        if "html-share-harness" not in text:
            failures.append(f"{name} must reference html-share-harness")
    return failures
