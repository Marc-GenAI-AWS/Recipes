"""Shared config + small helpers for the SMUS catalog demo scripts.

Reads from environment variables (optionally loaded from a .env file).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import boto3

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass


@dataclass(frozen=True)
class Config:
    region: str
    account_id: str
    domain_id: str
    project_name: str
    glue_database: str
    project_bucket: str
    demo_bucket: str
    project_id: str
    project_execution_role: str | None


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise SystemExit(
            f"Missing required environment variable: {name}\n"
            f"Copy .env.example to .env and fill in the values."
        )
    return val


@lru_cache(maxsize=1)
def load_config() -> Config:
    region = os.environ.get("AWS_REGION", "us-west-2")
    sts = boto3.client("sts", region_name=region)
    account_id = sts.get_caller_identity()["Account"]

    domain_id = _require("DZ_DOMAIN_ID")
    project_name = _require("DZ_PROJECT_NAME")
    glue_database = _require("GLUE_DATABASE")
    project_bucket = _require("PROJECT_BUCKET")
    demo_bucket = os.environ.get(
        "DEMO_BUCKET", f"smus-catalog-demo-{account_id}-{region}"
    )

    dz = boto3.client("datazone", region_name=region)
    project_id = _resolve_project_id(dz, domain_id, project_name)

    return Config(
        region=region,
        account_id=account_id,
        domain_id=domain_id,
        project_name=project_name,
        glue_database=glue_database,
        project_bucket=project_bucket,
        demo_bucket=demo_bucket,
        project_id=project_id,
        project_execution_role=os.environ.get("PROJECT_EXECUTION_ROLE"),
    )


def _resolve_project_id(dz, domain_id: str, project_name: str) -> str:
    paginator = dz.get_paginator("list_projects")
    for page in paginator.paginate(domainIdentifier=domain_id):
        for p in page["items"]:
            if p["name"] == project_name and p.get("projectStatus") == "ACTIVE":
                return p["id"]
    raise SystemExit(
        f"Could not find an ACTIVE project named '{project_name}' in domain {domain_id}."
    )


def datazone_client(cfg: Config | None = None):
    cfg = cfg or load_config()
    return boto3.client("datazone", region_name=cfg.region)


def s3_client(cfg: Config | None = None):
    cfg = cfg or load_config()
    return boto3.client("s3", region_name=cfg.region)


def glue_client(cfg: Config | None = None):
    cfg = cfg or load_config()
    return boto3.client("glue", region_name=cfg.region)


def sagemaker_client(cfg: Config | None = None):
    cfg = cfg or load_config()
    return boto3.client("sagemaker", region_name=cfg.region)
