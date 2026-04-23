# Contributing a recipe

## What is a recipe?

A recipe is a self-contained, opinionated, working example that solves one
customer problem on AWS. It is not a framework or a library to extend — it is
something a customer clones, adapts, and runs.

A recipe should answer three questions in its README:

1. **What problem does this solve?** (one sentence)
2. **When should I use this?** (bullet list — what signals make this the right
   choice vs. alternatives)
3. **How do I run it?** (prerequisites, env vars, commands, expected output)

## Adding a new recipe

1. Copy `_template/` into the right category:
   ```bash
   cp -r _template recipes/<category>/<recipe-name>
   ```
2. Use `kebab-case` for the recipe directory name
3. Fill out the recipe's `README.md` — the template lays out the expected
   sections
4. Add a one-line row for the new recipe in the top-level [`README.md`](README.md)
   index, under the correct category table
5. Open a PR

## When to create a new top-level category

Current categories: `model-customization`, `training-infrastructure`,
`integrations`.

Default behavior: **put new recipes in the closest existing category**, even
if the fit is imperfect. The cost of a too-broad category is low; the cost of
reorganizing customer-facing URLs later is high.

Create a new top-level category only when:

- You have 2+ recipes that clearly cluster together, AND
- That cluster does not fit any existing category without stretching it, AND
- The new name would make the top-level README more scannable, not less

When you do add a category, update:
- The category tables in [`README.md`](README.md)
- This file's "Current categories" list above

## Naming

- Recipe directories: `kebab-case`, descriptive but short
  (`cross-az-fsx`, not `sagemaker-training-job-cross-az-fsx-lustre`)
- Category directories: `kebab-case`, singular noun phrase
  (`training-infrastructure`, not `training-infra` or `training_infrastructures`)

## What belongs in each recipe

- `README.md` — the three questions above, plus a results/validation section
  if you have benchmark numbers
- Source code, configs, notebooks
- Per-recipe `requirements.txt` or equivalent
- Per-recipe `LICENSE` only if it differs from the repo license

## What does not belong in a recipe

- Shared utilities pulled from another recipe (copy-paste is fine — recipes
  should stand alone)
- Internal customer names, account IDs, or non-sanitized data
- Credentials or `.env` files
