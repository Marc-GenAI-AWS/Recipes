# Marc-GenAI-AWS-Recipes

Sanitized, customer-ready recipes for building GenAI and ML workloads on AWS —
primarily SageMaker AI, with integrations into NVIDIA BioNeMo, on-prem Slurm,
and FSx for Lustre.

Each recipe is a self-contained, opinionated example that solves one specific
customer problem end-to-end. Clone a recipe, read its README, run it.

## Index

### `recipes/model-customization/`

Fine-tuning, evaluation, and data generation for customizing LLMs.

| Recipe | Use this when |
|---|---|
| [`finetune-automation/`](recipes/model-customization/finetune-automation/) | You want an end-to-end SageMaker fine-tuning workflow — synthetic data generation, S3 upload, training job, deployment, inference testing — driven from a Streamlit dashboard. |
| [`llm-customization-challenge/`](recipes/model-customization/llm-customization-challenge/) | You're building use cases for the AWS AI Model Customization Challenge and need scaffolding for data gen, prompt-engineered judges, and evaluation. |

### `recipes/training-infrastructure/`

Training-plane infrastructure patterns: storage, cross-AZ, hybrid cloud/on-prem.

| Recipe | Use this when |
|---|---|
| [`cross-az-fsx/`](recipes/training-infrastructure/cross-az-fsx/) | Your P5/P4de GPU capacity lives in a different AZ than your FSx Lustre data. Validated with BioNeMo Evo2 (1B/7B/40B) at no measurable throughput cost. |
| [`smus-to-slurm-on-prem/`](recipes/training-infrastructure/smus-to-slurm-on-prem/) | You want SageMaker Unified Studio as the consolidation plane (JupyterLab, MLflow, catalog) but training must run on on-prem GPUs — data stays local, only metadata crosses. |

### `recipes/integrations/`

Recipes for running third-party frameworks and images on AWS.

| Recipe | Use this when |
|---|---|
| [`nvidia-bionemo-evo2/`](recipes/integrations/nvidia-bionemo-evo2/) | You need to load the NVIDIA BioNeMo image into a SageMaker AI Notebook for interactive work, or launch BioNeMo training as a SageMaker Training Job. |

### `recipes/studio-demos/`

End-to-end SageMaker Unified Studio demos — populated catalogs, governance, and
workflows you can show a customer.

| Recipe | Use this when |
|---|---|
| [`smus-catalog-hydration/`](recipes/studio-demos/smus-catalog-hydration/) | You need a SageMaker Unified Studio project pre-loaded with realistic catalog content — a retail dataset, Glue tables, a business glossary with term hierarchy, asset descriptions and governance tags, OpenLineage lineage, a published data product, and a deployable training-job model — to demo the catalog. |

## How to use a recipe

1. Pick a recipe from the index above
2. Read its README — it includes prerequisites, env vars, and run instructions
3. Each recipe stands alone; you do not need to clone the whole repo to use one

```bash
# sparse-checkout a single recipe
git clone --filter=blob:none --sparse https://github.com/Marc-GenAI-AWS/Marc-GenAI-AWS-Recipes.git
cd Marc-GenAI-AWS-Recipes
git sparse-checkout set recipes/model-customization/finetune-automation
```

## Contributing a new recipe

See [CONTRIBUTING.md](CONTRIBUTING.md). Start from [`_template/`](_template/).

## History

This repo consolidates five previously separate GitHub repos. Full commit
history was preserved via `git-filter-repo` during the migration. Original
repos are archived (read-only) — their issues and URLs still resolve.
