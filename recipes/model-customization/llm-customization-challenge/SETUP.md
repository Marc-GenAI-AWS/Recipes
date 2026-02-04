# Setup Guide: Automated LLM Finetuning Pipeline

This guide provides step-by-step instructions for setting up the development environment for the Automated LLM Finetuning Pipeline.

## Prerequisites

- **Python 3.10 or higher** (Python 3.11+ recommended)
- **Windows Operating System** (these instructions are Windows-specific)
- **Git** (for version control)
- **AWS Account** with appropriate permissions for SageMaker, Bedrock, and S3

## Python Version Verification

Before proceeding, verify that you have Python 3.10 or higher installed:

```powershell
python --version
```

Expected output: `Python 3.10.x` or higher (e.g., `Python 3.11.9`)

If you need to install or upgrade Python:
1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, ensure you check "Add Python to PATH"
3. Restart your terminal after installation

## Virtual Environment Setup

### Step 1: Create Virtual Environment

From the project root directory, create a Python virtual environment:

```powershell
python -m venv venv
```

This creates a `venv` directory containing an isolated Python environment.

### Step 2: Activate Virtual Environment

**On Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**

```cmd
.\venv\Scripts\activate.bat
```

After activation, your command prompt should show `(venv)` prefix:

```
(venv) PS C:\path\to\project>
```

### Step 3: Verify Virtual Environment

Confirm you're using the virtual environment's Python:

```powershell
python --version
which python  # or: Get-Command python
```

The path should point to `venv\Scripts\python.exe` in your project directory.

### Step 4: Upgrade pip

Ensure you have the latest version of pip:

```powershell
python -m pip install --upgrade pip
```

## Installing Dependencies

Once the virtual environment is activated, install project dependencies:

```powershell
pip install -r requirements.txt
```

**Note:** The `requirements.txt` file will be created in a subsequent setup task.

## Deactivating Virtual Environment

When you're done working on the project, deactivate the virtual environment:

```powershell
deactivate
```

## Troubleshooting

### PowerShell Execution Policy Error

If you encounter an error like "cannot be loaded because running scripts is disabled", you need to change the PowerShell execution policy:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating the virtual environment again.

### Virtual Environment Not Found

If the activation script is not found:
1. Verify the `venv` directory exists in your project root
2. Ensure you're running the command from the project root directory
3. Try recreating the virtual environment: `python -m venv venv --clear`

### Wrong Python Version

If `python --version` shows a version older than 3.10:
1. Check if you have multiple Python installations
2. Try using `python3` or `py -3.11` instead of `python`
3. Update your PATH environment variable to prioritize the correct Python version

## Next Steps

After setting up the virtual environment:

1. **Install Dependencies**: Create and install from `requirements.txt` (Task 1.1)
2. **Configure AWS**: Set up AWS credentials and IAM roles (Task 1.3)
3. **Run Tests**: Verify the setup by running the test suite
4. **Start Development**: Begin implementing pipeline components

## Additional Resources

- [Python Virtual Environments Documentation](https://docs.python.org/3/library/venv.html)
- [pip User Guide](https://pip.pypa.io/en/stable/user_guide/)
- [AWS SDK for Python (Boto3) Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)

## Environment Variables

The following environment variables may need to be configured (details in AWS setup):

- `AWS_REGION`: AWS region for SageMaker and Bedrock (e.g., `us-east-1`)
- `AWS_PROFILE`: AWS CLI profile name (optional)
- `PYTHONPATH`: Should include the project `src` directory

## Development Tools

Recommended tools for development:

- **IDE**: VS Code, PyCharm, or similar with Python support
- **Linting**: pylint, flake8 (configured in Task 1.2)
- **Type Checking**: mypy (configured in Task 1.2)
- **Testing**: pytest, hypothesis (configured in Task 1.2)

---

**Last Updated**: 2024
**Python Version**: 3.11.9
**Platform**: Windows
