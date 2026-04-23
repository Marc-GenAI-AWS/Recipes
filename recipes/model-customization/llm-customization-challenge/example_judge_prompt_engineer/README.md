# Model Query and Answer Update System

This system queries your finetuned model ARNs with their corresponding questions and updates the 70B answer files with the new "finetuned" responses for comparison.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure AWS credentials:**
   Make sure your AWS credentials are configured (via AWS CLI, environment variables, or IAM role).

## File Structure

- `config.py` - Configuration file with model ARNs, file mappings, and parameters
- `run_model_queries.py` - Main script to run the queries and updates
- `query_models_and_update_answers.py` - Full-featured version with detailed logging

## Model Mappings

The system maps your model ARNs to their corresponding question and answer files:

| Model Key | Questions File | Answer File |
|-----------|----------------|-------------|
| `lilly` | `lilly_questions.txt` | `lilly_patient_edu_responses_working.json` |
| `uhg` | `uhg_questions.txt` | `uhg_patient_edu_responses_working.json` |
| `money` | `money_laundering_questions.txt` | `money_laundering_responses_working.json` |
| `gaming` | `responsible_gaming_questions.txt` | `responsible_gaming_responses.json` |

## Usage

### Process All Usecases
```bash
python run_model_queries.py
```

### Process Single Usecase
```bash
python run_model_queries.py money
python run_model_queries.py lilly
python run_model_queries.py uhg
python run_model_queries.py gaming
```

## What the Script Does

1. **Reads Questions**: Loads questions from the corresponding text files
2. **Queries Models**: Sends each question to the appropriate SageMaker endpoint
3. **Updates Answers**: Adds a new "finetuned" field to each entry in the 70B answer files
4. **Creates Backups**: Automatically backs up original answer files before updating

## Output Format

Each entry in the answer files will have the original structure plus a new `finetuned` field:

```json
{
  "dataset": "codeinstructions",
  "instruction": "Original question...",
  "output": "Original 70B response...",
  "generator": "llama3_70b_instruct",
  "finetuned": "New finetuned model response..."
}
```

## Configuration

Modify `config.py` to:
- Update model ARNs
- Change file paths
- Adjust model parameters (temperature, max_tokens, etc.)
- Enable/disable backups
- Change processing delays

## Error Handling

- Automatic backup creation before updates
- Graceful handling of missing files
- Detailed error logging
- Individual usecase processing (failures don't stop the entire process)

## AWS Requirements

- SageMaker runtime permissions
- Access to the specified endpoints in us-west-2 region
- Proper IAM roles/policies for endpoint invocation
