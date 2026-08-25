# Science Verifier 구현 검증 보고서

> **구현 상태: VERIFIED**<br>
> **보고서 상태: FINAL**<br>
> **Science Knowledge Release: NOT ACTIVE — 사람 Admin 승인과 독립 sealed holdout 대기**

이 보고서는 AI나 호출자 제공 숫자를 신뢰하지 않는다. 현재 Git 상태와 기계 산출 JUnit, 브라우저 캡처 manifest, Candidate qualification, 독립 리뷰를 검증하고 각 원본 파일의 SHA-256을 묶어 구현 상태를 계산한다.

## 검증 식별자

- 생성 시각: `2026-08-25T05:53:06Z`
- 검증 코드 revision: `02f89be5caad41f45f57af7558a4b3e69c42efbc`
- Git dirty: `false`
- Git status digest: `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Evidence bundle digest: `sha256:404f247418254fbbabca94ec124be5200a36525eacd0fb961320be558561485b`
- Report record digest: `sha256:e13ff8200856d2cda1cd8a54491ed9a3bee502c073b74d03da61fe807661ed0b`
- Release: `sci-release:0.1.0` (`release_candidate`, `active=false`)
- Release digest: `sha256:5802a4efce096e003d23550b90e5c956967893bc50646455447b91a97d1db9ae`
- Qualification result digest: `sha256:ecce372fcd3adfb56f2ab9b3643721e2bda7305e03f610eb0816fff981ac31e9`
- Activation eligible: `false`

## 기계 검증 증거

| 증빙 | 파생 상태 | 기계 결과 | 파일 SHA-256 |
|---|---|---|---|
| Tracked pytest suite contract | VERIFIED | schema=science-test-suite-contract/0.1, suites=3 | `sha256:b5d113acaff14e84d77bd834642f1d7370c9cc443c89f418a3f326fed6f37562` |
| Science 회귀 JUnit | VERIFIED | tests=1689, failures=0, errors=0, skipped=0 | `sha256:4c76246c9a88a19ba8528dd3ea9023ec751d713b4ef085525a706fe74321ed2a` |
| MCP 계약 JUnit | VERIFIED | tests=23, failures=0, errors=0, skipped=0 | `sha256:6e51e282fd52e2c79868f409798d3f090d031a23d0dd80a4e0d5b1afaa3deeb6` |
| 전체 저장소 회귀 JUnit | VERIFIED | tests=2296, failures=0, errors=0, skipped=9 | `sha256:3e7ebcb2945601577157c3daa825fcb9b61b404e3ebf083b971237b071068f28` |
| 브라우저 캡처 manifest | VERIFIED | checks=27, captures=3 | `sha256:16816a225fa77c3f99988966972ae89ec242dd874894ef5d7036f26bd37b9686` |
| 수식 Knowledge·표시 asset | VERIFIED | assets=6, catalog_equations=6, pdf_safe=6 | `sha256:337a70a877d45fd14d58ff42a8b0307d2525f6db0292b96167675ba1c5d25fff` |
| Candidate qualification | VERIFIED | cases=440, lifecycle=release_candidate | `sha256:20a42afd100923d4a821452f6d1ee678d1def4218848ef00a36ef1306bb5f361` |
| 독립 코드 리뷰 | VERIFIED | status=passed, findings={'critical': 0, 'important': 0, 'advisory': 0} | `sha256:3d1961c9f05333c1c6ec83ae29f6c9306de61b55ac359ebe02fa89af844d7946` |

## 상태 하향 사유

- 없음

## Candidate 지식 자산

| 자산 | 파일/결과 수량 |
|---|---:|
| Science Knowledge | 44 |
| Evidence | 50 |
| Deterministic Rules | 44 |
| Knowledge Packs | 7 |
| Ontology bindings | 29 |
| Qualification families | 44 |
| Public qualification cases | 440 |

## 수식 지식·검증·표시 구현

- Equation asset manifest: `sha256:6f4e12c4da689bc4e93d0e85393b8f26c7191cc41a1a94359a975e673fecf744` (assets=6, Catalog equations=6)
- 범용 도메인: Chemistry, Circuits, Materials Science, Physics, Semiconductor Devices, Spin Coating
- 결정론적 Rule 수식: 3개
- 설명 전용 수식: 3개
- 닫힌 evaluator: `sci-evaluator:closed-arithmetic-relation` version `0.1.0` (`sha256:a2324dddd46cd907539eb675d129edfcee646af75b94763f54a365d54c1276ac`)
- 지원하는 결정 연산: `equal`, `product`, `quotient`. 이 목록 밖의 수식 구조는 판정 권한을 얻지 않는다.
- 표시 자산 권한: `none`; SVG/PDF 표시 실패가 verdict나 빨간 표시에 영향을 주지 않는다.

| 도메인 | Equation identity | 표시 LaTeX | plain fallback | decision use |
|---|---|---|---|---|
| Chemistry | `sci:equation:chemistry:molar-concentration-definition` | `c = \frac{n_{\mathrm{solute}}}{V_{\mathrm{solution}}}` | `c = n_solute / V_solution` | `deterministic_rule` |
| Circuits | `sci:equation:circuits:kvl-loop-balance` | `\sum_{k} V_k = 0` | `sum(loop voltages with sign) = 0 V` | `deterministic_rule` |
| Materials Science | `sci:equation:materials:arrhenius-diffusion` | `D = D_0 \exp\!\left(-\frac{E_a}{k_B T}\right)` | `D = D0 * exp(-Ea / (kB*T))` | `explanation_only` |
| Physics | `sci:equation:physics:applied-work-kinetic-energy-change` | `W_{\mathrm{applied}} = \Delta K` | `W_applied = delta_K` | `deterministic_rule` |
| Semiconductor Devices | `sci:equation:semiconductor:low-field-conductivity` | `\sigma = q n \mu_n + q p \mu_p` | `sigma = q*n*mu_n + q*p*mu_p` | `explanation_only` |
| Spin Coating | `sci:equation:spin-coating:drying-limited-power-law` | `h \propto \omega^{-1/2}` | `h proportional to omega^(-1/2)` | `explanation_only` |

### 원문 Evidence 연결

- `sci:equation:chemistry:molar-concentration-definition` → Evidence `sci-evidence:chemistry:amount-concentration` (`sha256:61b31d09c34669364ca64b25acab41c860f5c3847889de9b525a04c9e0b6cb90`), Source [sci-source:chem1-virtual-textbook](https://www.chem1.com/acad/webtext/virtualtextbook.html), locator `{"content_hash":"sha256:f40fc5c0ec0afb3ebb34d21bc2eab905c3675348bf432503256d2fe94eea0013","exact":true,"hash_scope":"utf8_sha256_prefix_lf_original_lf_suffix","heading":"Molarity: mole/volume basis","medium":"html","prefix":"This is the method most used by chemists to express concentration, and it is the one most important for you to master.","preservation_status":"checksum_only_no_archived_copy","requested_url":"https://www.chem1.com/acad/webtext/solut/solut-1.html","resolved_url":"https://www.chem1.com/acad/webtext/solut/solut-1.html","resource_url":"https://www.chem1.com/acad/webtext/solut/solut-1.html","retrieved_at":"2026-08-25T02:45:00+09:00","retrieved_resource_hash":"sha256:53dd0dd0907cbc911738b1fe0a4a1268bb22ec4c562077d687389486f80f7c1d","sentence_ordinal":2,"suffix":"The important point to remember is that the volume of the solution is different from the volume of the solvent;"}`
- `sci:equation:circuits:kvl-loop-balance` → Evidence `sci-evidence:circuits:kvl-law` (`sha256:3fb7e681d5cb647d112356caaafccc8fe21aed62580f03758fb88febecbaf91b`), Source [sci-source:mit-6-002](https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/), locator `{"content_hash":"sha256:b4c453cd2265ef5a94a2a2ce4025078a870b4db9c6d70a2bf3aa7722ecc8fba8","exact":true,"hash_scope":"retrieved_pdf_bytes","medium":"pdf","pdf_page_index":2,"preservation_status":"checksum_only_no_archived_copy","printed_page":"PDF page 3","requested_url":"https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf","resolved_url":"https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf","resource_url":"https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf","retrieved_at":"2026-08-25T02:45:00+09:00","section":"Transcript — Lecture 2, Kirchhoff laws","sentence_label":"KVL definition"}`
- `sci:equation:materials:arrhenius-diffusion` → Evidence `sci-evidence:materials:diffusion-arrhenius` (`sha256:6179ca39a0a0ea9fe50623a689383281c4bc8d232ce07a3718637b98bfdc7c71`), Source [sci-source:mit-3-091](https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/), locator `{"content_hash":"sha256:ded3970444be9ed9b62f3aef4d90f3ece6687caf336a6894a0b6a17723f6300a","equation":"D = D₀e^(−Eₐ/(kBT))","exact":true,"hash_scope":"retrieved_pdf_bytes","medium":"pdf","pdf_page_index":1,"preservation_status":"checksum_only_no_archived_copy","printed_page":"PDF page 2","requested_url":"https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf","resolved_url":"https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf","resource_url":"https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf","retrieved_at":"2026-08-25T02:45:00+09:00","section":"Recitation 26 — Arrhenius relationship","transcription_method":"manual visual transcription of the typeset equation; no OCR substitution"}`
- `sci:equation:physics:applied-work-kinetic-energy-change` → Evidence `sci-evidence:physics:work-energy-power` (`sha256:a8963aa86fa9cb4108bf4c7893437e800f87ab2301b1efd557db21aaea66484b`), Source [sci-source:mit-8-01sc](https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/), locator `{"content_hash":"sha256:a6bf0626b4c9446a7b6aec206024b90f611403eb059a8dd7ffc45fe1a98fec00","exact":true,"hash_scope":"retrieved_pdf_bytes","medium":"pdf","pdf_page_index":16,"preservation_status":"checksum_only_no_archived_copy","printed_page":"printed 13-16; PDF page 17","requested_url":"https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter13.pdf","resolved_url":"https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter13.pdf","resource_url":"https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter13.pdf","retrieved_at":"2026-08-25T02:45:00+09:00","section":"13.6 Work-Kinetic Energy Theorem"}`
- `sci:equation:semiconductor:low-field-conductivity` → Evidence `sci-evidence:semiconductor-devices:carrier-conductivity` (`sha256:b9b6b568baa5f168fc5defe85da1206c207e8fac2a2a29bb32b041fc1ada1ce5`), Source [sci-source:chenming-hu-devices](https://www.chu.berkeley.edu/modern-semiconductor-devices-for-integrated-circuits-chenming-calvin-hu-2010/), locator `{"content_hash":"sha256:af37b00ce074935c54c88d27af5c8dceac5bc9b900085ef66c1e863b0b291e98","equation":"σ = qnµn + qpµp","exact":true,"hash_scope":"retrieved_pdf_bytes","medium":"pdf","pdf_page_index":9,"preservation_status":"checksum_only_no_archived_copy","printed_page":"printed page 44; PDF page 10","requested_url":"https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf","resolved_url":"https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf","resource_url":"https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf","retrieved_at":"2026-08-25T02:45:00+09:00","section":"Chapter 2, 2.2 Drift, equation (2.2.14)","transcription_method":"manual visual transcription of the typeset equation; symbols preserved"}`
- `sci:equation:spin-coating:drying-limited-power-law` → Evidence `sci-evidence:spin-coating:microchemicals-spin-speed-direction` (`sha256:a43a9b1721afc9870f7587310e7a10bec272058d36d1af281e43f500f089c02d`), Source [sci-source:microchemicals-spin-coating-photoresist](https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf), locator `{"content_hash":"sha256:3d9b159838744f504db5c9742ef7f18b1b5f5d2ff78dfecc487086f41639c6b7","exact":true,"hash_scope":"retrieved_pdf_bytes","medium":"pdf","pdf_page_index":0,"preservation_status":"checksum_only_no_archived_copy","printed_page":"PDF page 1","requested_url":"https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf","resolved_url":"https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf","resource_url":"https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf","retrieved_at":"2026-08-25T05:14:00+09:00","section":"Influence of the Attained Spin Speed","transcription_method":"agent-reviewed visual/PDF text transcription preserving wording and punctuation"}`

### 구조화된 과학 설명과 digest 분리

- GroundedExplanation blocks bind exact Knowledge, Rule, Equation, evaluator, and Evidence identities/digests.
- VerificationReport.report_digest is computed from a renderer-independent scientific payload.
- Markdown/PDF export_digest identifies exact rendered bytes and does not replace the scientific report digest.
- 즉, `VerificationReport.report_digest`는 renderer 전용 SVG/renderer/asset bytes를 제외한 과학적 기록을 식별하고, Markdown/PDF `export_digest`는 실제 내보내기 바이트를 식별한다. 둘을 서로 대신 사용하지 않는다.

## 자동 검증된 범위와 실제 표시 증거

- Equation manifest 자체 digest, 6개 asset digest/SVG digest, 접근성 문구를 검증하고, Catalog가 다시 검증한 Equation Knowledge·Evidence locator와 정확히 대조했다.
- 3개 `deterministic_rule` 수식은 exact Rule binding과 닫힌 evaluator identity를 다시 대조했다. 나머지 3개 `explanation_only` 수식은 판정 경로에 넣지 않았다.
- Science JUnit: tests=1689, failures=0, errors=0, skipped=0. 결과는 tracked suite identity digest가 일치할 때만 VERIFIED로 파생한다.
- 브라우저 증거는 입력 capture manifest의 passed check/capture만 보고한다: checks=27, captures=3. 수식 관련 입력 check: `equation_committed_asset_renders_exact_svg`, `equation_identity_and_evidence_visible`, `equation_details_copy_and_accessibility`, `equation_failures_keep_plain_fallback_without_red`, `equation_mobile_scroll_is_contained`, `equation_qa_is_explicitly_non_operational`.
- PDF 표시 QA: 안전 검증과 ReportLab 변환을 통과한 Candidate equation drawing=6. PDF export에는 이 수식들을 벡터 drawing으로 배치하지만, 이는 표시 QA이지 판정 근거가 아니다. 최종 PDF 바이트 digest는 `verification-manifest.json`의 `pdf.export_digest`에 기록한다.

## 판정 권한으로 지원하지 않는 수식 유형

| AST form | 의미 | 결정론적 판정 권한 | 허용 범위 |
|---|---|---|---|
| `vector` | vectors | 지원하지 않음 | 검토·근거 결합 시 설명/표시는 가능 |
| `matrix` | matrices | 지원하지 않음 | 검토·근거 결합 시 설명/표시는 가능 |
| `derivative` | derivatives | 지원하지 않음 | 검토·근거 결합 시 설명/표시는 가능 |
| `integral` | integrals | 지원하지 않음 | 검토·근거 결합 시 설명/표시는 가능 |
| `summation` | summations | 지원하지 않음 | 검토·근거 결합 시 설명/표시는 가능 |
| `chemical_reaction` | chemical reactions | 지원하지 않음 | 검토·근거 결합 시 설명/표시는 가능 |

복잡 수식을 단순화·재배열하거나 범용 CAS로 판정하지 않는다. vector/matrix/derivative/integral/summation/chemical reaction은 닫힌 AST에 보존할 수 있어도 현재 evaluator에서는 결정 권한이 없다.

## 설명 전용 수식

| 도메인 | Equation identity | plain fallback | 운영 경계 |
|---|---|---|---|
| Materials Science | `sci:equation:materials:arrhenius-diffusion` | `D = D0 * exp(-Ea / (kB*T))` | 설명·표시만 허용; 판정 권한 없음 |
| Semiconductor Devices | `sci:equation:semiconductor:low-field-conductivity` | `sigma = q*n*mu_n + q*p*mu_p` | 설명·표시만 허용; 판정 권한 없음 |
| Spin Coating | `sci:equation:spin-coating:drying-limited-power-law` | `h proportional to omega^(-1/2)` | 설명·표시만 허용; 판정 권한 없음 |

설명 전용 수식은 충분한 과학 설명과 근거 탐색에 사용할 수 있지만 빨간 밑줄, verdict, Rule 위반을 생성할 수 없다.

## Release Gate

| Gate | 기계 산출 상태 | 근거/대기 사항 |
|---|---|---|
| G0 | PASS | Schema, IDs, references, immutable component digests, and candidate lifecycle are valid. |
| G1 | PASS | Source/Evidence hashes and locator structures are internally reproducible. |
| G2 | PASS | Every public decision remains inside release-pinned Knowledge and Evidence. |
| G3 | PASS | All 440 public cases match their expected verdict or ambiguity gate. |
| G4 | PASS | Repeated public qualification is byte-stable. |
| G5 | PENDING | Independent sealed holdout is not commissioned. |
| G6 | PENDING | Web/REST/MCP/explanation/export parity must be established by the authoritative post-integration checker; caller assertions cannot pass this gate. |
| G7 | PENDING | Authorized human Admin review and activation must be resolved from the operational audit store; caller assertions cannot pass this gate. |

G5·G6·G7 또는 사람 Admin 승인 대기를 종합점수로 상쇄하지 않는다. 사람 Admin 승인과 독립 sealed holdout이 아직 대기 중이며 Release는 활성화되지 않았다. 구현 보고서가 FINAL이어도 **구현 증빙 묶음의 완료만** 의미하고 Science Knowledge Release의 승인·활성화·과학적 진실·공정 또는 안전 승인을 의미하지 않는다.
