import json
import os
import pathlib
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
POWERSHELL = "powershell.exe"


def run(*args, cwd=None, env=None, check=True):
    completed = subprocess.run(
        [str(a) for a in args],
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode:
        raise AssertionError(
            f"command failed ({completed.returncode}): {args}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def git(*args, cwd=None):
    return run("git", *args, cwd=cwd).stdout.strip()


def make_checkout(base: pathlib.Path):
    work = base / "work"
    work.mkdir()
    git("init", "-b", "main", cwd=work)
    git("config", "user.email", "test@example.invalid", cwd=work)
    git("config", "user.name", "BoI Test", cwd=work)
    (work / "README.md").write_text("test\n", encoding="utf-8")
    git("add", "README.md", cwd=work)
    git("commit", "-m", "initial", cwd=work)
    return work


def make_bare(base: pathlib.Path, source: pathlib.Path, name: str):
    bare = base / name
    git("clone", "--bare", str(source), str(bare), cwd=base)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=bare)
    return bare


def write_manifest(path: pathlib.Path, internal: str, external: str):
    path.write_text(
        json.dumps(
            {
                "schema": "boi-repository-sources/v1",
                "probe": {"timeout_seconds": 2, "network_retry_count": 1},
                "repositories": {
                    "boi-wiki-local": {
                        "internal_url": internal,
                        "external_url": external,
                        "stable_branch": "main",
                        "markers": ["README.md"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def selector(work: pathlib.Path, manifest: pathlib.Path, mode="Preview", plan_hash="", check=True):
    command = [
        POWERSHELL,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ROOT / "scripts" / "select-repository-source.ps1",
        "-Mode",
        mode,
        "-Root",
        work,
        "-RepositoryId",
        "boi-wiki-local",
        "-ManifestPath",
        manifest,
        "-ProbeTimeoutSeconds",
        "2",
        "-NetworkRetryCount",
        "1",
    ]
    if plan_hash:
        command.extend(["-ConfirmPlanHash", plan_hash])
    result = run(*command, check=check)
    payload = json.loads(result.stdout) if result.stdout.strip() else None
    return result, payload


class UnauthorizedHandler(BaseHTTPRequestHandler):
    requests = 0

    def do_GET(self):
        type(self).requests += 1
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="boi-test"')
        self.end_headers()

    def log_message(self, *_args):
        pass


class McpHandler(BaseHTTPRequestHandler):
    required_tools = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        if request.get("method") == "initialize":
            payload = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "serverInfo": {"name": "boi-test", "version": "1"},
                },
            }
        elif request.get("method") == "tools/list":
            payload = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {"tools": [{"name": name} for name in self.required_tools]},
            }
        else:
            payload = {"jsonrpc": "2.0", "result": {}}
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Mcp-Session-Id", "boi-test-session")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class RepositorySourceContractTests(unittest.TestCase):
    def test_internal_success_skips_external_probe(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            work = make_checkout(base)
            internal = make_bare(base, work, "internal.git")
            manifest = base / "sources.json"
            write_manifest(manifest, str(internal), "http://127.0.0.1:1/never.git")
            _, preview = selector(work, manifest)
            self.assertEqual(preview["state"], "internal-readable")
            self.assertIsNone(preview["probes"]["external"])
            self.assertEqual(preview["probes"]["internal"]["attempts"].__len__(), 1)

    def test_network_failure_falls_back_and_apply_verify_rollback_are_hash_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            work = make_checkout(base)
            external = make_bare(base, work, "external.git")
            git("remote", "add", "origin", "https://example.invalid/old.git", cwd=work)
            manifest = base / "sources.json"
            write_manifest(manifest, "http://127.0.0.1:1/internal.git", str(external))
            _, preview = selector(work, manifest)
            self.assertEqual(preview["state"], "external-readable")
            self.assertEqual(len(preview["probes"]["internal"]["attempts"]), 2)
            wrong, _ = selector(work, manifest, mode="Apply", plan_hash="0" * 64, check=False)
            self.assertNotEqual(wrong.returncode, 0)
            _, applied = selector(work, manifest, mode="Apply", plan_hash=preview["plan_hash"])
            self.assertTrue(applied["ok"])
            self.assertEqual(git("remote", "get-url", "origin", cwd=work), str(external))
            _, verified = selector(work, manifest, mode="Verify")
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["stable_branch"], "main")
            _, rollback_preview = selector(work, manifest, mode="Rollback")
            _, rolled_back = selector(
                work, manifest, mode="Rollback", plan_hash=rollback_preview["plan_hash"]
            )
            self.assertTrue(rolled_back["ok"])
            self.assertEqual(
                git("remote", "get-url", "origin", cwd=work),
                "https://example.invalid/old.git",
            )

    def test_internal_auth_failure_never_probes_external(self):
        UnauthorizedHandler.requests = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), UnauthorizedHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                base = pathlib.Path(temp)
                work = make_checkout(base)
                external = make_bare(base, work, "external.git")
                manifest = base / "sources.json"
                write_manifest(
                    manifest,
                    f"http://127.0.0.1:{server.server_port}/internal.git",
                    str(external),
                )
                _, preview = selector(work, manifest)
                self.assertEqual(
                    preview["state"], "internal-auth-or-repository-access-required"
                )
                self.assertEqual(preview["action"], "blocked")
                self.assertIsNone(preview["probes"]["external"])
                self.assertGreater(UnauthorizedHandler.requests, 0)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_offline_existing_keeps_origin_and_blocks_update(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            work = make_checkout(base)
            old_origin = "https://example.invalid/unchanged.git"
            git("remote", "add", "origin", old_origin, cwd=work)
            manifest = base / "sources.json"
            write_manifest(
                manifest,
                "http://127.0.0.1:1/internal.git",
                "http://127.0.0.1:1/external.git",
            )
            _, preview = selector(work, manifest)
            self.assertEqual(preview["state"], "offline-existing")
            self.assertEqual(preview["action"], "blocked")
            self.assertEqual(git("remote", "get-url", "origin", cwd=work), old_origin)

    def test_origin_drift_invalidates_approved_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            work = make_checkout(base)
            external = make_bare(base, work, "external.git")
            git("remote", "add", "origin", "https://example.invalid/old.git", cwd=work)
            manifest = base / "sources.json"
            write_manifest(manifest, "http://127.0.0.1:1/internal.git", str(external))
            _, preview = selector(work, manifest)
            git("remote", "set-url", "origin", "https://example.invalid/drift.git", cwd=work)
            result, _ = selector(
                work, manifest, mode="Apply", plan_hash=preview["plan_hash"], check=False
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(
                git("remote", "get-url", "origin", cwd=work),
                "https://example.invalid/drift.git",
            )

    def test_candidate_mirror_may_advance_when_it_contains_current_stable(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            work = make_checkout(base)
            external = make_bare(base, work, "external.git")
            git("remote", "add", "origin", str(external), cwd=work)
            git("fetch", "origin", "main", cwd=work)
            advanced = base / "advanced"
            git("clone", str(external), str(advanced), cwd=base)
            git("config", "user.email", "test@example.invalid", cwd=advanced)
            git("config", "user.name", "BoI Test", cwd=advanced)
            (advanced / "NEXT.md").write_text("next\n", encoding="utf-8")
            git("add", "NEXT.md", cwd=advanced)
            git("commit", "-m", "next", cwd=advanced)
            git("push", "origin", "main", cwd=advanced)
            internal = make_bare(base, advanced, "internal.git")
            manifest = base / "sources.json"
            write_manifest(manifest, str(internal), str(external))
            _, preview = selector(work, manifest)
            self.assertEqual(preview["state"], "internal-readable")
            self.assertEqual(preview["action"], "set-origin")
            self.assertEqual(
                preview["mirror_status"], "candidate-contains-current-stable"
            )
            self.assertEqual(git("remote", "get-url", "origin", cwd=work), str(external))

    def test_diverged_mirror_history_blocks_switch(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            work = make_checkout(base)
            external = make_bare(base, work, "external.git")
            git("remote", "add", "origin", str(external), cwd=work)
            git("fetch", "origin", "main", cwd=work)
            unrelated_source = base / "unrelated"
            unrelated_source.mkdir()
            git("init", "-b", "main", cwd=unrelated_source)
            git("config", "user.email", "test@example.invalid", cwd=unrelated_source)
            git("config", "user.name", "BoI Test", cwd=unrelated_source)
            (unrelated_source / "OTHER.md").write_text("other\n", encoding="utf-8")
            git("add", "OTHER.md", cwd=unrelated_source)
            git("commit", "-m", "unrelated", cwd=unrelated_source)
            internal = make_bare(base, unrelated_source, "internal.git")
            manifest = base / "sources.json"
            write_manifest(manifest, str(internal), str(external))
            _, preview = selector(work, manifest)
            self.assertEqual(preview["state"], "mirror-sync-required")
            self.assertEqual(preview["action"], "blocked")
            self.assertEqual(
                preview["mirror_status"], "stable-history-diverged-or-incomplete"
            )
            self.assertEqual(git("remote", "get-url", "origin", cwd=work), str(external))


class McpConnectionContractTests(unittest.TestCase):
    def test_codex_preview_apply_and_rollback_preserve_unrelated_config_and_token(self):
        script = ROOT / "scripts" / "connect-boi-wiki-mcp.ps1"
        descriptor = (
            ROOT / "templates" / "mcp" / "boi-wiki-mcp-connection.json"
            if (ROOT / "templates" / "mcp" / "boi-wiki-mcp-connection.json").exists()
            else ROOT / "config" / "boi-wiki-mcp-connection.json"
        )
        with tempfile.TemporaryDirectory() as temp:
            config_root = pathlib.Path(temp)
            original = 'model = "test"\n'
            (config_root / "config.toml").write_text(original, encoding="utf-8")
            env = os.environ.copy()
            env["BOI_WIKI_MCP_SERVICE_TOKEN"] = "must-not-appear"

            common = [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script,
                "-Client",
                "Codex",
                "-Endpoint",
                "http://127.0.0.1:9/mcp",
                "-DescriptorPath",
                descriptor,
                "-ClientConfigRoot",
                config_root,
            ]
            preview_result = run(*common, "-Mode", "Preview", env=env)
            preview = json.loads(preview_result.stdout)
            self.assertNotIn("must-not-appear", preview_result.stdout + preview_result.stderr)
            apply_result = run(
                *common,
                "-Mode",
                "Apply",
                "-ConfirmPlanHash",
                preview["plan_hash"],
                env=env,
            )
            self.assertNotIn("must-not-appear", apply_result.stdout + apply_result.stderr)
            configured = (config_root / "config.toml").read_text(encoding="utf-8")
            self.assertIn(original.strip(), configured)
            self.assertIn("bearer_token_env_var", configured)
            self.assertNotIn("must-not-appear", configured)

            rollback_preview = json.loads(
                run(*common, "-Mode", "Rollback", env=env).stdout
            )
            run(
                *common,
                "-Mode",
                "Rollback",
                "-ConfirmPlanHash",
                rollback_preview["plan_hash"],
                env=env,
            )
            self.assertEqual(
                (config_root / "config.toml").read_text(encoding="utf-8"), original
            )

    def test_verify_runs_initialize_and_tools_list_without_private_content(self):
        descriptor = (
            ROOT / "templates" / "mcp" / "boi-wiki-mcp-connection.json"
            if (ROOT / "templates" / "mcp" / "boi-wiki-mcp-connection.json").exists()
            else ROOT / "config" / "boi-wiki-mcp-connection.json"
        )
        descriptor_data = json.loads(descriptor.read_text(encoding="utf-8"))
        McpHandler.required_tools = descriptor_data["verification"]["required_tools"]
        server = ThreadingHTTPServer(("127.0.0.1", 0), McpHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                result = run(
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    ROOT / "scripts" / "connect-boi-wiki-mcp.ps1",
                    "-Mode",
                    "Verify",
                    "-Client",
                    "Codex",
                    "-AuthMode",
                    "None",
                    "-Endpoint",
                    f"http://127.0.0.1:{server.server_port}/mcp",
                    "-DescriptorPath",
                    descriptor,
                    "-ClientConfigRoot",
                    temp,
                )
                payload = json.loads(result.stdout)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["state"], "verified")
                self.assertEqual(payload["local_private_bytes_sent"], 0)
                self.assertEqual(payload["write_tools_invoked"], 0)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
