"""Use the archived HumanEval+ long-script regression suite unchanged."""
import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'training/historical/cs/test_script_execution.py'
spec=importlib.util.spec_from_file_location('archived_execution_tests',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ScriptExecutionTests=m.ScriptExecutionTests
