"""Copy to the completed formal Linux repo; run with its existing Python environment.

python formal_combined_39_41.py --dry-run
nohup python -u formal_combined_39_41.py > combined_39_41.log 2>&1 &

Only REWARD_STYLE_WEIGHT changes, from 0.0 to 1.0. No runtime file is replaced.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parent
STAGES = ["train", "eval_lora", "eval_lora_holdout"]
RUNS = [(39, 3407), (40, 3408), (41, 3409)]
REFERENCE = {'baseline': '8cc4accd0c687a040543a791e472e3f5b236e2e2',
 'source_hashes': {'train.py': 'edb8384bc6812850e623edba14a8ae18272e3f804458abbc0f67108775ceddcc',
                   'judge_reliability.py': '2c1940049a7965a0dd221c2e0c6d5e5dbcffa98956dbb8a9f03b291cfdb3829a',
                   'scripts/formal_judge_run.py': '4204f2bc6c3dbb362ae8787c1ff66d002c3f4e07bb07f782e7f35fe488116854',
                   'run_correctness_judge.sh': 'ae4cb457f5288c92eee507a52aa51bba77f594eb0d8cddabacfe1064dfdbba80',
                   'configs/correctness_judge_3seeds.sh': '1ef5bc357255a51350e24e2de9ac76c179c612f17daf5517008c396ba5967578',
                   'configs/correctness_judge_smoke.sh': '8003c3a71f856695a73b7ab4f51b790e75c0ee7d5325e76ce1072b39b5243e8c'},
 'recorded_backend': 'Qwen2.5-32B-Instruct-AWQ',
 'prompt': {'version': 'taxonomy_readability_maintainability_v3',
            'historical_hash': '50d083c5e7100d2e',
            'sha256': '50d083c5e7100d2e2bf5d5d94e04e18eb1222d851473b8a51b994fd1bd65c660'},
 'configuration': {'MODEL_NAME': 'unsloth/Qwen3.6-27B',
                   'MAX_SEQ_LENGTH': '2048',
                   'LOAD_IN_4BIT': '1',
                   'LOAD_IN_8BIT': '0',
                   'LOAD_IN_16BIT': '0',
                   'FULL_FINETUNING': '0',
                   'LORA_RANK': '16',
                   'LORA_ALPHA': '16',
                   'LORA_DROPOUT': '0',
                   'LORA_TARGET_MODULES': 'all-linear',
                   'USE_CHAT_TEMPLATE': '1',
                   'QWEN_ENABLE_THINKING': '0',
                   'DATASET_NAME': 'evalplus/humanevalplus',
                   'DATASET_SPLIT': 'test',
                   'SEED': '3407',
                   'NUM_GENERATIONS': '4',
                   'EVAL_NUM_GENERATIONS': '4',
                   'PER_DEVICE_TRAIN_BATCH_SIZE': '4',
                   'GRADIENT_ACCUMULATION_STEPS': '1',
                   'MAX_STEPS': '500',
                   'MAX_PROMPT_LENGTH': '1024',
                   'MAX_COMPLETION_LENGTH': '384',
                   'LEARNING_RATE': '5e-6',
                   'OPTIM': 'adamw_8bit',
                   'REPORT_TO': 'none',
                   'LOGGING_STEPS': '1',
                   'AUTO_RESUME': '0',
                   'RESUME_FROM_CHECKPOINT': 'none',
                   'SAVE_STRATEGY': 'steps',
                   'SAVE_STEPS_TRAIN': '250',
                   'SAVE_TOTAL_LIMIT': '2',
                   'TRAIN_TASK_START': '0',
                   'TRAIN_TASK_END': '50',
                   'HOLDOUT_TASK_START': '50',
                   'HOLDOUT_TASK_END': '100',
                   'CODE_RUN_TIMEOUT_SECONDS': '8',
                   'CODE_RUN_CPU_SECONDS': '8',
                   'CODE_RUN_MEMORY_MB': '0',
                   'CODE_RUN_USE_RESOURCE_LIMITS': '0',
                   'RUFF_SELECT': 'E,W',
                   'STYLE_PENALTY_BUDGET': '10.0',
                   'LIGHT_PENALTY_CODES': 'E501,W291,W293',
                   'REWARD_PROFILE': 'judge_combined',
                   'REWARD_FORMAT_WEIGHT': '0.1',
                   'REWARD_SYNTAX_WEIGHT': '0.1',
                   'REWARD_COMPILE_WEIGHT': '0.3',
                   'REWARD_TESTS_WEIGHT': '4.5',
                   'REWARD_STYLE_WEIGHT': '0.0',
                   'REWARD_AI_JUDGE_WEIGHT': '1.0',
                   'REWARD_PERFORMANCE_WEIGHT': '0.0',
                   'AI_JUDGE_ENABLED': '1',
                   'PERFORMANCE_ENABLED': '0',
                   'AI_JUDGE_REQUIRE_TEST_PASS': '1',
                   'AI_JUDGE_MOCK': '0',
                   'AI_JUDGE_TEMPERATURE': '0.0',
                   'AI_JUDGE_TOP_P': '1.0',
                   'AI_JUDGE_MAX_TOKENS': '900',
                   'AI_JUDGE_TIMEOUT_SECONDS': '60.0',
                   'AI_JUDGE_SEED': '3407',
                   'AI_JUDGE_MAX_FINDINGS': '8',
                   'AI_JUDGE_LOW_PENALTY': '0.15',
                   'AI_JUDGE_MEDIUM_PENALTY': '0.35',
                   'AI_JUDGE_HIGH_PENALTY': '0.65',
                   'AI_JUDGE_CRITICAL_PENALTY': '1.0',
                   'SAVE_BEFORE_AFTER_CSV': '1',
                   'BEFORE_AFTER_SPLIT': 'current',
                   'BEFORE_AFTER_NUM_TASKS': '10',
                   'BEFORE_AFTER_NUM_GENERATIONS': '1',
                   'BEFORE_AFTER_DO_SAMPLE': '0',
                   'BEFORE_AFTER_TEMPERATURE': '0.8',
                   'BEFORE_AFTER_TOP_P': '0.95'},
 'completed_runs': {'3407': {'run_number': 36,
                             'seed': 3407,
                             'status': 'completed',
                             'health_pass': True,
                             'metadata_sha256': '0e2ec2c51cd4f80fc366cfb428b408d4374f63e1e86b27bff9dc326e1eaa3fa5',
                             'health_sha256': '6cc9d0581d93ee762b5d130c164acdda4aafac55aaeb9a4d3b381999c7a41d67',
                             'git_commit': '6db72159491210cf81e1b7dee3940f1634525572',
                             'recorded_run_root': '<PRIVATE_PATH>'},
                    '3408': {'run_number': 37,
                             'seed': 3408,
                             'status': 'completed',
                             'health_pass': True,
                             'metadata_sha256': 'ee8e897694ea55550213dba184a76ac38b30924f219e69c671bcec7137f85a40',
                             'health_sha256': 'a5869e63eef63b15c708605b98ba0cb748cf9ba36ff88b472133dd8ac4b91323',
                             'git_commit': '6db72159491210cf81e1b7dee3940f1634525572',
                             'recorded_run_root': '<PRIVATE_PATH>'},
                    '3409': {'run_number': 38,
                             'seed': 3409,
                             'status': 'completed',
                             'health_pass': True,
                             'metadata_sha256': '73188b4914dda78b9435bfeb796a3c2a1d22dd33882c8e8980e21b889abbe8fc',
                             'health_sha256': '878a4978865ad2673fb12cf91b20d69b220c14de10ff2e61d019a1ce73c255e7',
                             'git_commit': '6db72159491210cf81e1b7dee3940f1634525572',
                             'recorded_run_root': '<PRIVATE_PATH>'}},
 'path_keys': ['RUN_ROOT',
               'RUN_NAME',
               'LOG_DIR',
               'OUTPUT_DIR',
               'LORA_OUTPUT_DIR',
               'LORA_PATH',
               'AI_JUDGE_STATUS_PATH'],
 'stage_extras': {'train': {'TEST_MODE': 'train',
                            'RUN_ID': 'train',
                            'REPEAT_INDEX': '1',
                            'REPEAT_TOTAL': '1'},
                  'eval_lora': {'TEST_MODE': 'eval_lora',
                                'RUN_ID': 'eval_lora',
                                'REPEAT_INDEX': '1',
                                'REPEAT_TOTAL': '1'},
                  'eval_lora_holdout': {'TEST_MODE': 'eval_lora_holdout',
                                        'RUN_ID': 'eval_lora_holdout',
                                        'REPEAT_INDEX': '1',
                                        'REPEAT_TOTAL': '1'}}}


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def load_formal():
    require((ROOT / "scripts/formal_judge_run.py").is_file(),
            "Copy this file to the existing completed formal repo root.")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    import formal_judge_run
    return formal_judge_run


def verify_frozen(formal, original_config):
    require(formal.source_hashes() == REFERENCE["source_hashes"],
            "STOP: runtime source hashes differ from completed Runs 36-38.")
    require(formal.BASELINE == REFERENCE["baseline"], "STOP: baseline differs.")
    require(formal.BACKEND == REFERENCE["recorded_backend"], "STOP: backend differs.")
    prompt = {k: v for k, v in formal.prompt_metadata().items() if k != "text"}
    require(prompt == REFERENCE["prompt"], "STOP: historical judge prompt differs.")
    for _, seed in RUNS:
        expected = {**REFERENCE["configuration"], "SEED": str(seed)}
        actual = original_config(False, seed)
        differences = sorted(k for k in set(actual) | set(expected)
                             if actual.get(k) != expected.get(k))
        require(not differences, "STOP: original configuration differs: " + ", ".join(differences))
        for stage in STAGES:
            settings = formal.stage_config(actual, ROOT / "results/audit-only", stage)
            stable = {k: v for k, v in settings.items() if k not in REFERENCE["path_keys"]}
            require(stable == {**expected, **REFERENCE["stage_extras"][stage]},
                    "STOP: effective stage settings differ: " + stage)


def combined_config(original_config, smoke=False, seed=3407):
    require(not smoke, "Smoke is excluded from this formal queue.")
    values = original_config(False, seed)
    values["REWARD_STYLE_WEIGHT"] = "1.0"
    return values


def verify_outputs(formal, root):
    require(formal.health(root, save=False)["pass"], "STOP: preceding formal health FAIL.")
    counts = {}
    for stage, filename, expected in (
        ("train", "samples.csv", 2000),
        ("eval_lora", "eval_lora_train_tasks.csv", 200),
        ("eval_lora_holdout", "eval_lora_holdout_tasks.csv", 200),
    ):
        with (root / "logs" / stage / filename).open(encoding="utf-8", newline="") as stream:
            count = sum(1 for _ in csv.DictReader(stream))
        require(count == expected, "STOP: incomplete output: " + stage)
        counts[filename] = count
    formal.write_json(root / "output-counts.json", counts)


def execute(formal, dry_run=False):
    original_config = formal.config
    verify_frozen(formal, original_config)
    formal.STAGES = STAGES.copy()
    formal.config = lambda smoke=False, seed=3407: combined_config(original_config, smoke, seed)
    original_write = formal.write_json
    current = {}
    entry_source = Path(__file__).read_bytes()
    entry_hash = hashlib.sha256(entry_source).hexdigest()

    def write_with_identity(path, value):
        path = Path(path)
        if path.name == "metadata.json" and value.get("mode") == "formal":
            current["root"] = path.parent
            value.update(run_number=current["run"], condition="correctness + style + AI judge")
            value["matched_reference"] = REFERENCE["completed_runs"][str(value["seed"])]
            value["intended_experimental_differences"] = {
                "REWARD_STYLE_WEIGHT": {"from": "0.0", "to": "1.0"}}
            value["orchestration"] = {
                "stage_order": STAGES.copy(), "fresh_training_adapter": True,
                "adapter_reused": False, "pretraining_base_evaluations_skipped": True,
                "configuration_override": {"REWARD_STYLE_WEIGHT": "1.0"},
                "note": "Frozen config source stays unchanged; effective settings above include the override.",
                "launcher_sha256": entry_hash,
            }
            snapshot = path.parent / "source" / Path(__file__).name
            if snapshot.exists():
                require(snapshot.read_bytes() == entry_source, "STOP: launcher snapshot changed.")
            else:
                snapshot.write_bytes(entry_source)
        return original_write(path, value)

    def approval_gate(after, mode, seed):
        verify_frozen(formal, original_config)
        require(mode == "formal", "STOP: formal mode required.")
        if seed == 3407:
            require(after == "completed-runs-36-38", "STOP: reference gate differs.")
            return
        root = Path(after).resolve()
        meta = json.loads((root / "metadata.json").read_text())
        require(meta.get("run_number") == current["run"] - 1 and meta["seed"] == seed - 1,
                "STOP: preceding combined run identity differs.")
        require(meta["configuration"] == combined_config(original_config, seed=seed - 1),
                "STOP: preceding combined configuration differs.")
        require(meta["source_hashes"] == REFERENCE["source_hashes"],
                "STOP: preceding runtime sources differ.")
        require(meta["orchestration"]["launcher_sha256"] == entry_hash,
                "STOP: preceding launcher differs.")
        verify_outputs(formal, root)

    formal.write_json = write_with_identity
    formal.approval_gate = approval_gate
    after = "completed-runs-36-38"
    print("CONFIG_AUDIT=PASS; sole experimental difference: REWARD_STYLE_WEIGHT 0.0 -> 1.0", flush=True)
    for run, seed in RUNS:
        current.clear()
        current["run"] = run
        print(f"RUN={run} SEED={seed} STAGES=train_500,eval_lora,eval_lora_holdout", flush=True)
        result = formal.run(SimpleNamespace(smoke=False, seed=seed, after=after, dry_run=dry_run))
        require(result == 0, f"STOP: Run {run} failed; later seeds will not start.")
        if not dry_run:
            root = current["root"]
            verify_outputs(formal, root)
            verify_frozen(formal, original_config)
            after = str(root)
            print(f"RUN_{run}_HEALTH=PASS DIRECTORY={root}", flush=True)
    print("DRY_RUN=PASS" if dry_run else "COMBINED_RUNS_39_41=PASS", flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Source/config checks only; no network/GPU/writes")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        return execute(load_formal(), args.dry_run)
    except AuditError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"COMBINED_QUEUE=FAIL ({type(exc).__name__}); inspect run artifacts. Later seeds stopped.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
