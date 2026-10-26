"""SSH wrapper safety tests; no real SSH connection or research files."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("remote_stage_safety", Path(__file__).resolve().parents[1] / "scripts/remote_stage.py")
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)


class BridgeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_bridge(self):
        root = self.root / "bridge"
        root.mkdir()
        (root / "requests").mkdir()
        (root / "responses").mkdir()
        (root / "state.json").write_text("{}")
        info = root.stat()
        return root, (info.st_dev, info.st_ino)

    def test_cleanup_only_removes_owned_bridge_files(self):
        root, identity = self.make_bridge()
        (root / "requests" / ("a" * 32 + ".request.json")).write_text("{}")
        remote.cleanup_state(root, identity)
        self.assertFalse(root.exists())

    def test_unexpected_file_preserves_all_bridge_contents(self):
        root, identity = self.make_bridge()
        important = root / "responses" / "unrelated.txt"
        important.write_text("preserve")
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            remote.cleanup_state(root, identity)
        self.assertEqual(important.read_text(), "preserve")
        self.assertTrue((root / "state.json").exists())

    def test_replaced_directory_identity_blocks_cleanup(self):
        root, identity = self.make_bridge()
        with self.assertRaisesRegex(ValueError, "changed"):
            remote.cleanup_state(root, (identity[0], identity[1] + 1))
        self.assertTrue((root / "state.json").exists())

    def test_redirected_queue_blocks_before_any_cleanup(self):
        root, identity = self.make_bridge()
        queue = root / "requests"
        target = queue / ("a" * 32 + ".request.json")
        target.write_text("preserve")
        original = remote.redirected
        with patch.object(remote, "redirected", side_effect=lambda p: p == queue or original(p)):
            with self.assertRaisesRegex(ValueError, "Linked"):
                remote.cleanup_state(root, identity)
        self.assertEqual(target.read_text(), "preserve")
        self.assertTrue((root / "state.json").exists())

    def test_windows_junction_reparse_attribute_is_rejected(self):
        from types import SimpleNamespace
        with patch.object(Path, "lstat", return_value=SimpleNamespace(st_mode=remote.stat.S_IFDIR,
                                                                      st_file_attributes=0x400)):
            self.assertTrue(remote.redirected(self.root))

    def test_symlinked_state_parent_rejected_before_resolution(self):
        target = self.root / "target"
        target.mkdir()
        link = self.root / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("Creating symlinks requires platform permissions")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            remote.state_root(link / "new-bridge")

    def test_direct_output_is_saved_without_newline_translation(self):
        output = self.root / "result.txt"
        content = "검증\nsecond line\n".encode("utf-8")
        def fake_call(command, stdout):
            self.assertEqual(command[-1], "printf 'KBDS_BRIDGE_OK\\n'")
            stdout.write(content)
            return 0
        with patch.object(remote.subprocess, "call", side_effect=fake_call):
            status = remote.main(["--host", "example.invalid", "--bridge-state", str(self.root / "absent"),
                                  "--output", str(output), "check"])
        self.assertEqual(status, 0)
        self.assertEqual(output.read_bytes(), content)

    def test_existing_output_blocks_before_ssh(self):
        output = self.root / "existing.txt"
        output.write_text("keep")
        with patch.object(remote.subprocess, "call") as call:
            status = remote.main(["--host", "example.invalid", "--bridge-state", str(self.root / "absent"),
                                  "--output", str(output), "check"])
        self.assertEqual(status, 2)
        call.assert_not_called()
        self.assertEqual(output.read_text(), "keep")

    def test_existing_bridge_output_blocks_before_request(self):
        output = self.root / "existing.txt"
        output.write_text("keep")
        with patch.object(remote, "submit_request") as submit:
            with self.assertRaises(FileExistsError):
                remote.submit(self.root, "run", "printf test", output=output)
        submit.assert_not_called()
        self.assertEqual(output.read_text(), "keep")

    def test_nonfinite_timeout_blocks_before_request(self):
        with patch.object(remote.subprocess, "call") as call:
            for value in ("nan", "inf", "0", "-1"):
                self.assertEqual(remote.main(["--host", "example.invalid", "--bridge-timeout", value, "check"]), 2)
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
