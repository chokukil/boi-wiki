#!/usr/bin/env python3
"""Render public OKF mirrors from the canonical repository Science harnesses."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT / "harness"
PUBLIC_ROOT = ROOT / "data" / "boi" / "public" / "harness"
HARNESS_METADATA = {
    "science-source-curation-harness.md": (
        "Science Source Curation Harness",
        "과학 원본과 locator-bound Evidence를 제안하고 검토하는 운영 기준",
    ),
    "science-knowledge-authoring-harness.md": (
        "Science Knowledge Authoring Harness",
        "Evidence 범위를 보존한 atomic Science Knowledge 작성 기준",
    ),
    "science-equation-knowledge-harness.md": (
        "Science Equation Knowledge Harness",
        "검토된 수식 의미·변수·근거·판정 연결·채널 표시의 공통 계약",
    ),
    "science-rule-qualification-harness.md": (
        "Science Rule Qualification Harness",
        "결정론적 Rule과 실제 과학 주장 qualification 기준",
    ),
    "science-verification-harness.md": (
        "Science Verification Harness",
        "문서 해석부터 판정·근거·채널 parity까지 검증하는 운영 기준",
    ),
}


def canonical_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---\n", 2)
    if len(parts) != 3 or parts[0]:
        raise ValueError(f"invalid harness frontmatter: {path}")
    return parts[2].strip() + "\n"


def public_document(name: str, title: str, description: str) -> str:
    body = canonical_body(REPO_ROOT / name)
    slug = name.removesuffix(".md")
    return f"""---
okf_version: "0.1"
boi_profile_version: "0.1"
sci_profile_version: "0.1"
type: boi/harness
title: {title}
description: {description}
tags: [BoIWiki, ScienceVerifier, Harness]
timestamp: 2026-08-25T16:00:00+09:00
boi_id: boi:public:harness:{slug}
visibility: public
classification: internal
owner: science-admin
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: draft
source_refs:
  - type: repo
    ref: harness/{name}
  - type: repo
    ref: data/okf/profiles/sci-profile.yaml
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
---
{body}"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale: list[str] = []
    for name, (title, description) in HARNESS_METADATA.items():
        expected = public_document(name, title, description)
        target = PUBLIC_ROOT / name
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != expected:
                stale.append(name)
            continue
        target.write_text(expected, encoding="utf-8")
    if stale:
        raise SystemExit("stale Science harness mirrors: " + ", ".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
