"""Adapter for original historical tests: read archived baseline instead of private Git."""
from pathlib import Path
import importlib.util,subprocess,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'training/historical/judge/tests/test_formal_judge.py'
spec=importlib.util.spec_from_file_location('archived_judge_tests',p);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ReliabilityTests=mod.ReliabilityTests
class HistoricalContractTests(mod.HistoricalTests):
 @classmethod
 def setUpClass(cls):
  baseline=(ROOT/'training/historical/cs/train.py').read_bytes()
  with patch.object(mod.subprocess,'check_output',return_value=baseline):super().setUpClass()
