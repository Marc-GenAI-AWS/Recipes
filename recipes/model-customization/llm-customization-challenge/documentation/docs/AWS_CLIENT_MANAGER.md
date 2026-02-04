# AWS Client Manager Documentation

## Overview

The AWS Client Manager provides centralized management of boto3 clients for AWS services used in the automated LLM finetuning pipeline. It handles client initialization, retry logic with exponential backoff, error handling, and supports both real AWS clients and mock clients for testing.

## Features

- **Centralized Client Management**: Single point of initialization for all AWS service clients
- **Automatic Retry Logic**: Exponential backoff with jitter for transient errors
- **Error Classification**: Distinguishes between transient and non-transient errors
- **Mock Client Support**: Easy integration with testing frameworks
- **Comprehensive Logging**: Detailed logging of all operations and errors
- **Credential Validation**: Built-in credential validation
- **Resource Cleanup**: Proper cleanup of all clients

## Supported AWS Services

- **SageMaker**: Model training and management
- **SageMaker Runtime**: Model inference
- **Bedrock Runtime**: Claude Sonnet 4 for data generation and judging
- **S3**: Storage for training data, model artifacts, and results

## Installation

The AWS Client Manager is part of the automated LLM finetuning pipeline. Ensure you have the required dependencies:

```bash
pip install boto3>=1.28.0
```

## Basic Usage

### Initialize the Manager

```python
from src.aws_client_manager import AWSClientManager

# Initialize with default configuration
manager = AWSClientManager()

# Get clients
sagemaker = manager.get_sagemaker_client()
bedrock = manager.get_bedrock_runtime_client()
s3 = manager.get_s3_client()
```

### Custom Configuration

```python
config = {
    "region": "us-west-2",
    "retry": {
        "max_attempts": 5,
        "initial_backoff_seconds": 1.0,
        "max_backoff_seconds": 30.0,
        "jitter_factor": 0.1,
    },
    "connect_timeout": 30,
    "read_timeout": 30,
}

manager = AWSClientManager(config)
```

### Using Retry Logic

The manager provides automatic retry logic for transient errors:

```python
# Automatic retry on transient errors
response = manager.invoke_with_retry(
    sagemaker.describe_training_job,
    TrainingJobName='my-job'
)
```

## Configuration Options

### AWS Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `region` | str | `"us-east-1"` | AWS region for all services |
| `aws_access_key_id` | str | None | AWS access key (optional, uses default credentials) |
| `aws_secret_access_key` | str | None | AWS secret key (optional) |
| `aws_session_token` | str | None | AWS session token (optional) |
| `connect_timeout` | int | 60 | Connection timeout in seconds |
| `read_timeout` | int | 60 | Read timeout in seconds |

### Retry Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_attempts` | int | 3 | Maximum number of retry attempts |
| `initial_backoff_seconds` | float | 2.0 | Initial backoff delay in seconds |
| `max_backoff_seconds` | float | 60.0 | Maximum backoff delay in seconds |
| `jitter_factor` | float | 0.1 | Jitter factor for randomization (0.0 to 1.0) |

## API Reference

### AWSClientManager

#### `__init__(config=None, mock_clients=None)`

Initialize the AWS Client Manager.

**Parameters:**
- `config` (dict, optional): Configuration dictionary with AWS settings
- `mock_clients` (dict, optional): Dictionary of mock clients for testing

**Example:**
```python
manager = AWSClientManager({
    "region": "us-east-1",
    "retry": {"max_attempts": 5}
})
```

#### `get_sagemaker_client()`

Get or create SageMaker client.

**Returns:** Boto3 SageMaker client

**Example:**
```python
sagemaker = manager.get_sagemaker_client()
response = sagemaker.list_training_jobs(MaxResults=10)
```

#### `get_sagemaker_runtime_client()`

Get or create SageMaker Runtime client.

**Returns:** Boto3 SageMaker Runtime client

**Example:**
```python
runtime = manager.get_sagemaker_runtime_client()
response = runtime.invoke_endpoint(
    EndpointName='my-endpoint',
    Body=json.dumps({"inputs": "test"})
)
```

#### `get_bedrock_runtime_client()`

Get or create Bedrock Runtime client.

**Returns:** Boto3 Bedrock Runtime client

**Example:**
```python
bedrock = manager.get_bedrock_runtime_client()
response = bedrock.invoke_model(
    modelId='anthropic.claude-sonnet-4-20250514-v1:0',
    body=json.dumps({"prompt": "Hello"})
)
```

#### `get_s3_client()`

Get or create S3 client.

