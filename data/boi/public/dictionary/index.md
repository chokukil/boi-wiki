# Public Dictionary

Public dictionary terms help BoI Agent and ontology search understand semiconductor, quality, equipment, packaging, and AI Native Workflow language. Scope priority is Private, Team, then Public; this page is the curated public fallback vocabulary.

This page is not a giant term list. BoI Wiki uses domain/folder/search exploration and cursor-based API pagination so a large dictionary does not get loaded into Agent context at once.

대량 확장을 전제로 하므로 이 문서는 모든 term을 직접 나열하지 않습니다. 전체 목록은 업무 용어 UI와 `dictionary_terms` cursor 검색으로 확인합니다.

## Scale Policy

- Source of truth: individual OKF Markdown term documents under `public`, `team`, and `private` dictionary folders.
- Runtime retrieval: generated ontology index with compact term records.
- Agent context: compact resolve results only, with bounded matches, aliases, related terms, and query expansion.
- UI exploration: domain/folder/search first; do not render every term on this page.
- MCP/API: use `dictionary_resolve` for query interpretation and `dictionary_terms` with `cursor`, `domain`, `scope`, and `limit` for browsing.

## Representative Entry Points

These examples are stable entry points for the current public vocabulary. Use search or the 업무 용어 UI for the full list.

### Semiconductor Objects

- [Fab](fab.md) - 반도체 제조 시설
- [Wafer](wafer.md) - 반도체 공정 기판
- [Lot](lot.md) - 함께 처리되는 wafer 묶음
- [Die](die.md) - wafer 위 개별 chip 단위

### Process Modules

- [Etch](etch.md) - 식각 공정
- [Lithography](lithography.md) - 노광 공정
- [Deposition](deposition.md) - 박막 증착 범주
- [CMP](cmp.md) - chemical mechanical planarization

### Equipment And Operations

- [Equipment](equipment.md) - 생산 설비 단위
- [Alarm](alarm.md) - 이상 조건 event signal
- [FDC](fdc.md) - Fault Detection and Classification
- [Root Cause Analysis](root-cause-analysis.md) - 근본 원인 분석

### Quality, Inspection, And SPC

- [SPC](spc.md) - Statistical Process Control
- [Reliability Test](reliability-test.md) - 장기 동작, stress, disturb 조건의 품질 평가 범주
- [Word Line Disturbance Test](word-line-disturbance-test.md) - NAND word line disturb 세부 test-method
- [Response Trend](response-trend.md) - 품질 시스템 trend evidence
- [Map View](map-view.md) - wafer/map image 기반 evidence
- [Cross-section Inspection](cross-section-inspection.md) - 단면검사

### Memory And Advanced Packaging

- [HBM](hbm.md) - high bandwidth memory
- [TSV](tsv.md) - through-silicon via
- [Hybrid Bonding](hybrid-bonding.md) - dielectric + copper direct bonding
- [Advanced Packaging](advanced-packaging.md) - 2.5D/3D packaging 범주
- [Memory Stack Height](memory-stack-height.md) - 2HI, 4HI, 8HI 같은 memory stack 높이 표현의 canonical term

### AI Native Workflow

- [Event Broker](event-broker.md) - 업무 event 발행/전달 계층
- [Action Gateway](action-gateway.md) - allowlisted action 실행 계층
- [Manual Handoff](manual-handoff.md) - 사람 판단/승인/현장 조치 이관
- [Approval](approval.md) - 고위험 action 승인

## Authoring Rule

When adding many terms, create or update individual term documents and rely on dictionary search. Do not append a full alphabetical list here. Public and team term additions should run dedupe, relation checks, and compact context budget tests before publication.
