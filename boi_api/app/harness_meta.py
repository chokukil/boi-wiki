from __future__ import annotations

"""메타 하네스 검증 헬퍼 (계획서 §4.5 Phase 4).

- `harness/manifest.yaml`이 하네스 버전의 SSOT다: repo 원본 ↔ 서빙 사본 쌍마다 한 항목.
- 서빙 사본 frontmatter의 `harness_version`은 manifest version과 일치해야 한다.
- `harness/CHANGELOG.md`는 ratchet 원칙(모든 규칙은 실제 실패 사례로 소급 가능)을 기록하며,
  각 manifest key의 현재 버전이 근거와 함께 등장해야 한다.
- main.py는 glue(acceptance `Meta` 버킷 등록)만 유지하고 검증 로직은 이 모듈에 둔다.
"""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .okf import split_frontmatter

# 배포 컨테이너에는 boi_api/app만 복사되므로 repo checkout이 없을 수 있다.
# 기본값은 소스 트리 기준 repo root이며, 리포를 다른 위치에 mount하면 env로 재지정한다.
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_RELATIVE_PATH = "harness/manifest.yaml"
CHANGELOG_RELATIVE_PATH = "harness/CHANGELOG.md"
# manifest의 served_path는 repo 기준(data/boi/...)으로 기록한다. 실제 콘텐츠 루트는
# 테스트 임시 복사본처럼 다른 위치일 수 있어 이 prefix를 벗겨 data root에 매핑한다.
SERVED_PATH_PREFIX = "data/boi/"
MANIFEST_ENTRY_FIELDS = ("key", "version", "repo_path", "served_path", "served_boi_id", "title")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
EVAL_STATUS_RELATIVE_PATH = "harness-evals/status.json"


def harness_repo_available(repo_root: Path | None = None) -> bool:
    return (Path(repo_root or REPO_ROOT) / "harness").is_dir()


