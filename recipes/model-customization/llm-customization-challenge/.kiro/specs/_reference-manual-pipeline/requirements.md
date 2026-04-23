# Requirements Document

## Introduction

This document specifies the requirements for an LLM Fine-tuning Pipeline Best Practices system. The system documents proven patterns, architectural decisions, and operational procedures from a production LLM fine-tuning project that successfully trained domain-specific Llama 3.2 3B models and evaluated them against baseline 70B models using automated judging.

The system captures a complete 6-stage pipeline workflow including data generation, model training, deployment, response generation, comparison, and automated evaluation. These requirements focus on the patterns and practices that enable reliable, scalable, and maintainable LLM fine-tuning operations.

## Glossary

- **Pipeline**: A sequence of automated stages that transform raw requirements into deployed, evaluated fine-tuned models
- **Data_Generator**: Component that uses Claude Sonnet 4 to generate domain-specific training data in JSONL format
- **Fine_Tuner**: Component that trains Llama models using SageMaker JumpStart with LoRA adapters
- **Model_Deployer**: Component that deploys trained models to SageMaker inference endpoints
- **Response_Generator**: Component that generates model responses to test questions
- **Answer_Combiner**: Component that pairs baseline and fine-tuned responses for comparison
- **Answer_Judge**: Component that uses Claude Sonnet 4 to evaluate response quality
- **Use_Case**: A domain-specific application context (e.g., healthcare, gaming, financial compliance)
- **JSONL**: JSON Lines format where each line is a valid JSON object
- **Endpoint**: A SageMaker inference endpoint that serves model predictions
- **Win_Rate**: Percentage of comparisons where fine-tuned model outperforms baseline

## Requirements

### Requirement 1: Pipeline Stage Organization

**User Story:** As a machine learning engineer, I want a clearly numbered sequential pipeline, so that I can understand execution order and dependencies between stages.

#### Acceptance Criteria

1. THE Pipeline SHALL organize stages using numbered prefixes (1-, 2-, 3-, 4-, 5-, 6-)
2. WHEN viewing pipeline scripts, THE System SHALL present them in execution order
3. THE Pipeline SHALL ensure each stage produces outputs required by subsequent stages
4. THE Pipeline SHALL maintain stage independence where outputs are persisted to files
5. WHEN a stage completes, THE System SHALL save results to structured directories

### Requirement 2: Configuration Management

**User Story:** As a developer, I want centralized configuration management, so that I can modify settings without changing code logic.

#### Acceptance Criteria

1. THE System SHALL maintain a central config.py file with AWS regions, model ARNs, and parameters
2. THE System SHALL separate use case mappings into a dedicated usecase_map.py file
3. WHEN configuration changes, THE System SHALL require modifications only to configuration files
4. THE System SHALL provide file path mappings for each use case
5. THE System SHALL define model inference parameters (max_tokens, temperature, top_p) centrally

### Requirement 3: Training Data Generation

**User Story:** As a data engineer, I want automated training data generation, so that I can create domain-specific datasets at scale.

#### Acceptance Criteria

1. WHEN generating data, THE Data_Generator SHALL use Claude Sonnet 4 via AWS Bedrock
2. THE Data_Generator SHALL load domain-specific use case descriptions and judging criteria
3. THE Data_Generator SHALL generate exactly 5 examples per batch in JSONL format
4. THE Data_Generator SHALL validate each JSON line before saving
5. THE Data_Generator SHALL clean unicode characters and ensure ASCII compliance
6. THE Data_Generator SHALL save outputs to data_gen/{domain}_data_gen.jsonl
7. WHEN generating at scale, THE Data_Generator SHALL support batch processing (e.g., 40 batches for 200 examples)

### Requirement 4: Model Fine-tuning

**User Story:** As a machine learning engineer, I want automated SageMaker fine-tuning, so that I can train models with optimal hyperparameters.

#### Acceptance Criteria

1. THE Fine_Tuner SHALL upload training data to S3 before starting training jobs
2. THE Fine_Tuner SHALL use SageMaker JumpStartEstimator for Llama 3.2 3B models
3. THE Fine_Tuner SHALL analyze dataset size to calculate optimal training parameters
4. WHEN dataset has fewer than 100 samples, THE Fine_Tuner SHALL use batch_size=1 and validation_split=0.05
5. WHEN dataset has 100-500 samples, THE Fine_Tuner SHALL use batch_size=1 and validation_split=0.1
6. WHEN dataset has 500-1000 samples, THE Fine_Tuner SHALL use batch_size=2 and validation_split=0.15
7. WHEN dataset has more than 1000 samples, THE Fine_Tuner SHALL use batch_size=4 and cap max_steps at 1000
8. THE Fine_Tuner SHALL configure LoRA parameters (r=16, alpha=64, dropout=0.05)
9. THE Fine_Tuner SHALL set EULA acceptance in environment variables
10. THE Fine_Tuner SHALL provide AWS Console links for monitoring training jobs

### Requirement 5: Model Deployment

