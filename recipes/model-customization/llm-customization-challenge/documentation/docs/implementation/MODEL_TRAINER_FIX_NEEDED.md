# Model Trainer Fix Needed

**Date:** January 19, 2026  
**Issue:** Training jobs not appearing in AWS SageMaker console  
**Root Cause:** Using low-level `create_training_job` API instead of JumpStartEstimator

## Problem

The current `model_trainer.py` implementation uses the low-level SageMaker `create_training_job` API, which requires:
- Manual specification of training image URI
- Complex configuration of algorithm specifications
- Manual handling of JumpStart model specifics

The `_get_training_image()` method returns a placeholder string instead of the actual JumpStart image URI, causing training jobs to fail silently or not start at all.

## Working Example

The file `example_judge_prompt_engineer/2-sagemaker_finetune_training.py` shows the correct approach using `JumpStartEstimator`:

```python
from sagemaker.jumpstart.estimator import JumpStartEstimator
from sagemaker.inputs import TrainingInput

# Create estimator with model_id
estimator = JumpStartEstimator(
    model_id="meta-textgeneration-llama-3-2-3b-instruct",
    role=role_arn,
    instance_count=1,
    instance_type="ml.g5.12xlarge",
    sagemaker_session=sagemaker_session,
    environment={
        "accept_eula": "true"  # REQUIRED for Llama models
    },
    hyperparameters={
        "chat_dataset": "False",
        "instruction_tuned": "True",
        "use_default_template": "True",
        "epoch": "1",
        "max_steps": "100",
        "learning_rate": "1e-4",
        "per_device_train_batch_size": "1",
        "lora_r": "16",
        "lora_alpha": "64",
        "lora_dropout": "0.05",
        "target_modules": "q_proj,k_proj,v_proj,o_proj"
    },
    output_path=f"s3://{bucket}/fine-tuning-output/{job_name}",
    base_job_name=job_name
)

# Prepare training input
training_input = TrainingInput(
    s3_data=s3_uri,
    content_type="application/jsonlines"
)

# Start training
estimator.fit({"training": training_input}, wait=False)
```

## Required Changes

### 1. Update Imports (DONE)
```python
import boto3
import sagemaker
from sagemaker.jumpstart.estimator import JumpStartEstimator
from sagemaker.inputs import TrainingInput
```

### 2. Update `__init__` Method (DONE)
Add SageMaker session creation:
```python
boto_session = boto3.Session(region_name=self.config.aws_region)
self.sagemaker_session = sagemaker.Session(boto_session=boto_session)
```

### 3. Replace `_create_training_job` Method (TODO)
Replace the entire method with JumpStartEstimator approach:

```python
def _create_training_job_with_jumpstart(
    self,
    job_name: str,
    s3_data_uri: str,
    hyperparameters: Dict[str, Any]
) -> Any:  # Returns estimator
    """Create training job using JumpStartEstimator."""
    
    # Convert hyperparameters to proper format
    jumpstart_hyperparameters = {
        "chat_dataset": "False",
        "instruction_tuned": "True",
        "use_default_template": "True",
        "disable_output_compression": "False",
        "epoch": str(hyperparameters.get("epochs", 1)),
        "max_steps": str(hyperparameters.get("max_steps", 100)),
        "learning_rate": str(hyperparameters.get("learning_rate", 1e-4)),
        "per_device_train_batch_size": str(hyperparameters.get("batch_size", 1)),
        "per_device_eval_batch_size": str(hyperparameters.get("batch_size", 1)),
        "validation_split_ratio": str(hyperparameters.get("validation_split", 0.05)),
        "preprocessing_num_workers": "0",
        "num_workers_dataloader": "0",
        "max_input_length": "2048",
        "gradient_accumulation_steps": "4",
        "lora_r": str(hyperparameters.get("lora_r", 16)),
        "lora_alpha": str(hyperparameters.get("lora_alpha", 64)),
        "lora_dropout": str(hyperparameters.get("lora_dropout", 0.05)),
        "target_modules": "q_proj,k_proj,v_proj,o_proj"
    }
    
    # Create estimator
    estimator = JumpStartEstimator(
        model_id="meta-textgeneration-llama-3-2-3b-instruct",
        role=self.config.sagemaker_role_arn,
        instance_count=1,
        instance_type=self.config.training_instance_type,
        sagemaker_session=self.sagemaker_session,
        environment={
            "accept_eula": "true"  # Required for Llama models
        },
        hyperparameters=jumpstart_hyperparameters,
        output_path=f"s3://{self.config.s3_bucket}/model-artifacts/",
        base_job_name=job_name
    )
    
    # Prepare training input
    training_input = TrainingInput(
        s3_data=s3_data_uri,
        content_type="application/jsonlines"
    )
    
    # Start training (non-blocking)
    estimator.fit({"training": training_input}, wait=False)
    
    return estimator
```

