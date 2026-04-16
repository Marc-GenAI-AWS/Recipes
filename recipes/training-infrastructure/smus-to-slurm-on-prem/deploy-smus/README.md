# Bootstrap — from zero AWS account to a working SMUS demo

The main [`README.md`](../README.md) assumes you already have:

- AWS CLI installed and configured
- A SageMaker Unified Studio domain
- A project in that domain with JupyterLab + managed MLflow enabled

This folder is for getting there. Work top-to-bottom.

---

## 1. Install and configure the AWS CLI

### Install

**macOS** (Homebrew):
```bash
brew install awscli
```

**Linux** (official bundle — works on any arch):
```bash
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o awscliv2.zip
unzip -q awscliv2.zip
sudo ./aws/install
rm -rf awscliv2.zip aws
```

**Windows**: download the MSI from https://awscli.amazonaws.com/AWSCLIV2.msi.

Verify:
```bash
aws --version
# aws-cli/2.x.x Python/... Linux/...
```

### Configure credentials

You need credentials for the account where the SMUS domain lives (or will be created).

```bash
aws configure
#   AWS Access Key ID     [None]: AKIA...
#   AWS Secret Access Key [None]: ...
#   Default region name   [None]: us-west-2
#   Default output format [None]: json
```

If your org uses IAM Identity Center (recommended for humans, and required for SMUS access):
```bash
aws configure sso
# Then follow the browser flow; pick the account and role that can manage SMUS.
```

Verify:
```bash
aws sts get-caller-identity
# Should print your account, user/role ARN, and UserId.
```

---

## 2. Deploy a SageMaker Unified Studio domain

SMUS domains are org-level resources with a lot of moving parts: IAM Identity Center configuration, an S3 bucket, IAM roles, a DataZone domain, optionally a KMS key and VPC. **Use AWS's published CloudFormation quick-setup template** rather than reinventing it.

AWS's guided setup docs:
**https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/setup-quickstart.html**

The short version:

1. In the AWS console, go to **SageMaker Unified Studio → Create domain → Quick setup**.
2. Pick your VPC (a default VPC is fine to start), supply a domain name, confirm.
3. Wait ~10 minutes. The console provisions: DataZone domain, backing IAM roles, a default project profile, blueprints for JupyterLab and MLflow.
4. When status is **Available**, note the **domain ID** (format `dzd_xxxxxxxxxxxxx`) and the **domain URL** (your sign-in link for users).

**Why not script this?** The quick setup requires IAM Identity Center to be enabled in the account (org-level, one-time), touches ~12 AWS services, and the exact CloudFormation varies with account state (existing IdC, existing VPC, etc.). AWS's guided flow handles the branching — a generic third-party script can't.

If you prefer CloudFormation over the console, AWS publishes templates under [aws-samples/amazon-sagemaker-unified-studio-quickstart](https://github.com/aws-samples). Clone, parameterize, `aws cloudformation deploy`.

---

## 3. Create a project and enable MLflow + JupyterLab

Once the domain exists, the project + tooling is scriptable. From this folder:

```bash
python deploy_smus_resources.py --domain-id dzd_xxxxxxxxxxxxx --project-name smus-to-dgx
```

The script will:

1. Verify the domain exists and you have access.
2. Create the project (or reuse one with the same name).
3. List the MLflow tracking servers it finds, so you can confirm or enable MLflow tooling via the SMUS UI.
4. Print the exact values to paste into `sagemaker/launch_to_slurm.py`'s `CONFIG` block.

**What the script does not do yet**:
- Enable the MLflow blueprint for the project. This step is one click in the SMUS UI (Project → Tooling → MLflow → Enable) and the exact blueprint identifier varies by domain setup, so we don't automate it.
- Create the JupyterLab space. Again, one click (Project → Spaces → Create JupyterLab Space).

Both are surfaced as follow-up prompts in the script output.

---

## 4. Return to the main README

Once the project has MLflow and a JupyterLab space, pick up at [*How to reproduce end-to-end*](../README.md#how-to-reproduce-end-to-end) in the main README.
