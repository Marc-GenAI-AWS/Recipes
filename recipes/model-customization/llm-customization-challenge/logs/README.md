# Logs Directory

This directory contains application logs for the automated LLM finetuning pipeline.

## Log Files

Logs are named: `{use_case_name}_{timestamp}.log`

## Log Format

Logs use structured logging with the following fields:
- Timestamp
- Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Component name
- Message
- Additional context (error details, operation parameters, etc.)

## Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages about pipeline progress
- **WARNING**: Warning messages for non-critical issues
- **ERROR**: Error messages for failures that don't stop the pipeline
- **CRITICAL**: Critical errors that stop pipeline execution

## Retention

Log files should be retained according to your organization's retention policy. Consider implementing log rotation for long-running deployments.
