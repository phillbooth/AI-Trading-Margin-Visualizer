import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_BOOT_TIMEOUT_SECONDS = 60
DEFAULT_DOCKER_BOOT_TIMEOUT_SECONDS = 90


def onyx_base_url():
    return os.getenv("ONYX_BASE_URL", "http://localhost:3000").rstrip("/")


def onyx_install_dir():
    raw = os.getenv("ONYX_INSTALL_DIR", "").strip()
    return Path(raw) if raw else None


def onyx_boot_timeout_seconds():
    try:
        return max(5, int(os.getenv("ONYX_BOOT_TIMEOUT_SECONDS", str(DEFAULT_BOOT_TIMEOUT_SECONDS))))
    except ValueError:
        return DEFAULT_BOOT_TIMEOUT_SECONDS


def docker_desktop_path():
    configured = os.getenv("DOCKER_DESKTOP_PATH", "").strip()
    candidates = [configured] if configured else []
    candidates.append(r"C:\Program Files\Docker\Docker\Docker Desktop.exe")
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw)
        if path.exists():
            return path
    return None


def docker_boot_timeout_seconds():
    try:
        return max(10, int(os.getenv("DOCKER_BOOT_TIMEOUT_SECONDS", str(DEFAULT_DOCKER_BOOT_TIMEOUT_SECONDS))))
    except ValueError:
        return DEFAULT_DOCKER_BOOT_TIMEOUT_SECONDS


def docker_available():
    return shutil.which("docker") is not None


def docker_running():
    if not docker_available():
        return False, "Docker CLI not found on PATH."

    result = subprocess.run(
        ["docker", "ps"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode == 0:
        return True, ""

    message = (result.stderr or result.stdout or "").strip() or "Docker is not responding."
    return False, message


def onyx_http_ok(timeout_seconds=3):
    url = f"{onyx_base_url()}/"
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            return 200 <= getattr(response, "status", 0) < 400, ""
    except URLError as error:
        return False, str(error.reason or error)
    except Exception as error:  # pragma: no cover - defensive surface
        return False, str(error)


def find_compose_dir(base_dir):
    candidates = [
        base_dir,
        base_dir / "deployment",
        base_dir / "deployment" / "docker_compose",
    ]
    compose_names = ("docker-compose.yml", "compose.yml", "compose.yaml")
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_dir():
            continue
        if any((candidate / name).exists() for name in compose_names):
            return candidate
    return None


def onyx_status():
    docker_ok, docker_message = docker_running()
    http_ok, http_message = onyx_http_ok()
    install_dir = onyx_install_dir()
    compose_dir = find_compose_dir(install_dir) if install_dir else None

    payload = {
        "onyx_base_url": onyx_base_url(),
        "onyx_http_ok": http_ok,
        "docker_ok": docker_ok,
        "docker_message": docker_message,
        "http_message": http_message,
        "install_dir": str(install_dir) if install_dir else "",
        "compose_dir": str(compose_dir) if compose_dir else "",
    }
    payload["ready"] = docker_ok and http_ok
    return payload


def ensure_docker_running():
    docker_ok, docker_message = docker_running()
    payload = {
        "docker_ok": docker_ok,
        "docker_message": docker_message,
        "docker_desktop_path": str(docker_desktop_path() or ""),
    }
    if docker_ok:
        payload["action"] = "already_running"
        return payload

    desktop_path = docker_desktop_path()
    if not desktop_path:
        payload["action"] = "missing_docker_desktop_path"
        payload["error"] = "Docker is not running and Docker Desktop executable was not found."
        return payload

    try:
        subprocess.Popen([str(desktop_path)])
    except Exception as error:  # pragma: no cover - defensive surface
        payload["action"] = "docker_start_failed"
        payload["error"] = str(error)
        return payload

    deadline = time.time() + docker_boot_timeout_seconds()
    while time.time() < deadline:
        docker_ok, docker_message = docker_running()
        if docker_ok:
            payload["docker_ok"] = True
            payload["docker_message"] = ""
            payload["action"] = "booted"
            return payload
        payload["docker_message"] = docker_message
        time.sleep(3)

    payload["action"] = "docker_boot_timeout"
    payload["error"] = (
        f"Docker did not become ready within {docker_boot_timeout_seconds()} seconds."
    )
    return payload


def ensure_onyx_running():
    status = onyx_status()
    if status["ready"]:
        status["action"] = "already_running"
        return status

    if status["onyx_http_ok"]:
        status["action"] = "http_ok"
        return status

    if not status["docker_ok"]:
        docker_status = ensure_docker_running()
        status["docker_boot"] = docker_status
        if not docker_status.get("docker_ok"):
            status["action"] = "docker_unavailable"
            status["error"] = docker_status.get("error") or docker_status.get("docker_message", "")
            return status
        status["docker_ok"] = True
        status["docker_message"] = ""

    if not status["docker_ok"]:
        status["action"] = "docker_unavailable"
        return status

    install_dir = onyx_install_dir()
    if not install_dir:
        status["action"] = "missing_install_dir"
        status["error"] = "Set ONYX_INSTALL_DIR in .env to allow local boot attempts."
        return status

    if not install_dir.exists():
        status["action"] = "missing_install_path"
        status["error"] = f"ONYX_INSTALL_DIR does not exist: {install_dir}"
        return status

    compose_dir = find_compose_dir(install_dir)
    if not compose_dir:
        status["action"] = "missing_compose_dir"
        status["error"] = "Could not find a Docker Compose file under ONYX_INSTALL_DIR."
        return status

    command = ["docker", "compose", "up", "-d"]
    result = subprocess.run(
        command,
        cwd=compose_dir,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    status["compose_dir"] = str(compose_dir)
    status["boot_command"] = " ".join(command)
    status["boot_stdout"] = (result.stdout or "").strip()
    status["boot_stderr"] = (result.stderr or "").strip()

    if result.returncode != 0:
        status["action"] = "boot_failed"
        status["error"] = status["boot_stderr"] or "docker compose up -d failed."
        return status

    deadline = time.time() + onyx_boot_timeout_seconds()
    while time.time() < deadline:
        http_ok, http_message = onyx_http_ok()
        if http_ok:
            status["onyx_http_ok"] = True
            status["http_message"] = ""
            status["ready"] = True
            status["action"] = "booted"
            return status
        status["http_message"] = http_message
        time.sleep(2)

    status["action"] = "boot_timeout"
    status["error"] = (
        f"Onyx did not respond at {onyx_base_url()} within {onyx_boot_timeout_seconds()} seconds."
    )
    return status