### 4. Update `train_model` Method (TODO)
Replace the call to `_create_training_job` with `_create_training_job_with_jumpstart`:

```python
# OLD:
training_job_response = self._create_training_job(
    job_name=job_name,
    s3_data_uri=s3_data_uri,
    hyperparameters=hyperparameters
)

# NEW:
estimator = self._create_training_job_with_jumpstart(
    job_name=job_name,
    s3_data_uri=s3_data_uri,
    hyperparameters=hyperparameters
)

# Store estimator for later use (deployment)
self._current_estimator = estimator
```

### 5. Update `_wait_for_training` Method (TODO)
Update to work with estimator instead of job name:

```python
def _wait_for_training_with_estimator(
    self,
    estimator: Any,
    job_name: str,
    poll_interval: int = 60
) -> TrainingResult:
    """Wait for training job to complete using estimator."""
    
    logger.info(f"Waiting for training job {job_name} to complete...")
    
    try:
        # The estimator tracks the job internally
        # We can use describe_training_job to monitor
        while True:
            response = self.sagemaker_client.describe_training_job(
                TrainingJobName=job_name
            )
            
            status = response['TrainingJobStatus']
            
            if status in ['Completed', 'Failed', 'Stopped']:
                break
            
            logger.debug(f"Training job {job_name} status: {status}")
            time.sleep(poll_interval)
        
        # Process final status
        if status == 'Completed':
            return TrainingResult(
                job_name=job_name,
                status='Completed',
                model_artifact_s3_uri=response.get('ModelArtifacts', {}).get('S3ModelArtifacts'),
                training_time_seconds=response.get('TrainingTimeInSeconds', 0),
                billable_time_seconds=response.get('BillableTimeInSeconds', 0),
                final_loss=response.get('FinalMetricDataList', [{}])[0].get('Value'),
                error_message=None
            )
        else:
            return TrainingResult(
                job_name=job_name,
                status=status,
                error_message=response.get('FailureReason', 'Training failed')
            )
    
    except Exception as e:
        logger.error(f"Error waiting for training: {e}")
        raise
```

### 6. Remove `_get_training_image` Method (TODO)
This method is no longer needed with JumpStartEstimator.

## Key Differences

| Aspect | Current (Low-level API) | Required (JumpStartEstimator) |
|--------|------------------------|-------------------------------|
| Training Image | Manual placeholder | Automatic from model_id |
| EULA Acceptance | Not handled | Required in environment |
| Hyperparameters | Custom format | JumpStart-specific format |
| Configuration | Complex manual setup | Simple estimator creation |
| Error Handling | Manual | Built-in |

## Benefits of JumpStartEstimator

1. **Automatic Image Resolution**: No need to manually specify training image URIs
2. **Model-Specific Defaults**: Proper defaults for Llama models
3. **EULA Handling**: Built-in support for model license acceptance
4. **Simplified Configuration**: Less boilerplate code
5. **Better Error Messages**: More informative failures
6. **Deployment Integration**: Estimator can be used directly for deployment

## Testing Plan

After implementing changes:

1. **Unit Tests**: Update mocks to work with JumpStartEstimator
2. **Integration Test**: Run actual training job with small dataset
3. **Verify in Console**: Check that job appears in SageMaker console
4. **Monitor Logs**: Ensure proper logging throughout process
5. **Test Deployment**: Verify trained model can be deployed

## Priority

**HIGH** - This is blocking the pipeline from actually training models.

## Estimated Effort

- Code changes: 2-3 hours
- Testing: 1-2 hours
- Documentation: 30 minutes

## Next Steps

1. Implement the changes outlined above
2. Update unit tests to mock JumpStartEstimator
3. Run integration test with real AWS account
4. Update documentation
5. Commit changes

## References

- Working example: `example_judge_prompt_engineer/2-sagemaker_finetune_training.py`
- SageMaker JumpStart docs: https://docs.aws.amazon.com/sagemaker/latest/dg/jumpstart.html
- Current implementation: `src/model_trainer.py`