**User Story:** As a deployment engineer, I want automated endpoint deployment, so that I can serve fine-tuned models for inference.

#### Acceptance Criteria

1. THE Model_Deployer SHALL retrieve model artifacts from completed training jobs
2. THE Model_Deployer SHALL create JumpStartModel instances with fine-tuned weights
3. THE Model_Deployer SHALL support configurable instance types (ml.g5.xlarge, ml.g5.2xlarge, ml.g5.12xlarge)
4. THE Model_Deployer SHALL set EULA acceptance in model environment variables
5. WHEN deployment completes, THE Model_Deployer SHALL test endpoints with sample prompts
6. THE Model_Deployer SHALL provide endpoint management functions (list, test, delete)
7. THE Model_Deployer SHALL display endpoint ARNs for configuration updates

### Requirement 6: Response Generation

**User Story:** As a quality assurance engineer, I want automated response generation, so that I can evaluate model performance on test questions.

#### Acceptance Criteria

1. THE Response_Generator SHALL load questions from event_files/questions/{usecase}_questions.txt
2. THE Response_Generator SHALL query SageMaker endpoints with configured parameters
3. WHEN API calls fail, THE Response_Generator SHALL retry with exponential backoff (up to 3 attempts)
4. THE Response_Generator SHALL clean responses by removing prompt echoes and normalizing whitespace
5. THE Response_Generator SHALL save progress every 10 items to prevent data loss
6. THE Response_Generator SHALL save outputs to event_files/finetune_answers/{usecase}_finetune_answers.json
7. THE Response_Generator SHALL format outputs matching baseline response structure

### Requirement 7: Answer Combination

**User Story:** As an evaluation engineer, I want side-by-side answer comparison, so that I can prepare data for automated judging.

#### Acceptance Criteria

1. THE Answer_Combiner SHALL load baseline responses from event_files/70b_answers/
2. THE Answer_Combiner SHALL load fine-tuned responses from event_files/finetune_answers/
3. THE Answer_Combiner SHALL extract clean questions by removing role prefixes
4. THE Answer_Combiner SHALL match questions between baseline and fine-tuned responses
5. THE Answer_Combiner SHALL create combined format with usecase, instruction, 70b, and finetuned fields
6. THE Answer_Combiner SHALL save outputs to event_files/combined_answers/{usecase}_combined_answers.json
7. WHEN responses are missing, THE Answer_Combiner SHALL include warning messages in output

### Requirement 8: Automated Judging

**User Story:** As a model evaluator, I want automated quality assessment, so that I can quantify fine-tuned model performance.

#### Acceptance Criteria

1. THE Answer_Judge SHALL load domain-specific judge prompts from event_files/judge_prompts/
2. THE Answer_Judge SHALL use Claude Sonnet 4 via AWS Bedrock for evaluation
3. THE Answer_Judge SHALL compare responses using A/B format (70B vs fine-tuned)
4. THE Answer_Judge SHALL parse JSON responses containing winner, rating, and rationale
5. THE Answer_Judge SHALL calculate win rates and statistics
6. THE Answer_Judge SHALL save progress every 10 judgments
7. THE Answer_Judge SHALL save results to event_files/judge_results/{usecase}_judge_results_{timestamp}.json
8. THE Answer_Judge SHALL include metadata (total questions, win counts, win rate, timestamp)

### Requirement 9: Error Handling and Resilience

**User Story:** As a system operator, I want robust error handling, so that transient failures don't require manual intervention.

#### Acceptance Criteria

1. WHEN API calls fail, THE System SHALL retry with exponential backoff
2. THE System SHALL save progress periodically to enable recovery from failures
3. THE System SHALL validate file existence before processing
4. THE System SHALL validate JSON parsing before saving data
5. WHEN errors occur, THE System SHALL log detailed error messages with tracebacks
6. THE System SHALL handle missing files gracefully with descriptive error messages

### Requirement 10: File Organization

**User Story:** As a project maintainer, I want structured file organization, so that I can locate artifacts and understand data flow.

#### Acceptance Criteria

1. THE System SHALL organize files in an event_files directory with subdirectories
2. THE System SHALL store questions in event_files/questions/
3. THE System SHALL store use case descriptions in event_files/usecases/
4. THE System SHALL store judge prompts in event_files/judge_prompts/
5. THE System SHALL store baseline responses in event_files/70b_answers/
6. THE System SHALL store fine-tuned responses in event_files/finetune_answers/
7. THE System SHALL store combined comparisons in event_files/combined_answers/
8. THE System SHALL store evaluation results in event_files/judge_results/
9. THE System SHALL store generated training data in data_gen/

### Requirement 11: Data Quality Assurance

**User Story:** As a data quality engineer, I want automated data validation, so that training data meets format requirements.

#### Acceptance Criteria

