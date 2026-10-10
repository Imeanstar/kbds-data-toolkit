#!/usr/bin/env python3
"""Run the KBDS toolkit through direct SSH or a user-authenticated local bridge."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import time
import uuid
import zlib


HOST_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
USER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
TOKEN_RE = re.compile(r"[0-9a-f]{64}")
MAX_REMOTE_COMMAND = 65536


def validate_endpoint(host, user, port):
    if not host or not HOST_RE.fullmatch(host):
        raise ValueError("Use an SSH alias, IPv4 address or hostname, not SSH options")
    if user and not USER_RE.fullmatch(user):
        raise ValueError("Invalid SSH user")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("SSH port must be between 1 and 65535")


def remote_command(args):
    if args.action == "check":
        return "printf 'KBDS_BRIDGE_OK\\n'"
    local_tool = getattr(args, "local_tool", None)
    remote_tool = getattr(args, "remote_tool", None)
    local_policy = getattr(args, "local_policy", None)
    remote_policy = getattr(args, "policy", None)
    if bool(local_tool) == bool(remote_tool):
        raise ValueError("remote action requires exactly one of --local-tool/--remote-tool")
    if local_tool and (not local_policy or remote_policy):
        raise ValueError("--local-tool requires --local-policy and forbids remote --policy")
    if remote_tool and (not remote_policy or local_policy):
        raise ValueError("--remote-tool requires remote --policy")
    for value in (remote_tool, remote_policy, args.plan, args.decisions):
        if value is not None and (not value.startswith("/") or any(ord(c) < 32 for c in value)):
            raise ValueError("Remote paths must be absolute and contain no control characters")
    if local_tool:
        source = Path(local_tool).expanduser()
        if source.is_symlink():
            raise ValueError("Local tool must be a regular non-symlink file")
        path = source.resolve()
        if not path.is_file():
            raise ValueError("Local tool must be a regular non-symlink file")
        payload = base64.b64encode(zlib.compress(path.read_bytes(), level=9)).decode("ascii")
        launcher = ("import base64,zlib;exec(compile(zlib.decompress(base64.b64decode(" +
                    repr(payload) + ")), '<kbds-data-organizer>', 'exec'))")
        command = ["python3", "-I", "-c", launcher, "--policy-data",
                   encoded_local_json(local_policy, "policy"), args.action]
    else:
        command = ["python3", "-I", remote_tool, "--policy", remote_policy, args.action]
    if args.action == "plan":
        if not args.name:
            raise ValueError("plan requires --name")
        command += ["--name", args.name]
        local_decisions = getattr(args, "local_decisions", None)
        if local_tool and args.decisions:
            raise ValueError("--local-tool forbids remote --decisions")
        if remote_tool and local_decisions:
            raise ValueError("--remote-tool does not accept --local-decisions")
        if local_decisions:
            command += ["--decisions-data", encoded_local_json(local_decisions, "decisions")]
        elif args.decisions:
            command += ["--decisions", args.decisions]
    elif args.action in ("apply", "verify"):
        if not args.plan:
            raise ValueError("apply/verify require --plan")
        command += ["--plan", args.plan]
        if args.action == "apply":
            if not re.fullmatch(r"[0-9a-f]{64}", args.approve_plan or ""):
                raise ValueError("apply requires the exact approved plan hash")
            command += ["--approve-plan", args.approve_plan]
    elif args.action != "inventory":
        raise ValueError("Unsupported action")
    result = shlex.join(command)
    if len(result) > MAX_REMOTE_COMMAND:
        raise ValueError("Encoded local tool is too large for the SSH bridge")
    return result


def encoded_local_json(value, label):
    source = Path(value).expanduser()
    if source.is_symlink():
        raise ValueError(f"Local {label} must be a regular non-symlink JSON file")
    path = source.resolve()
    if not path.is_file():
        raise ValueError(f"Local {label} must be a regular non-symlink JSON file")
    data = json.loads(path.read_text(encoding="utf-8"))
    packed = zlib.compress(json.dumps(data, ensure_ascii=True, separators=(",", ":")).encode("ascii"), level=9)
    return base64.b64encode(packed).decode("ascii")


def ssh_options():
    return ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ForwardAgent=no", "-o", "ClearAllForwardings=yes",
            "-o", "ConnectTimeout=10"]


def endpoint_options(user, port):
    options = []
    if port is not None:
        options += ["-p", str(port)]
    if user:
        options += ["-l", user]
    return options


def build_command(args):
    validate_endpoint(args.host, getattr(args, "user", None), getattr(args, "port", None))
    ssh = getattr(args, "ssh", None) or "ssh"
    return ([ssh] + ssh_options() + endpoint_options(getattr(args, "user", None),
                                                     getattr(args, "port", None))
            + [args.host, remote_command(args)])


def find_ssh(explicit=None):
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"SSH executable not found: {path}")
        return str(path)
    if os.name != "nt":
        path = shutil.which("ssh")
        if path:
            return path
        raise ValueError("OpenSSH client not found")
    candidates = []
    git = shutil.which("git")
    if git:
        root = Path(git).resolve().parent.parent
        candidates += [root / "usr/bin/ssh.exe", root / "bin/ssh.exe"]
    for variable in ("ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            candidates += [Path(base) / "Git/usr/bin/ssh.exe",
                           Path(base) / "Programs/Git/usr/bin/ssh.exe"]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise ValueError("Git for Windows ssh.exe is required for password handoff on Windows")


def atomic_json(path, data):
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def state_root(value):
    path = Path(value).expanduser().resolve()
    if path.exists() and path.is_symlink():
        raise ValueError("Bridge state directory must not be a symlink")
    return path


def load_state(root):
    path = root / "state.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"No active SSH bridge at {root}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("version") != 1 or not TOKEN_RE.fullmatch(data.get("token", ""))
            or not isinstance(data.get("pid"), int)):
        raise ValueError("Invalid SSH bridge state")
    validate_endpoint(data.get("host"), data.get("user"), data.get("port"))
    return data


def session_command(ssh, host, user, port):
    return ([ssh, "-T", "-o", "StrictHostKeyChecking=ask", "-o", "ForwardAgent=no",
             "-o", "ClearAllForwardings=yes", "-o", "ServerAliveInterval=30",
             "-o", "ServerAliveCountMax=3"] + endpoint_options(user, port) + [host, "sh"])


def run_session_command(session, command, token, request_id):
    if session.poll() is not None:
        raise RuntimeError("SSH session is no longer running")
    marker = f"__KBDS_{token}_{request_id}"
    begin = marker + "_BEGIN__"
    end = marker + "_END__"
    script = (f"printf '%s\\n' {shlex.quote(begin)}\n"
              f"(\n{command}\n) 2>&1\n"
              "kbds_status=$?\n"
              f"printf '\\n%s:%s\\n' {shlex.quote(end)} \"$kbds_status\"\n")
    session.stdin.write(script.encode("utf-8"))
    session.stdin.flush()
    output = []
    started = False
    while True:
        raw_line = session.stdout.readline()
        if raw_line == b"":
            raise RuntimeError("SSH session closed before returning a result")
        line = raw_line.decode("utf-8", errors="replace")
        text = line.rstrip("\r\n")
        if text == begin:
            started = True
            continue
        if started and text.startswith(end + ":"):
            status = text[len(end) + 1:]
            if not status.isdigit():
                raise RuntimeError("SSH session returned an invalid status marker")
            # Remove only the framing newline; preserve the command's exact stdout.
            framed_output = "".join(output)
            if not framed_output.endswith("\n"):
                raise RuntimeError("SSH session returned an invalid output separator")
            return int(status), framed_output[:-1]
        if started:
            output.append(line)


def response_name(request_path):
    return request_path.name.replace(".request.json", ".response.json")


def handle_request(request_path, responses, token, session):
    try:
        if request_path.is_symlink():
            raise ValueError("Symlink requests are not accepted")
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if request.get("token") != token:
            raise ValueError("Bridge token mismatch")
        operation = request.get("operation")
        if operation == "close":
            response = {"returncode": 0, "stdout": "", "stderr": ""}
            closing = True
        elif operation == "run":
            command = request.get("command")
            if not isinstance(command, str) or not command or len(command) > MAX_REMOTE_COMMAND or "\0" in command:
                raise ValueError("Invalid remote command")
            returncode, output = run_session_command(
                session, command, token, request_path.name.split(".", 1)[0])
            response = {"returncode": returncode, "stdout": output, "stderr": ""}
            closing = False
        else:
            raise ValueError("Unknown bridge operation")
    except Exception as exc:
        response = {"returncode": 2, "stdout": "", "stderr": "BLOCKED: " + str(exc) + "\n"}
        closing = False
    response_path = responses / response_name(request_path)
    atomic_json(response_path, response)
    request_path.unlink(missing_ok=True)
    return closing, response_path


def run_bridge(args):
    validate_endpoint(args.host, args.user, args.port)
    ssh = find_ssh(args.ssh)
    root = state_root(args.bridge_state)
    if root.exists():
        raise ValueError(f"Bridge state already exists: {root}")
    root.mkdir(parents=True)
    requests = root / "requests"
    responses = root / "responses"
    requests.mkdir()
    responses.mkdir()
    if os.name != "nt":
        root.chmod(0o700)
    token = secrets.token_hex(32)
    session = None
    close_response = None
    try:
        print("Verify any new host fingerprint, then enter the SSH password.", flush=True)
        session = subprocess.Popen(session_command(ssh, args.host, args.user, args.port),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        run_session_command(session, ":", token, "ready")
        atomic_json(root / "state.json", {"version": 1, "token": token, "pid": os.getpid(),
                                          "host": args.host, "user": args.user, "port": args.port})
        print(f"KBDS SSH bridge ready at {root}", flush=True)
        print("Leave this terminal open and reply 로그인완료 in Codex.", flush=True)
        closing = False
        while not closing:
            found = False
            for request_path in sorted(requests.glob("*.request.json")):
                found = True
                closing, response_path = handle_request(request_path, responses, token, session)
                if closing:
                    close_response = response_path
                    break
            if not found and not closing:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("Closing SSH bridge.", file=sys.stderr)
    finally:
        if session is not None and session.poll() is None:
            try:
                session.stdin.write(b"exit\n")
                session.stdin.flush()
                session.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                session.terminate()
        if close_response:
            deadline = time.monotonic() + 5
            while close_response.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
        shutil.rmtree(root, ignore_errors=True)
    return 0


def submit(root, operation, command=None, timeout=86400, output=None):
    state = load_state(root)
    request_id = uuid.uuid4().hex
    request = {"version": 1, "token": state["token"], "operation": operation}
    if command is not None:
        request["command"] = command
    request_path = root / "requests" / f"{request_id}.request.json"
    response_path = root / "responses" / f"{request_id}.response.json"
    atomic_json(request_path, request)
    deadline = time.monotonic() + timeout
    while not response_path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("Bridge response timed out; the remote command may still be running")
        time.sleep(0.1)
    if response_path.is_symlink():
        raise ValueError("Symlink responses are not accepted")
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response_path.unlink()
    stdout = response.get("stdout", "")
    if output:
        path = Path(output).expanduser()
        if path.exists() or path.is_symlink() or not path.parent.resolve().is_dir():
            raise ValueError("Local output must be a new file under an existing directory")
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(stdout)
        print(f"LOCAL_OUTPUT\t{path.resolve()}")
    else:
        sys.stdout.write(stdout)
    sys.stderr.write(response.get("stderr", ""))
    return int(response.get("returncode", 2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host")
    parser.add_argument("--user")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--ssh")
    parser.add_argument("--bridge-state", default=".kbds-ssh-bridge")
    parser.add_argument("--bridge-timeout", type=float, default=86400)
    parser.add_argument("--remote-tool")
    parser.add_argument("--local-tool")
    parser.add_argument("--policy")
    parser.add_argument("--local-policy")
    parser.add_argument("--output")
    parser.add_argument("action", choices=("bridge-open", "bridge-close", "check",
                                           "inventory", "plan", "apply", "verify"))
    parser.add_argument("--name")
    parser.add_argument("--decisions")
    parser.add_argument("--local-decisions")
    parser.add_argument("--plan")
    parser.add_argument("--approve-plan")
    args = parser.parse_args(argv)
    try:
        root = state_root(args.bridge_state)
        if args.action == "bridge-open":
            if not args.host or not args.user:
                raise ValueError("bridge-open requires --host and --user")
            return run_bridge(args)
        if args.action == "bridge-close":
            return submit(root, "close", timeout=min(args.bridge_timeout, 30))
        command = remote_command(args)
        if (root / "state.json").is_file():
            return submit(root, "run", command=command, timeout=args.bridge_timeout,
                          output=args.output)
        if not args.host:
            raise ValueError("No active bridge; direct SSH requires --host")
        return subprocess.call(build_command(args))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, TimeoutError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted SSH: reconnect and inspect remote status before retrying.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
