"""Safety guards for the agent-only source snapshot (no application runtime)."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("agent_graph_build", Path(__file__).with_name("build_graph.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SnapshotGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.source = self.repo / "module.py"
        self.source.write_text("def example(): return 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "module.py"], cwd=self.repo, check=True)
        # HEAD is queried without creating commits in the user's repository.
        subprocess.run(["git", "-c", "user.name=Agent test", "-c", "user.email=agent@example.invalid", "commit", "-qm", "fixture"], cwd=self.repo, check=True)
        self.out = self.base / "knowledge"

    def test_untracked_and_generated_files_are_not_copied(self):
        (self.repo / "private.py").write_text("PRIVATE", encoding="utf-8")
        result = module.snapshot(self.repo, self.out)
        self.assertEqual(set(result["files"]), {"module.py"})
        self.assertFalse((self.out / "source/private.py").exists())
        self.assertFalse(module.source_allowed("secrets/credentials.json", {".json"}))
        self.assertFalse(module.source_allowed("artifacts/proof.py", {".py"}))
        self.assertFalse(module.source_allowed("web/static/react/generated.js", {".js"}))

    def test_snapshot_inside_application_is_refused(self):
        with self.assertRaises(ValueError):
            module.snapshot(self.repo, self.repo / "source-copy")
        self.assertFalse((self.repo / "source-copy").exists())

    def test_unowned_output_is_preserved(self):
        self.out.mkdir()
        sentinel = self.out / "keep.txt"
        sentinel.write_text("KEEP", encoding="utf-8")
        with self.assertRaises(ValueError):
            module.snapshot(self.repo, self.out)
        self.assertEqual(sentinel.read_text(), "KEEP")

    def test_incremental_copy_keeps_unchanged_files_and_removes_only_owned_source(self):
        module.snapshot(self.repo, self.out)
        target = self.out / "source/module.py"
        before = target.stat().st_mtime_ns
        self.assertEqual(module.snapshot(self.repo, self.out)["changed"], 0)
        self.assertEqual(target.stat().st_mtime_ns, before)
        keep = self.out / "source/keep.txt"
        keep.write_text("KEEP", encoding="utf-8")
        subprocess.run(["git", "rm", "--cached", "-q", "module.py"], cwd=self.repo, check=True)
        module.snapshot(self.repo, self.out)
        self.assertFalse(target.exists())
        self.assertTrue(self.source.exists())
        self.assertEqual(keep.read_text(), "KEEP")

    def test_manifest_traversal_is_refused(self):
        module.snapshot(self.repo, self.out)
        manifest = self.out / "source-manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["files"]["../../sentinel.py"] = {"sha256": "invalid", "bytes": 4}
        manifest.write_text(json.dumps(data), encoding="utf-8")
        sentinel = self.base / "sentinel.py"
        sentinel.write_text("KEEP", encoding="utf-8")
        with self.assertRaises(ValueError):
            module.snapshot(self.repo, self.out)
        self.assertEqual(sentinel.read_text(), "KEEP")


if __name__ == "__main__":
    unittest.main()
