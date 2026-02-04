# Automated LLM Finetuning Pipeline - Directory Structure

This document describes the complete directory structure for the automated LLM finetuning pipeline project.

## Root Directory Structure

```
project_root/
├── src/                    # Source code for all pipeline components
├── tests/                  # All test files (unit, property-based, integration)
├── config/                 # Configuration files for pipeline and use cases
├── event_files/            # Pipeline artifacts and intermediate results
├── progress/               # Pipeline execution state and performance history
├── logs/                   # Application logs
└── .kiro/                  # Kiro specifications and documentation
```

## Detailed Structure

### src/ - Source Code
```
src/
├── README.md              # Component overview and development guidelines
└── (Python modules to be added in subsequent tasks)
```

**Purpose**: Contains all source code for the pipeline components including:
- Configuration Manager
- Synthetic Data Generator
- Model Trainer
- Model Deployer
- Inference Engine
- Judge
- Self-Improvement Agent
- Progress Tracker
- Pipeline Orchestrator
- Streamlit UI

### tests/ - Test Suite
```
tests/
├── README.md              # Testing guidelines and instructions
├── unit/                  # Unit tests for individual components
│   └── .gitkeep
├── property/              # Property-based tests using hypothesis
│   └── .gitkeep
├── integration/           # Integration tests for component interactions
│   └── .gitkeep
└── fixtures/              # Test fixtures and mock data
    └── .gitkeep
```

**Purpose**: Comprehensive test coverage including:
- Unit tests (>80% code coverage target)
- Property-based tests (41 correctness properties)
- Integration tests (component interactions)
- Test fixtures (sample data, mock responses)

### config/ - Configuration Files
```
config/
├── README.md              # Configuration file format documentation
└── use_cases/             # Individual use case definitions (YAML)
    └── .gitkeep
```

**Purpose**: Stores configuration files for:
- Pipeline settings (AWS credentials, model IDs, thresholds)
- Use case definitions (descriptions, questions, prompts)
- Environment-specific configurations

**File Formats**:
- `pipeline_config.yaml` - Main pipeline configuration
- `use_cases/*.yaml` - Individual use case definitions

### event_files/ - Pipeline Artifacts
```
event_files/
├── README.md              # File naming conventions and formats
├── questions/             # Test questions for each use case (JSON)
│   └── .gitkeep
├── usecases/              # Use case descriptions (text)
│   └── .gitkeep
├── judge_prompts/         # Judge prompts for evaluation (text)
│   └── .gitkeep
└── training_data/         # Generated training data (JSONL)
    └── .gitkeep
```

**Purpose**: Stores pipeline artifacts matching the existing manual pipeline structure:
- Test questions for evaluation
- Use case descriptions
- Judge prompts
- Generated training data in JSONL format

**File Naming Conventions**:
- Questions: `{use_case_name}_questions.json`
- Use cases: `{use_case_name}_description.txt`
- Judge prompts: `{use_case_name}_judge_prompt.txt`
- Training data: `{use_case_name}_iter{N}_{timestamp}.jsonl`

### progress/ - Pipeline State
```
progress/
├── README.md              # State file formats and resumption guide
├── {use_case_name}/       # Per-use-case progress tracking
│   ├── iteration_{N}_results.json
│   └── pipeline_state_{id}.json
└── performance_reports/   # Generated performance reports
    └── {use_case_name}_report.json
```

**Purpose**: Tracks pipeline execution state and performance:
- Iteration results (win rates, metrics, timestamps)
- Pipeline state for resumption after interruption
- Performance reports with improvement metrics

### logs/ - Application Logs
```
logs/
├── README.md              # Log format and retention policy
└── {use_case_name}_{timestamp}.log
```

**Purpose**: Stores structured application logs:
- Pipeline execution logs
- Component-level diagnostic information
- Error details and stack traces
- Progress updates

**Log Format**: Structured logging with timestamp, level, component, message, and context

## Design Alignment

This directory structure aligns with the design document specifications:

1. **File Organization (Design Section)**: Matches the documented structure exactly
2. **Best Practices Compliance**: Preserves the `event_files/` structure from the manual pipeline
3. **Modularity**: Clear separation of concerns across directories
4. **Testability**: Dedicated test directory with organized subdirectories
5. **Configuration Management**: Centralized configuration with version control support
6. **Observability**: Dedicated directories for logs and progress tracking

## Next Steps

The following tasks will populate these directories:

1. **Task 1.2**: Set up Python virtual environment and dependencies
2. **Task 2.x**: Implement Configuration Manager components in `src/`
3. **Task 3.x**: Implement Synthetic Data Generator in `src/`
4. **Task 11.x**: Implement Streamlit UI in `src/`
5. **Various**: Add unit tests, property tests, and integration tests in `tests/`

## Verification

All directories have been created and verified:
- ✅ All main directories exist
- ✅ All subdirectories exist
- ✅ README.md files added to document each directory
- ✅ .gitkeep files added to ensure empty directories are tracked by git
- ✅ Structure matches design document specifications
