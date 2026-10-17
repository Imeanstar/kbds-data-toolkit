"""Keep the bundled inspection profile read-only and on the approved local model."""
import json
from fnmatch import fnmatchcase
import unittest
from pathlib import Path


class OpenCodeProfileTest(unittest.TestCase):
    def test_local_read_only_default(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "opencode.json").read_text())
        self.assertEqual(config["enabled_providers"], ["qwen-local"])
        self.assertEqual(config["model"], "qwen-local/qwen3.8-27b")
        self.assertEqual(config["small_model"], config["model"])
        self.assertEqual(config["default_agent"], "kbds-review")
        self.assertEqual(config["skills"]["paths"], ["./skills"])
        self.assertTrue((root / "skills/kbds-data-organizer/SKILL.md").is_file())
        self.assertEqual(config["agent"]["kbds-review"]["mode"], "primary")
        self.assertEqual(config["agent"]["kbds-review"]["model"], config["model"])
        self.assertEqual(config["permission"]["*"], "deny")
        for tool in ("edit", "bash", "grep", "task", "webfetch", "websearch"):
            self.assertEqual(config["permission"].get(tool, "deny"), "deny")
        self.assertEqual(config["permission"]["external_directory"], "ask")
        self.assertEqual(config["permission"]["skill"]["kbds-data-organizer"], "allow")
        self.assertEqual(config["permission"]["skill"]["*"], "deny")
        self.assertNotIn("permission", config["agent"]["kbds-review"])
        self.assertFalse(config["snapshot"])
        self.assertEqual(config["share"], "disabled")
        self.assertEqual(config["subagent_depth"], 0)
        self.assertEqual(config["provider"]["qwen-local"]["options"]["baseURL"],
                         "http://127.0.0.1:8080/v1")
        self.assertEqual(config["compaction"], {"auto": True, "prune": True, "reserved": 4096,
                                              "tail_turns": 1, "preserve_recent_tokens": 2048})
        model = config["provider"]["qwen-local"]["models"]["qwen3.8-27b"]
        self.assertEqual(model["limit"], {"context": 16384, "input": 16384, "output": 2048})
        self.assertGreaterEqual(config["compaction"]["reserved"], model["limit"]["output"])
        compact_name = config["agent"]["compaction"]["model"]
        self.assertEqual(compact_name, "qwen-local/qwen3.8-27b-compact")
        compact = config["provider"]["qwen-local"]["models"][compact_name.split("/", 1)[1]]
        self.assertEqual(compact["id"], "qwen3.8-27b")
        self.assertEqual(compact["options"], model["options"])
        self.assertEqual(compact["limit"], {"context": 16384, "input": 16384, "output": 1024})
        self.assertEqual(model["options"]["chat_template_kwargs"],
                         {"enable_thinking": False, "preserve_thinking": False})

    def test_staging_requires_permission_without_source_or_code_edits(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "opencode.json").read_text())
        stage = config["agent"]["kbds-stage"]
        self.assertEqual(stage["mode"], "primary")
        self.assertEqual(stage["model"], config["model"])

        def action(tool, value):
            result = config["permission"]["*"]
            for pattern, permission in stage["permission"][tool].items():
                if fnmatchcase(value, pattern):
                    result = permission
            return result

        for command in (
            "python3 scripts/kbds.py self-check",
            "python3 scripts/kbds.py --policy /approved/policy.local.json inventory",
            "python3 scripts/kbds.py --policy /approved/policy.local.json inventory --summary",
            "python3 scripts/kbds.py --policy /approved/policy.local.json plan --name reviewed-001 --decisions /approved/decisions.local.json",
            "python3 scripts/kbds.py --policy /approved/policy.local.json apply --plan /approved/work/reviewed-001/plan.json --approve-plan PLAN_HASH",
            "python3 scripts/kbds.py --policy /approved/policy.local.json verify --plan /approved/work/reviewed-001/plan.json",
            "python3 scripts/kbds.py report --plan /approved/work/reviewed-001/plan.json",
            "python3 scripts/kbds.py run --scope /approved/scope.local.json --inspect",
            "python3 scripts/kbds.py run --scope /approved/scope.local.json --approve-scope SCOPE_HASH --name job-001",
        ):
            self.assertEqual(action("bash", command), "ask")
        for command in ("rm -rf /data", "cp -r /source /destination", "python3 -c 'print(1)'",
                        "git restore .", "sudo chmod 777 /data", "curl https://example.com",
                        "python3 skills/kbds-data-organizer/scripts/toolkit.py --policy /approved/policy.local.json inventory"):
            self.assertEqual(action("bash", command), "deny")
        for file in ("config/policy.local.json", "config/decisions.local.json"):
            self.assertEqual(action("edit", file), "ask")
        for file in ("opencode.json", "AGENTS.md", "scripts/kbds.py", "config/scope.local.json", "source/sample_R1.fastq.gz",
                     "../source/sample_R1.fastq.gz", "skills/kbds-data-organizer/scripts/toolkit.py"):
            self.assertEqual(action("edit", file), "deny")
        self.assertEqual(set(stage["permission"]["edit"]),
                         {"*", "config/policy.local.json", "config/decisions.local.json"})