**Returns:** Boto3 S3 client

**Example:**
```python
s3 = manager.get_s3_client()
response = s3.list_buckets()
```

#### `get_client(service)`

Get a client for any supported AWS service.

**Parameters:**
- `service` (AWSService or str): AWS service enum or service name string

**Returns:** Boto3 client for the service

**Example:**
```python
from src.aws_client_manager import AWSService

# By enum
sagemaker = manager.get_client(AWSService.SAGEMAKER)

# By string
bedrock = manager.get_client("bedrock-runtime")
```

#### `invoke_with_retry(func, *args, **kwargs)`

Invoke a function with retry logic for transient errors.

**Parameters:**
- `func` (callable): Function to invoke (typically a boto3 client method)
- `*args`: Positional arguments for the function
- `**kwargs`: Keyword arguments for the function

**Returns:** Result of the function call

**Raises:** Exception if all retry attempts are exhausted or a non-transient error occurs

**Example:**
```python
response = manager.invoke_with_retry(
    sagemaker.describe_training_job,
    TrainingJobName='my-job'
)
```

#### `is_transient_error(error)`

Determine if an error is transient and should be retried.

**Parameters:**
- `error` (Exception): Exception to check

**Returns:** True if error is transient, False otherwise

**Example:**
```python
from botocore.exceptions import ClientError

error = ClientError(
    {"Error": {"Code": "ThrottlingException"}},
    "operation"
)
is_transient = manager.is_transient_error(error)  # True
```

#### `validate_credentials()`

Validate AWS credentials by making a simple API call.

**Returns:** True if credentials are valid, False otherwise

**Example:**
```python
if manager.validate_credentials():
    print("Credentials are valid")
else:
    print("Credentials are invalid")
```

#### `close_all_clients()`

Close all active boto3 clients.

**Example:**
```python
manager.close_all_clients()
```

### RetryConfig

Configuration class for retry logic with exponential backoff.

#### `__init__(max_attempts=3, initial_backoff_seconds=2.0, max_backoff_seconds=60.0, jitter_factor=0.1)`

Initialize retry configuration.

#### `calculate_backoff(attempt)`

Calculate backoff delay for a given attempt using exponential backoff.

**Parameters:**
- `attempt` (int): Current attempt number (0-indexed)

**Returns:** Backoff delay in seconds

### AWSService

Enumeration of supported AWS services.

**Values:**
- `SAGEMAKER`: "sagemaker"
- `SAGEMAKER_RUNTIME`: "sagemaker-runtime"
- `BEDROCK_RUNTIME`: "bedrock-runtime"
- `S3`: "s3"

## Error Handling

### Transient Errors

The following errors are automatically retried:

- **Connection Errors**: `ConnectionError`, `EndpointConnectionError`
- **Throttling**: `ThrottlingException`, `TooManyRequestsException`, `RequestLimitExceeded`
- **Service Errors**: `ServiceUnavailable`, `InternalError`, `InternalServerError`
- **Timeout**: `RequestTimeout`, `RequestTimeoutException`

### Non-Transient Errors

The following errors are not retried and fail immediately:

- **Validation Errors**: `ValidationException`, `InvalidParameterException`
- **Authorization Errors**: `AccessDeniedException`, `UnauthorizedException`
- **Resource Errors**: `ResourceNotFoundException`, `ResourceInUseException`

### Retry Behavior

1. **Exponential Backoff**: Each retry delay is approximately double the previous delay
2. **Jitter**: Random jitter is added to prevent thundering herd
3. **Maximum Backoff**: Delays are capped at the configured maximum
4. **Maximum Attempts**: Retries stop after the configured maximum attempts

**Example Retry Sequence** (with default config):
- Attempt 1: Immediate
- Attempt 2: Wait ~2 seconds
- Attempt 3: Wait ~4 seconds
- Fail after 3 attempts

## Testing with Mock Clients

The manager supports mock clients for testing:

```python
from unittest.mock import Mock

# Create mock clients
mock_sagemaker = Mock()
mock_sagemaker.describe_training_job.return_value = {
    "TrainingJobName": "test-job",
    "TrainingJobStatus": "Completed"
}

mock_clients = {"sagemaker": mock_sagemaker}

# Initialize with mocks
manager = AWSClientManager(mock_clients=mock_clients)

# Use mock client
sagemaker = manager.get_sagemaker_client()
response = sagemaker.describe_training_job(TrainingJobName="test-job")
```

## Integration with Pipeline

### Loading Configuration from Pipeline Config

