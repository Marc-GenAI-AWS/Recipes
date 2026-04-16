"""
deploy-smus/deploy_smus_resources.py

Given an existing SMUS (DataZone) domain, create a project and print the
values to paste into `sagemaker/launch_to_slurm.py`'s CONFIG
block.

Scope (deliberately conservative):
  - Verifies AWS CLI credentials resolve.
  - Confirms the domain exists and is accessible.
  - Creates a project with the given name, or reuses an existing one.
  - Lists any MLflow tracking servers in the region so the user can
    identify the ARN to use (or confirms there are none yet).
  - Prints the next manual steps (enable MLflow tool, create JupyterLab
    space) and the final CONFIG block shape.

What is intentionally NOT automated:
  - Domain creation (see deploy-smus/README.md — use AWS's quick setup).
  - Enabling the MLflow project tool. The blueprint identifier varies by
    domain configuration; a one-click UI action beats a brittle script.
  - JupyterLab space creation. Same reason.

Usage:
    python deploy_smus_resources.py --domain-id dzd_xxxxxxxxxxxxx \\
        --project-name smus-to-dgx \\
        [--region us-west-2]
"""

from __future__ import annotations

import argparse
import sys
import textwrap

import boto3
from botocore.exceptions import ClientError


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def verify_credentials(region: str) -> dict:
    try:
        ident = boto3.client("sts", region_name=region).get_caller_identity()
    except Exception as e:
        die(f"AWS credentials not usable: {e}. Run `aws configure` first.")
    print(f"✓ AWS identity: {ident['Arn']}")
    return ident


def verify_domain(dz, domain_id: str) -> dict:
    try:
        d = dz.get_domain(identifier=domain_id)
    except ClientError as e:
        die(f"could not read domain {domain_id}: {e.response['Error']['Message']}")
    print(f"✓ Domain {domain_id} found (name={d.get('name')}, status={d.get('status')})")
    return d


def find_or_create_project(dz, domain_id: str, project_name: str) -> dict:
    existing = dz.list_projects(domainIdentifier=domain_id, name=project_name).get("items", [])
    if existing:
        p = existing[0]
        print(f"✓ Project '{project_name}' already exists (id={p['id']})")
        return p
    print(f"→ Creating project '{project_name}' ...")
    p = dz.create_project(
        domainIdentifier=domain_id,
        name=project_name,
        description="Created by smus-to-slurm-on-prem deploy-smus script.",
    )
    print(f"✓ Project created (id={p['id']})")
    return p


def list_mlflow_servers(region: str) -> list[dict]:
    sm = boto3.client("sagemaker", region_name=region)
    items = sm.list_mlflow_tracking_servers().get("TrackingServerSummaries", [])
    return items


def print_next_steps(
    account_id: str,
    region: str,
    domain_id: str,
    project_name: str,
    project_id: str,
    mlflow_servers: list[dict],
) -> None:
    print()
    print("─" * 72)
    print("Next steps")
    print("─" * 72)
    print()
    print(
        textwrap.dedent(f"""
        1. In the SMUS console, open the project and enable the tools you need:

             Domain:   {domain_id}
             Project:  {project_name} (id={project_id})
             URL:      https://{domain_id}.sagemaker.{region}.on.aws

           In Project → Tooling, enable:
             - MLflow tracking server (if not already present)
             - JupyterLab (this provisions a default JupyterSpace)

        2. Once MLflow is enabled, its tracking server ARN will have the form:

             arn:aws:sagemaker:{region}:{account_id}:mlflow-tracking-server/<name>

           Discover it with:

             aws sagemaker list-mlflow-tracking-servers --region {region}
        """).strip()
    )

    print()
    if mlflow_servers:
        print("MLflow tracking servers currently visible in this region:")
        for s in mlflow_servers:
            print(f"  - {s['TrackingServerArn']}  [{s['TrackingServerStatus']}]")
    else:
        print("(No MLflow tracking servers found yet — enable it via Project → Tooling.)")

    print()
    print("─" * 72)
    print("When ready, paste into sagemaker/launch_to_slurm.py → CONFIG")
    print("─" * 72)
    print(
        textwrap.dedent(f"""
        SLURM_REST_URL      = "<paste tunnel URL from your on-prem setup>"
        SLURM_JWT           = "<scontrol token minted for SLURM_USER>"
        SLURM_USER          = "<POSIX user on the on-prem cluster>"
        SLURM_REPO_PATH     = "<absolute path of this repo's clone on the cluster>"
        MLFLOW_TRACKING_URI = "<one of the ARNs above, once MLflow is enabled>"
        """).strip()
    )
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--domain-id", required=True,
                    help="SMUS domain id (format: dzd_xxxxxxxxxxxxx)")
    ap.add_argument("--project-name", required=True,
                    help="project name to create or reuse")
    ap.add_argument("--region", default=None,
                    help="AWS region (defaults to AWS_DEFAULT_REGION / profile)")
    args = ap.parse_args()

    region = args.region or boto3.Session().region_name
    if not region:
        die("no region — pass --region or set AWS_DEFAULT_REGION.")

    ident = verify_credentials(region)
    dz = boto3.client("datazone", region_name=region)
    verify_domain(dz, args.domain_id)
    project = find_or_create_project(dz, args.domain_id, args.project_name)
    mlflow_servers = list_mlflow_servers(region)

    print_next_steps(
        account_id=ident["Account"],
        region=region,
        domain_id=args.domain_id,
        project_name=args.project_name,
        project_id=project["id"],
        mlflow_servers=mlflow_servers,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
