"""CPU-only regression tests; do not import train.py's GPU/model setup.

Run: python -m unittest -v test_script_execution.py
"""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


class ScriptExecutionTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).with_name("train.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        helper = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == "run_python_script")
        self.scope = dict(os=os, sys=sys, subprocess=subprocess, tempfile=tempfile,
                          resource=None, USE_RESOURCE_LIMITS=False, RUN_TIMEOUT_SECONDS=2)
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "train.py", "exec"), self.scope)
        self.run_script = self.scope["run_python_script"]

    def test_large_humaneval_sized_script(self):
        result = self.run_script("#" + "x" * 300_000 + "\nassert 2 + 2 == 4\nprint('passed')")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "passed")

    def test_unicode_source_and_main(self):
        result = self.run_script("assert __name__ == '__main__'\nassert len('你好') == 2\nprint('ok')")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_failure_and_stderr_preserved(self):
        result = self.run_script("raise AssertionError('expected failure')")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AssertionError: expected failure", result.stderr)

    def test_syntax_error_preserved(self):
        result = self.run_script("def broken(:\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SyntaxError", result.stderr)

    def test_timeout_override(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_script("import time\ntime.sleep(10)", timeout_seconds=0.1)

    def test_temporary_directory_cleaned(self):
        result = self.run_script("import os\nprint(os.getcwd())")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(Path(result.stdout.strip()).exists())

    def test_resource_hook_timeout_and_cleanup_on_error(self):
        marker = lambda: None
        self.scope.update(resource=object(), USE_RESOURCE_LIMITS=True,
                          set_subprocess_limits=marker)
        captured = {}
        def fail(args, **kwargs):
            captured.update(kwargs)
            self.assertIs(kwargs["preexec_fn"], marker)
            self.assertEqual(kwargs["timeout"], 2)
            self.assertEqual(args[0], sys.executable)
            self.assertEqual(Path(args[1]).read_text(encoding="utf-8"), "print(1)")
            raise OSError("simulated launch failure")
        with patch.object(subprocess, "run", side_effect=fail):
            with self.assertRaisesRegex(OSError, "simulated launch failure"):
                self.run_script("print(1)")
        self.assertFalse(Path(captured["cwd"]).exists())


if __name__ == "__main__":
    unittest.main()
