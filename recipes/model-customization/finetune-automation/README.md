# SageMaker Fine-tuning Automation

![Retro Wave Theme](./vibe_themes/car-outrun-synthwave-city-building-sunset-palm-tree-digital-art-4k-wallpaper-uhdpaper.com-275@0@j.jpg)

## 🚀 Overview

This project provides an end-to-end solution for automating the fine-tuning of Large Language Models (LLMs) using Amazon SageMaker. It features a Streamlit dashboard with a retro wave theme that guides users through the entire process, from generating synthetic training data to deploying and testing fine-tuned models.

## ✨ Features

- **Synthetic Data Generation**: Create domain-specific training data for fine-tuning LLMs
- **S3 Integration**: Seamless upload of training data to Amazon S3
- **Automated Fine-tuning**: Configure and execute fine-tuning jobs on Amazon SageMaker
- **Model Deployment**: Deploy fine-tuned models to SageMaker endpoints
- **Inference Testing**: Test deployed models with sample prompts
- **Custom Use Case Configuration**: Generate configurations for new domains using Perplexity API

## 🛠️ Workflow Steps

1. **Generate Synthetic Data**: Create training data based on selected use case
2. **Upload to S3**: Transfer the generated data to Amazon S3
3. **Fine-tune LLM**: Configure and start the fine-tuning process on SageMaker
4. **Compress Model Files**: Package model files for deployment
5. **Deploy Model**: Create a SageMaker endpoint for inference
6. **Test Inference**: Validate the deployed model with sample prompts

## 🔑 Prerequisites & Environment Variables

Before getting started, ensure you have the following prerequisites and environment variables set up:

### Required Tools
- **AWS CLI**: Install and configure with admin access or with specific IAM roles for SageMaker and S3 full access
- **Python 3.8+**: Required to run the scripts and dashboard

### API Keys
- **Hugging Face API Key**: Required for accessing model repositories and downloads
- **Perplexity API Key**: Used for generating synthetic data through the Perplexity service

### Environment Setup
```bash
# AWS Configuration
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-west-2  # or your preferred region

# API Keys
export HUGGINGFACE_TOKEN=your_huggingface_token
export PERPLEXITY_API_KEY=your_perplexity_api_key
```

Alternatively, you can configure these in the `config.yaml` file.

## 🔧 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/SageMaker-finetune-automation.git
cd SageMaker-finetune-automation

# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials
aws configure
```

## ⚙️ Configuration

Update the `config.yaml` file with your specific settings:

- AWS region and credentials
- S3 bucket names
- SageMaker role ARN
- Model parameters
- Data paths

## 🖥️ Usage

Launch the dashboard:

```bash
streamlit run synthwave_dashboard.py
```

Navigate through the tabs to:
- Select or create use cases
- Generate synthetic training data
- Upload data to S3
- Configure and start fine-tuning jobs
- Deploy models to SageMaker endpoints
- Test models with inference requests

## 🌟 Custom Use Cases

The dashboard provides a dedicated tab for generating new use case configurations:

1. Select a domain and describe your use case
2. Configure system and user prompts
3. Set data generation parameters
4. Generate and save the configuration

## 📊 Dashboard

The dashboard is built with Streamlit and features a retro wave theme with:
- Tab-based navigation
- Real-time job status monitoring
- Configuration management
- Log viewing capabilities

## 🔒 Security

- AWS credentials can be configured via environment variables or AWS CLI
- Sensitive information should not be hardcoded in configuration files

## 📋 Requirements

- Python 3.8+
- AWS account with SageMaker access
- Required Python packages (see `requirements.txt`)

## 📝 License

[Your license information here]

## 👥 Contributors

[Your contributor information here]

---

*Built with ❤️ for simplifying LLM fine-tuning workflows*
