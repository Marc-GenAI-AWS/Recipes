# Progress Directory

This directory stores pipeline execution state and performance history.

## Structure

- **{use_case_name}/**: Per-use-case progress tracking
  - `iteration_{N}_results.json`: Results from each iteration
  - `pipeline_state_{id}.json`: Saved pipeline state for resumption
- **performance_reports/**: Generated performance reports
  - `{use_case_name}_report.json`: Summary reports with metrics

## State Files

### Iteration Results

Contains:
- Iteration number
- Win rate and evaluation metrics
- Prompts used
- Training and evaluation times
- Model artifact URI and endpoint name

### Pipeline State

Contains:
- Use case name
- Current iteration number
- Completed steps
- Intermediate results
- Timestamp

## Resumption

Pipeline state files enable resumption after interruption or failure. The pipeline can load a saved state and continue from the last completed step.
