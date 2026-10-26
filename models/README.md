# Gimmich models

AI models that look at a screenshot and decide what to click or type. The
list is `models.toml`: what each model is good at, which systems it's for,
and the exact version Gimmich tested.

| Command | What it does |
|---|---|
| `python3 scripts/get-model.py list` | every model and what it's for |
| `python3 scripts/get-model.py pick android` | the model the orchestrator uses for Android |
| `python3 scripts/get-model.py get qwen3-vl-4b` | download one compressed model (~3 GB) |
| `python3 scripts/get-model.py get all` | all 7 compressed models (~36 GB) |
| `python3 scripts/get-model.py get all --full` | all 10 original models (~250 GB, for GPUs and training) |
| `python3 scripts/get-model.py check` | is a newer version out? |
| `scripts/ask-model.sh android shot.png "What should I tap?"` | show a screenshot to a model and get its answer |

Downloads come straight from Hugging Face and resume if they stop. The
models are far too big for GitHub, so they are never stored in this repo:
keep them on your own computer, or in a Google Cloud Storage bucket.

The **Models** workflow checks every Monday for newer versions and tests that
each compressed model can read a test screen.

Licenses differ: most are Apache-2.0 or MIT; Qwen2.5-VL 3B and CogAgent have
their own licenses, so read those before using them in a product.