def load_harness_manifest(repo_root: Path | None = None) -> list[dict[str, Any]]:
    root = Path(repo_root or REPO_ROOT)
    raw = yaml.safe_load((root / MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8"))
    docs = raw.get("docs") if isinstance(raw, dict) else raw
    if not isinstance(docs, list):
        return []
    return [entry for entry in docs if isinstance(entry, dict)]


def served_file_for_entry(data_root: Path, served_path: str) -> Path | None:
    normalized = str(served_path or "").replace("\\", "/")
    if not normalized.startswith(SERVED_PATH_PREFIX):
        return None
    return Path(data_root) / normalized[len(SERVED_PATH_PREFIX):]


def harness_manifest_issues(repo_root: Path | None = None, data_root: Path | None = None) -> list[str]:
    """manifest ↔ repo 원본 ↔ 서빙 사본의 일관성 이슈 목록을 반환한다 (빈 목록 = 통과).

    data_root는 BoI 콘텐츠 루트(예: data/boi 또는 테스트 임시 복사본)다.
    """
    root = Path(repo_root or REPO_ROOT)
    content_root = Path(data_root) if data_root is not None else root / "data" / "boi"
    manifest_path = root / MANIFEST_RELATIVE_PATH
    if not manifest_path.exists():
        return [f"harness manifest is missing: {MANIFEST_RELATIVE_PATH}"]
    try:
        entries = load_harness_manifest(root)
    except Exception as exc:
        return [f"harness manifest failed to parse: {exc}"]
    issues: list[str] = []
    if not entries:
        issues.append("harness manifest has no docs entries")
    seen_keys: set[str] = set()
    covered_served_names: list[str] = []
    for entry in entries:
        key = str(entry.get("key") or "")
        label = key or "<missing key>"
        for field_name in MANIFEST_ENTRY_FIELDS:
            if not str(entry.get(field_name) or "").strip():
                issues.append(f"{label}: manifest entry is missing {field_name}")
        if key:
            if key in seen_keys:
                issues.append(f"{label}: duplicate manifest key")
            seen_keys.add(key)
        version = str(entry.get("version") or "")
        if version and not SEMVER_RE.match(version):
            issues.append(f"{label}: version must be semver MAJOR.MINOR.PATCH, got {version!r}")
        repo_path = str(entry.get("repo_path") or "")
        if repo_path and not (root / repo_path).exists():
            issues.append(f"{label}: repo_path does not exist: {repo_path}")
        served_path = str(entry.get("served_path") or "")
        if not served_path:
            continue
        served_file = served_file_for_entry(content_root, served_path)
        if served_file is None:
            issues.append(f"{label}: served_path must live under {SERVED_PATH_PREFIX}: {served_path}")
            continue
        covered_served_names.append(served_file.name)
        if not served_file.exists():
            issues.append(f"{label}: served_path does not exist: {served_path}")
            continue
        try:
            metadata, _body = split_frontmatter(served_file.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(f"{label}: served copy failed to parse: {exc}")
            continue
        if not metadata:
            issues.append(f"{label}: served copy is missing YAML frontmatter")
            continue
        doc_version = str(metadata.get("harness_version") or "")
        if doc_version != version:
            issues.append(
                f"{label}: served harness_version {doc_version!r} does not match manifest version {version!r}"
            )
        served_boi_id = str(entry.get("served_boi_id") or "")
        if served_boi_id and str(metadata.get("boi_id") or "") != served_boi_id:
            issues.append(f"{label}: served boi_id {metadata.get('boi_id')!r} does not match manifest served_boi_id")
        ref_values = {
            str(ref.get("ref") or "").replace("\\", "/")
            for ref in metadata.get("source_refs") or []
            if isinstance(ref, dict)
        }
        if repo_path and repo_path not in ref_values:
            issues.append(f"{label}: served source_refs does not include repo_path {repo_path}")
    served_dir = content_root / "public" / "harness"
    if served_dir.is_dir():
        actual_names = {path.name for path in served_dir.glob("*.md") if path.name != "index.md"}
        for name in sorted(actual_names - set(covered_served_names)):
            issues.append(f"served harness doc is not covered by the manifest: {name}")
        duplicates = {name for name in covered_served_names if covered_served_names.count(name) > 1}
        for name in sorted(duplicates):
            issues.append(f"served harness doc is covered by more than one manifest entry: {name}")
    else:
        issues.append(f"served harness directory is missing: {served_dir}")
    return issues


def changelog_covers_manifest(repo_root: Path | None = None) -> list[str]:
    """ratchet 관례 검증: CHANGELOG에 각 manifest key의 현재 버전 문자열이 등장해야 한다."""
    root = Path(repo_root or REPO_ROOT)
    changelog_path = root / CHANGELOG_RELATIVE_PATH
    if not changelog_path.exists():
        return [f"harness changelog is missing: {CHANGELOG_RELATIVE_PATH}"]
    try:
        entries = load_harness_manifest(root)
    except Exception as exc:
        return [f"harness manifest failed to parse: {exc}"]
    text = changelog_path.read_text(encoding="utf-8").replace("`", "")
    issues: list[str] = []
    for entry in entries:
        key = str(entry.get("key") or "")
        version = str(entry.get("version") or "")
        if not key or not version:
            continue  # manifest 이슈는 harness_manifest_issues가 보고한다.
        if f"{key} {version}" not in text:
            issues.append(
                f"{key}: CHANGELOG does not record current version {version} with evidence (ratchet 원칙)"
            )
    return issues


def eval_status_path(runtime_root: Path) -> Path:
    return Path(runtime_root) / EVAL_STATUS_RELATIVE_PATH


def write_eval_status(runtime_root: Path, payload: dict[str, Any]) -> Path:
    path = eval_status_path(runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_eval_status(runtime_root: Path) -> dict[str, Any] | None:
    path = eval_status_path(runtime_root)
    if not path.exists():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None
