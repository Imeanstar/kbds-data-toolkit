"""Keep the bundled inspection profile read-only and on the approved local model."""
import json
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
        self.assertEqual(config["agent"]["kbds-review"]["mode"], "primary")
        self.assertEqual(config["agent"]["kbds-review"]["model"], config["model"])
        self.assertEqual(config["permission"]["*"], "deny")
        for tool in ("edit", "bash", "task", "webfetch", "websearch"):
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
