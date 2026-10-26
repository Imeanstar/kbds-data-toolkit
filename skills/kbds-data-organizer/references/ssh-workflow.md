# Password-only SSH handoff

Use the full repository's local `scripts/remote_stage.py` bridge. Collect the endpoint and
exact source/destination/workspace from the user or existing approved private policy.
Keep the toolkit and policy/decision JSON local; do not install tools, register keys or store passwords.
This bridge is for an explicitly authorized off-host workflow. Server-local Qwen does not need
it. Use a trusted local account and a fresh private state path, with no symlink/junction components.
The bridge is not an independently authenticated remote-approval service.

1. Ask the user to run from the local repository root with an available Python executable:
   `python scripts/remote_stage.py --host HOST --user USER --port PORT bridge-open`.
   Windows uses Git for Windows SSH in the user's Git Bash terminal.
   Explain host-fingerprint verification and the password prompt. Ask them to leave the terminal
   open after `KBDS SSH bridge ready` and reply `로그인완료`, then end the turn.
2. On that reply run `python scripts/remote_stage.py check` and resume the unfinished step.
   The ignored `.kbds-ssh-bridge/` holds a short-lived local token, not the password.
   After authentication the agent performs inventory, groups only material questions, incorporates
   the answers, obtains concrete plan approval, copies, verifies and writes the local report.
   Do not ask for another skill invocation or hand the user a list of toolkit commands.
   Resume again after each answer or approval while the bridge remains valid.
3. Use `--local-tool skills/kbds-data-organizer/scripts/toolkit.py`, `--local-policy <local JSON>`
   and, for planning, `--local-decisions <local JSON>`. Inputs are streamed into remote Python.
   Machine-readable plan/audit records remain only in approved output/workspace directories.
4. If disconnected, report the last confirmed state. Reconnect after user authentication;
   do not capture passwords, automate login popups or substitute ControlMaster handoff.
   If the bridge repeatedly fails, use the read-only TSV fallback below instead of endless retries.
5. After task completion or terminal failure run `python scripts/remote_stage.py bridge-close`.
   Never bypass SSH host-key checks, use sudo or invoke a generic remote shell.

`--output` reserves a new local output file before sending the SSH/bridge request. Existing
output blocks the request. Retain partial output after failure; do not delete and retry blindly.
Timeout values must be finite and positive. Cleanup removes only recognized bridge files that
still match the opened state. If unexpected/replaced files exist, preserve the state directory
for operator review and use a new private state path. Never recursively remove an uncertain path.

## TSV fallback

Ask the user to run one ordinary password-authenticated SSH command piping the local
`skills/kbds-data-organizer/scripts/inventory_tsv.py` to remote `python3 - /exact/source`,
redirecting stdout to a new ignored local TSV. This leaves no remote installed tool.
Analyze the TSV and ask material questions, then provide a concrete copy command for the
reviewed mappings and destination. Do not represent it as approved until the user approves.
