# Event Files Directory

This directory stores pipeline artifacts and intermediate results, matching the structure of the existing manual pipeline.

## Structure

- **questions/**: Test questions for each use case (JSON format)
- **usecases/**: Use case descriptions (text format)
- **judge_prompts/**: Judge prompts for evaluation (text format)
- **training_data/**: Generated training data in JSONL format

## File Naming Conventions

- Questions: `{use_case_name}_questions.json`
- Use cases: `{use_case_name}_description.txt`
- Judge prompts: `{use_case_name}_judge_prompt.txt`
- Training data: `{use_case_name}_iter{N}_{timestamp}.jsonl`

## Data Formats

### Training Data (JSONL)

Each line is a JSON object with:
```json
{"instruction": "...", "context": "...", "response": "..."}
```

### Questions (JSON)

Array of question strings:
```json
["Question 1?", "Question 2?", ...]
```
