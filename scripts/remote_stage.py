#!/usr/bin/env python3
"""Invoke an already-installed toolkit over existing, verified OpenSSH access."""
import argparse
import re
import shlex
import subprocess
import sys


def build_command(args):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.host):
        raise ValueError("Use an existing SSH config alias, not options or a password")
    for value in (args.remote_tool, args.policy, args.plan, args.decisions):
        if value is not None and (not value.startswith("/") or any(ord(c) < 32 for c in value)):
            raise ValueError("Remote paths must be absolute and contain no control characters")
    command = ["python3", "-I", args.remote_tool, "--policy", args.policy, args.action]
    if args.action == "plan":
        if not args.name:
            raise ValueError("plan requires --name")
        command += ["--name", args.name]
        if args.decisions:
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
    return ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ForwardAgent=no",
            "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=10", args.host, shlex.join(command)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--remote-tool", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("action", choices=("inventory", "plan", "apply", "verify"))
    parser.add_argument("--name")
    parser.add_argument("--decisions")
    parser.add_argument("--plan")
    parser.add_argument("--approve-plan")
    args = parser.parse_args()
    try:
        return subprocess.call(build_command(args))
    except (OSError, ValueError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted SSH: reconnect and inspect remote status before retrying.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