1. WHEN generating training data, THE System SHALL validate each JSON line
2. THE System SHALL replace unicode characters with ASCII equivalents
3. THE System SHALL clean escape characters (\\n, \\t, \\r) from responses
4. THE System SHALL normalize multiple spaces to single spaces
5. THE System SHALL ensure JSONL files contain one valid JSON object per line
6. THE System SHALL use ensure_ascii=True when serializing JSON

### Requirement 12: User Experience

**User Story:** As a pipeline operator, I want clear progress indicators, so that I can monitor long-running operations.

#### Acceptance Criteria

1. WHEN processing items, THE System SHALL display progress as "X/Y completed"
2. THE System SHALL provide interactive prompts for user decisions
3. THE System SHALL display sample outputs after generation
4. THE System SHALL create timestamped output files for versioning
5. THE System SHALL provide AWS Console links for external monitoring
6. WHEN operations complete, THE System SHALL display summary statistics

### Requirement 13: AWS Integration

**User Story:** As a cloud engineer, I want standardized AWS integration patterns, so that I can deploy across accounts and regions.

#### Acceptance Criteria

1. THE System SHALL use boto3 for SageMaker, Bedrock, and S3 operations
2. THE System SHALL accept EULA in environment variables for model deployment
3. THE System SHALL use JumpStart SDK for model management
4. THE System SHALL support cross-account endpoint access
5. THE System SHALL provide endpoint ARNs in standard format
6. THE System SHALL configure AWS regions centrally

### Requirement 14: Scalability Considerations

**User Story:** As a performance engineer, I want scalable processing patterns, so that the pipeline handles varying dataset sizes efficiently.

#### Acceptance Criteria

1. THE System SHALL analyze dataset size before training to optimize hyperparameters
2. THE System SHALL support configurable instance types for different workloads
3. THE System SHALL implement batch processing with progress saves
4. THE System SHALL add delays between API calls to respect rate limits
5. WHEN processing large datasets, THE System SHALL cap training steps at reasonable limits

### Requirement 15: Testing and Validation

**User Story:** As a quality engineer, I want endpoint validation, so that I can verify deployments before production use.

#### Acceptance Criteria

1. WHEN endpoints are deployed, THE System SHALL test with sample prompts
2. THE System SHALL display sample responses for manual verification
3. THE System SHALL calculate and display win rate statistics
4. THE System SHALL track metadata (timestamps, counts, statistics) in results
5. THE System SHALL support manual endpoint testing through interactive prompts

### Requirement 16: Technology Stack and Dependencies

**User Story:** As a developer, I want clearly documented technology dependencies, so that I can replicate the pipeline environment.

#### Acceptance Criteria

1. THE System SHALL use Python 3.x as the primary programming language
2. THE System SHALL use boto3 (>=1.28.0) for AWS service interactions
3. THE System SHALL use sagemaker SDK (>=2.190.0) for model training and deployment
4. THE System SHALL use SageMaker JumpStart SDK for pre-configured model access
5. THE System SHALL use AWS Bedrock for Claude Sonnet 4 API access
6. THE System SHALL use SageMaker JumpStartEstimator for fine-tuning jobs
7. THE System SHALL use SageMaker JumpStartModel for model deployment
8. THE System SHALL use TrainingInput for S3 data configuration
9. THE System SHALL use Predictor with JSONSerializer and JSONDeserializer for inference
10. THE System SHALL target Llama 3.2 3B Instruct models (model_id: meta-textgeneration-llama-3-2-3b-instruct)
11. THE System SHALL use Claude Sonnet 4 for data generation and judging (model_id: us.anthropic.claude-sonnet-4-20250514-v1:0)

### Requirement 17: Reference Implementation Patterns

**User Story:** As a developer, I want proven code templates, so that I can implement similar capabilities using patterns that are known to work.

#### Acceptance Criteria

1. THE System SHALL provide reference implementations for data generation (1-7-disney-generate.py pattern)
2. THE System SHALL provide reference implementations for SageMaker fine-tuning (2-sagemaker_finetune_training.py pattern)
3. THE System SHALL provide reference implementations for endpoint deployment (3-deploy_endpoint.py pattern)
4. THE System SHALL provide reference implementations for response generation (4-get_finetune_answers.py pattern)
5. THE System SHALL provide reference implementations for answer combination (5-combine_answers.py pattern)
6. THE System SHALL provide reference implementations for automated judging (6-judge_answers.py pattern)
7. WHEN implementing data generation, THE System SHALL use boto3.client with configured timeouts and retry settings
8. WHEN calling Bedrock APIs, THE System SHALL implement exponential backoff retry logic
9. WHEN generating training data, THE System SHALL validate and clean JSON before saving
10. WHEN fine-tuning models, THE System SHALL use JumpStartEstimator with LoRA configuration
11. WHEN deploying models, THE System SHALL use JumpStartModel with fine-tuned model_data
12. WHEN generating responses, THE System SHALL clean outputs by removing prompt echoes and normalizing whitespace
13. WHEN combining answers, THE System SHALL extract clean questions by removing role prefixes
14. WHEN judging answers, THE System SHALL parse JSON responses and calculate statistics
