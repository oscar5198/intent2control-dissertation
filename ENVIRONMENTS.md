# Reproducibility Environments

This repository contains a static HTML/CSS/JavaScript listening-study frontend,
Python statistical analysis, and Python LLM experiment tooling.

## Statistical Analysis

Use `requirements-statistical.txt` for the final Bayesian mixed-effects models,
held-out mixed-effects evaluation, and acoustic-feature verification notebooks.
The file is a reproducibility specification, not a byte-identical lockfile. The
expensive model-fitting entry points use Bambi/PyMC and should not be run during
routine checks.

## LLM Experiments

Use `requirements-llm.txt` for prompt rendering, prediction consolidation,
evaluation, and production runner code. The file is a reproducibility
specification, not a byte-identical lockfile. Final retained predictions and
scoring can be inspected locally without calling APIs.

## External Model Access

The production runners require external model access:

- GPT-5.5: OpenAI-compatible provider API credentials in the QMUL runtime.
- Claude Sonnet 5: Anthropic-compatible provider API credentials in the QMUL
  runtime.
- Llama 3.1 70B Instruct: QMUL GPU/Hugging Face Transformers environment with
  the frozen model identity in `llm-experiments/outputs/final/inference-config/`.
- Centaur: RunPod environment with the retained Centaur adapter/base-model
  identity in `llm-experiments/outputs/final/inference-config/model_registry.json`.

Do not store credentials or secrets in this repository.

## Frontend

The final study interface under `study-interface/frontend-5mix/` is static and
does not require a Node build step. It can be served as ordinary static files by
Netlify or any static web server.