```python
import yaml

# Load pipeline configuration
with open("config/pipeline_config.prod.yaml") as f:
    pipeline_config = yaml.safe_load(f)

# Extract AWS configuration
aws_config = {
    "region": pipeline_config["aws"]["region"],
    "retry": pipeline_config.get("retry", {}),
}

# Initialize manager
manager = AWSClientManager(aws_config)
```

### Using with Pipeline Components

```python
from src.aws_client_manager import AWSClientManager

class SyntheticDataGenerator:
    def __init__(self, aws_manager: AWSClientManager):
        self.bedrock = aws_manager.get_bedrock_runtime_client()
        self.aws_manager = aws_manager
    
    def generate_data(self, prompt: str):
        # Use invoke_with_retry for automatic error handling
        response = self.aws_manager.invoke_with_retry(
            self.bedrock.invoke_model,
            modelId='anthropic.claude-sonnet-4-20250514-v1:0',
            body=json.dumps({"prompt": prompt})
        )
        return response
```

## Best Practices

### 1. Use invoke_with_retry for AWS API Calls

Always use `invoke_with_retry` for AWS API calls to handle transient errors automatically:

```python
# Good
response = manager.invoke_with_retry(
    sagemaker.describe_training_job,
    TrainingJobName='my-job'
)

# Avoid
response = sagemaker.describe_training_job(TrainingJobName='my-job')
```

### 2. Configure Appropriate Timeouts

Set timeouts based on your use case:

```python
# For long-running operations
config = {
    "connect_timeout": 60,
    "read_timeout": 300,  # 5 minutes
}

# For quick operations
config = {
    "connect_timeout": 10,
    "read_timeout": 30,
}
```

### 3. Validate Credentials Early

Validate credentials before starting long-running operations:

```python
manager = AWSClientManager(config)

if not manager.validate_credentials():
    raise ValueError("Invalid AWS credentials")

# Proceed with operations
```

### 4. Clean Up Resources

Always clean up clients when done, especially in testing:

```python
try:
    # Use clients
    sagemaker = manager.get_sagemaker_client()
    # ... operations ...
finally:
    manager.close_all_clients()
```

### 5. Use Mock Clients in Tests

Always use mock clients in unit tests to avoid AWS API calls:

```python
def test_my_component():
    mock_sagemaker = Mock()
    mock_sagemaker.list_training_jobs.return_value = {"TrainingJobSummaries": []}
    
    manager = AWSClientManager(mock_clients={"sagemaker": mock_sagemaker})
    
    # Test your component
    component = MyComponent(manager)
    result = component.do_something()
    
    assert result is not None
```

## Logging

The AWS Client Manager integrates with the pipeline logging framework:

```python
from src.logging_config import configure_logging, LogLevel

# Configure logging
configure_logging(
    log_dir="logs",
    console_level=LogLevel.INFO,
    file_level=LogLevel.DEBUG
)

# Manager will log all operations
manager = AWSClientManager(config)
```

**Log Levels:**
- `DEBUG`: Client creation, cache hits
- `INFO`: Initialization, successful retries, credential validation
- `WARNING`: Transient errors with retry information
- `ERROR`: Non-transient errors, exhausted retries

## Troubleshooting

### Issue: "No module named 'boto3'"

**Solution:** Install boto3:
```bash
pip install boto3>=1.28.0
```

### Issue: "Unable to locate credentials"

**Solution:** Configure AWS credentials:
```bash
aws configure
```

Or set environment variables:
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

### Issue: "All retry attempts exhausted"

**Possible Causes:**
1. Service is experiencing prolonged outage
2. Rate limits are too restrictive
3. Network connectivity issues

**Solutions:**
1. Increase `max_attempts` in retry configuration
2. Increase `max_backoff_seconds` for longer waits
3. Check AWS service health dashboard
4. Verify network connectivity

### Issue: "Non-transient error not being retried"

**Explanation:** This is expected behavior. Non-transient errors (like validation errors) should not be retried as they require code or configuration changes.

**Solution:** Fix the underlying issue (invalid parameters, missing permissions, etc.)

## Examples

See `examples/aws_client_manager_example.py` for comprehensive usage examples.

## Related Documentation

- [Logging Guide](LOGGING_GUIDE.md)
- [Pipeline Configuration Guide](../config/CONFIGURATION_GUIDE.md)
- [AWS IAM Setup](../config/aws/README.md)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the examples in `examples/aws_client_manager_example.py`
3. Check the unit tests in `tests/unit/test_aws_client_manager.py`
4. Consult the AWS boto3 documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
