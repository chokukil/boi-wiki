# BoI Wiki Native Agent Kit

Installable Codex and Claude guidance for evidence-bound knowledge assetization and reuse. Wiki stores permissions, source/revision evidence and durable tasks; the configured external host interprets material and submits actual work. The bundle has no repository-runtime dependency and does not execute a hidden model.

Install all shared/domain skills, references and the HTTP helper:

```bash
python3 agent_kit/install.py --client codex
python3 agent_kit/install.py --client claude --target /chosen/skills/boi-wiki-v2
```

The existing shell entry `scripts/install_boi_agent_kit.sh` forwards the same options. Default targets are the configured Codex skills directory or `~/.claude/skills/boi-wiki-v2`. `--target` is the complete package directory. Reinstallation preserves a changed existing installation as a sibling backup and retains unmanaged files; identical installations are unchanged. Verify local files with `python3 install.py --verify --target INSTALLED_DIRECTORY` from the package source or installed directory.

Distribute without a repository checkout:

```bash
python3 agent_kit/install.py --bundle /chosen/boi-agent-kit.zip
```

Extract the archive, then run its `boi-agent-kit/install.py --client codex` or `--client claude`. The archive contains both host entries, package metadata, every relative skill/reference dependency and the standard-library HTTP helper. Installation requires no server checkout or database. Local preparation additionally uses the bundled exact contract runtime and pinned Python dependencies.

For new data, follow [portable local preparation and HOTL delivery](references/local-preparation.md). The external agent reads the source, authors meaning and checks a local bundle with the shipped `scripts/boi_local.py`. Its exact manifest is admitted under the authenticated actor's current write and model-input rights; item and bundle confirmation are not required in this HOTL path. The official binary uploader sends only missing offsets after reading the admitted bundle's status. Browser confirmation remains available as a separate mechanism.

The optional [portable SDK2 client](scripts/boi_mcp.py) and its [versioned dependencies](runtime/mcp-requirements.txt) are included in the distribution. Install those dependencies only for hosts needing the Python SDK2 transport; the standard-library HTTP helper remains independent. The contract-only local runtime deliberately excludes server applications and network clients.

Use the user's configured native BoI MCP connection, `boi_bootstrap`, then `boi_knowledge_work` for task creation/continuation. An opaque task reference is sufficient to restore server work from another configured host. For hosts using HTTP, configure `BOI_BASE_URL` and a secret environment token named `BOI_PAT`, then use [the portable helper](scripts/boi_knowledge_work.py) and [task operations](references/host-work.md). Do not paste secrets into chat or package files.

User corrections and stop requests use [supervision operations](references/supervision.md), preserving the exact affected task/definition revisions. Reading or resolving an instruction is not a semantic approval. The installed helper transports list, read, correct, resolve and stop; availability still depends on the connected server version.

Read [common workflow](skills/boi-domain-work/SKILL.md), [source intake](skills/boi-source-intake/SKILL.md), and only the applicable [process](skills/boi-process-knowledge/SKILL.md), [SVID](skills/boi-svid-knowledge/SKILL.md), [DEXA](skills/boi-dexa-knowledge/SKILL.md) or [science](skills/boi-science-knowledge/SKILL.md) guidance. Existing detailed semantic/recovery instructions remain linked references. Novel domains preserve common knowledge and expose required extensions rather than forcing a known schema.

For reusable domain extensions, follow [package authoring and qualification](references/package-operations.md). The external agent uses server-discovered schemas and frozen criteria, actual independent evaluation/trial evidence, and team adoption/observation/withdrawal. Without the configured evaluator or policy, the package remains unqualified.

Current server contracts determine available stages and output shapes. Installation does not prove source review, semantic coverage, scientific truth, production authority or live equipment binding. Preserve source/meaning revisions and failed or unknown attempts; do not reingest unchanged sources or treat a saved proposal as an executed result.

For prepared knowledge in Public, Team or Private spaces, use [Profile discovery, typed queries and index recovery](references/typed-knowledge-query.md). The external host selects meaning from exact declarations; the server executes logical queries and protects saved results. An editor can rebuild a missing Profile index from its unchanged native revision without reuploading the source or changing its use qualification.

The query reference also describes explicit retrieval-expression provenance and current Published explain-qualified composition. The installed transport can submit these connected-server contracts; repository response-review/model helpers are not included or automatically run. See the final explanation section before claiming reviewed or meaning-reused answers.

For SQLite or the existing query gateway, use [DB knowledge intake](references/database-intake.md). The installed adapter preserves paged rows, nulls, duplicates and exact source spans for the same Profile/OKF publication path.
