from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT = Path("scripts/nas_auto_pull_deploy.sh").resolve()
TASK_SCRIPT = Path("scripts/nas_auto_pull_task.sh").resolve()


def run(cmd: list[str], cwd: Path, **kwargs):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, **kwargs)


def git(cwd: Path, *args: str) -> None:
    result = run(["git", *args], cwd=cwd)
    assert result.returncode == 0, result.stderr


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    git(repo, "init")
    git(repo, "checkout", "-b", "main")
    git(repo, "config", "user.email", "nas-test@example.invalid")
    git(repo, "config", "user.name", "NAS Test")


def run_deploy_script(app_dir: Path, *, lock_dir: Path, extra_env: dict[str, str] | None = None):
    env = os.environ.copy()
    env.update(
        {
            "APP_DIR": str(app_dir),
            "LOCK_DIR": str(lock_dir),
            "BRANCH": "main",
        }
    )
    if extra_env:
        env.update(extra_env)
    return run(["bash", str(SCRIPT)], cwd=app_dir, env=env)


def setup_remote_worktree(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    app = tmp_path / "app"

    git(tmp_path, "init", "--bare", str(origin))
    init_repo(work)
    write(
        work / "docker-compose.yml",
        "name: boi-poc\nservices:\n  app:\n    image: busybox\n    depends_on:\n      init:\n        condition: service_completed_successfully\n",
    )
    write(work / "README.md", "# BoI Wiki\n")
    commit_all(work, "initial")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-u", "origin", "main")
    git(tmp_path, "--git-dir", str(origin), "symbolic-ref", "HEAD", "refs/heads/main")
    git(tmp_path, "clone", str(origin), str(app))
    return work, app


def classify(*paths: str) -> str:
    result = run(["bash", str(SCRIPT), "--classify-only", *paths], cwd=SCRIPT.parent.parent)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_script_contains_required_safety_contracts():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "git pull --ff-only" in text
    assert "mkdir \"$LOCK_DIR\"" in text
    assert "set +x" in text
    assert "DEPLOY_STATUS=" in text
    assert "service_completed_successfully" in text
    assert "service_started" in text
    assert "cat \"$ENV_FILE\"" not in text
    assert "set -x" not in text


def test_task_wrapper_rotates_logs_and_preserves_final_marker(tmp_path: Path):
    text = TASK_SCRIPT.read_text(encoding="utf-8")

    assert "LOG_MAX_BYTES" in text
    assert "LOG_ROTATE_KEEP" in text
    assert "DEPLOY_STATUS=failed" in text
    assert "set +x" in text
    assert "set -x" not in text

    app = tmp_path / "app"
    log_dir = tmp_path / "logs"
    deploy_script = app / "scripts" / "nas_auto_pull_deploy.sh"
    write(
        deploy_script,
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf 'deploy body\\n'\n"
        "printf 'DEPLOY_STATUS=noop\\n'\n",
    )
    log_dir.mkdir()
    log_file = log_dir / "autopull.log"
    log_file.write_text("x" * 80, encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "APP_DIR": str(app),
            "LOG_DIR": str(log_dir),
            "LOG_MAX_BYTES": "64",
            "LOG_ROTATE_KEEP": "2",
        }
    )

    result = run(["bash", str(TASK_SCRIPT)], cwd=tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    assert log_file.read_text(encoding="utf-8").splitlines()[-1] == "DEPLOY_STATUS=noop"
    assert (log_dir / "autopull.log.1").read_text(encoding="utf-8") == "x" * 80
    assert "LOG_ROTATED" in log_file.read_text(encoding="utf-8")


def test_classify_hot_reload_paths_do_not_require_compose():
    assert classify(
        "data/boi/public/example.md",
        "data/event_catalog/event_types.yaml",
        "data/action_catalog/actions.yaml",
        "docs/V0_4_PEER_CONNECTOR_MODEL.md",
        "README.md",
    ) == "hot_reload"


def test_classify_runtime_paths_require_compose():
    for path in [
        "boi_api/app/main.py",
        "docker-compose.yml",
        "boi_api/Dockerfile",
        "boi_api/requirements.txt",
    ]:
        assert classify(path) == "compose_required"


def test_dirty_tracked_worktree_blocks_pull(tmp_path: Path):
    app = tmp_path / "dirty-app"
    init_repo(app)
    write(app / "docker-compose.yml", "services: {}\n")
    write(app / "README.md", "# clean\n")
    commit_all(app, "initial")
    write(app / "README.md", "# dirty\n")

    result = run_deploy_script(app, lock_dir=tmp_path / "dirty.lock")

    assert result.returncode == 2
    assert "tracked working tree changes exist" in result.stdout
    assert "DEPLOY_STATUS=blocked" in result.stdout.splitlines()[-1]


def test_hot_reload_pull_skips_compose_and_runtime_change_generates_nas_compose(tmp_path: Path):
    work, app = setup_remote_worktree(tmp_path)

    write(work / "README.md", "# BoI Wiki\n\nDocs-only update.\n")
    commit_all(work, "docs update")
    git(work, "push", "origin", "main")

    docs_result = run_deploy_script(app, lock_dir=tmp_path / "docs.lock")

    assert docs_result.returncode == 0, docs_result.stderr
    assert "hot-reload-only change set" in docs_result.stdout
    assert "DEPLOY_STATUS=success" in docs_result.stdout.splitlines()[-1]
    assert not (app / "docker-compose.nas.yml").exists()

    write(work / "boi_api/app/main.py", "print('runtime change')\n")
    commit_all(work, "runtime update")
    git(work, "push", "origin", "main")
    write(app / ".env", "SERVICE_TOKEN=redacted-test-token\n")

    runtime_result = run_deploy_script(
        app,
        lock_dir=tmp_path / "runtime.lock",
        extra_env={"NAS_AUTO_PULL_DRY_RUN": "1"},
    )

    assert runtime_result.returncode == 0, runtime_result.stderr
    assert "dry run: would run docker-compose up -d --build" in runtime_result.stdout
    assert "DEPLOY_STATUS=success" in runtime_result.stdout.splitlines()[-1]
    compose = (app / "docker-compose.nas.yml").read_text(encoding="utf-8")
    assert not compose.startswith("name:")
    assert "service_completed_successfully" not in compose
    assert "service_started" in compose
