# Third-party notices and license scope

The root [MIT license](LICENSE) applies to original project code and original supporting documentation by Jacky Zhang and Conrad Ang. Both authors' agreement to inclusion of their project code and saved research records, and to that license choice, was confirmed by the user on 17 October 2026. This records the reported agreement; no signed consent document is asserted.

Third-party material retains its own terms. The MIT grant does not relicense benchmark prompts/tests, generated model outputs or recorded study data. Their inclusion does not grant a separate blanket data or output license. The two author-reviewers have approved inclusion of the minimised study records; pseudonymisation alone would not establish permission or guarantee anonymity. The individual report, manuscript sources, university logo, model/adapter weights and raw named reviewer export are excluded.

## HumanEval and EvalPlus

Recorded CSVs and human-review output catalogs contain benchmark prompts, test/solution fragments and generated completions. OpenAI HumanEval is MIT licensed; its copyright and permission notice is retained in [licenses/HumanEval-MIT.txt](licenses/HumanEval-MIT.txt), from the [official HumanEval license](https://github.com/openai/human-eval/blob/master/LICENSE).

EvalPlus is Apache 2.0 licensed, with an additional HumanEval MIT note for `evalplus/eval/`. The complete notice is retained in [licenses/EvalPlus-Apache-2.0.txt](licenses/EvalPlus-Apache-2.0.txt), from the [official EvalPlus license](https://github.com/evalplus/evalplus/blob/master/LICENSE). The [HumanEval+ dataset card](https://huggingface.co/datasets/evalplus/humanevalplus/blob/main/README.md) declares Apache 2.0. Benchmark-derived content remains subject to those notices; citation alone does not replace them. Immutable historical dataset revisions were not recovered.

## CodeQual analyzer

The [CodeQual pilot](exploratory/codequal_analyzer_pilot/) uses [MaximeRobeyns/codequal_analyzer](https://github.com/MaximeRobeyns/codequal_analyzer) at commit `518360297f59ad7b6569233eb4b934e6b00c083b`. The exact MIT notice from that commit is retained in [licenses/CodeQual-MIT.txt](licenses/CodeQual-MIT.txt): copyright (c) 2025 Maxime Robeyns.

In particular, [patches/windows-compat.patch](exploratory/codequal_analyzer_pilot/patches/windows-compat.patch) includes context from upstream `python/pycq_analyzer/api.py` and `utils.py`, alongside this project's compatibility changes. The upstream notice applies to that retained upstream material. The pilot adapter imports the external analyzer; the complete analyzer package is not vendored here. Project wrappers and the separate CodeQual-inspired AST detector are retained as project research code, without claiming ownership of the upstream implementation.

## Models and installed dependencies

Formal records name [Unsloth Qwen3.6-27B](https://huggingface.co/unsloth/Qwen3.6-27B); Judge configuration names [Qwen2.5-32B-Instruct-AWQ](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct-AWQ). Their model cards declare Apache 2.0. Earlier exploratory records also contain outputs from [CodeLlama-7b-Python](https://huggingface.co/codellama/CodeLlama-7b-Python-hf), whose [Llama 2 Community License](https://huggingface.co/codellama/CodeLlama-7b-Python-hf/blob/main/LICENSE), section 1(b)(v), prohibits using its outputs or results to improve other large language models, except Llama 2 or its derivative works. The license does not expressly prohibit publication of saved research outputs; it must not be read as an unrestricted downstream-training grant. These are recorded model-family identifiers, not recovered immutable historical weight revisions.

Only saved outputs and metadata are included; model/adapter weights are absent. The project MIT license grants no rights to model weights and does not assert unrestricted reuse of every generated output. Consult the relevant model terms for any further use.

Unsloth, PyTorch, Hugging Face libraries, Transformers, TRL, PEFT, Ruff, other analyzers and SonarQube are referenced dependencies, not bundled installations or binaries. Installing or redistributing them requires their own applicable terms. [manifests/files.csv](manifests/files.csv) records source identity and transformations for included research files; it is provenance, not an additional license grant.
