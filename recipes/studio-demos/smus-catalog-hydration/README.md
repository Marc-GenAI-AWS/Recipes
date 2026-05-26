# SageMaker Unified Studio — Catalog Demo

End-to-end "hydration" of a SageMaker Unified Studio (SMUS) project so you can
demo the catalog with realistic content: a retail dataset, a Glue database with
four tables, business glossary with a term hierarchy, asset descriptions and
governance tagging, OpenLineage lineage, a published data product, and a
SageMaker Training Job that produces a deployable model.

The dataset is a small synthetic retail schema:

```
customers ─┐
           ├──► order_items_enriched   (daily_retail_etl job)
orders ────┤
           │
order_items
```

## What gets created

| Layer | Resource |
|---|---|
| S3 | `smus-catalog-demo-<account>-<region>` bucket with 4 retail CSVs |
| Glue | 4 tables in your project's Glue database (`customers`, `orders`, `order_items`, `order_items_enriched`) |
| SMUS Catalog | 4 published assets with descriptions and glossary tags |
| SMUS | "Retail Domain Glossary" with 17 terms and a parent/child hierarchy |
| SMUS | OpenLineage events for the `daily_retail_etl` job, including column-level lineage |
| SMUS | "Retail Analytics Mart" data product bundling all 4 assets |
| SageMaker | A Training Job that produces a deployable sklearn linear-regression model |

## Prerequisites

1. **An SMUS V2 domain** with a project that has the standard SageMaker
   project profile applied. The default profile provisions Tooling, LakeHouseDatabase,
   LakehouseCatalog, MLExperiments, and EmrServerless environments. You'll
   reference the project by name in `.env`.
2. **AWS credentials** configured locally (`aws configure`).
3. **Python 3.10+**.

### IAM permissions for your CLI principal

The principal you authenticate with locally needs IAM-side access for DataZone,
Glue, S3, SageMaker, and Lake Formation. The simplest setup is to attach AWS
managed policies. The least-permission alternative is at the bottom.

**Option A — managed policies (quickest):**

```
AmazonDataZoneFullAccess
AmazonS3FullAccess
AWSGlueConsoleFullAccess
AmazonSageMakerFullAccess
AWSLakeFormationDataAdmin
```

> ⚠️ Never commit credentials. The repo's `.gitignore` excludes `.env`; the
> `.env.example` only contains placeholders, no account-specific values.

**Option B — least-privilege custom policy** (paste into a new IAM policy and
attach to your user/role):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DataZone",
      "Effect": "Allow",
      "Action": [
        "datazone:*",
        "iam:PassRole"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Glue",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase", "glue:GetDatabases",
        "glue:CreateTable", "glue:UpdateTable", "glue:GetTable", "glue:GetTables",
        "glue:DeleteTable"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3DemoBucket",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket", "s3:ListBucket", "s3:GetObject", "s3:PutObject",
        "s3:DeleteObject", "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::smus-catalog-demo-*",
        "arn:aws:s3:::smus-catalog-demo-*/*",
        "arn:aws:s3:::amazon-sagemaker-*",
        "arn:aws:s3:::amazon-sagemaker-*/*"
      ]
    },
    {
      "Sid": "SageMaker",
      "Effect": "Allow",
      "Action": [
        "sagemaker:CreateTrainingJob", "sagemaker:DescribeTrainingJob",
        "sagemaker:StopTrainingJob", "sagemaker:CreateModelPackageGroup",
        "sagemaker:CreateModelPackage", "sagemaker:DescribeModelPackage",
        "sagemaker:UpdateModelPackage", "sagemaker:ListModelPackages",
        "sagemaker:CreateModel", "sagemaker:CreateEndpointConfig",
        "sagemaker:CreateEndpoint", "sagemaker:DescribeEndpoint",
        "sagemaker:DeleteEndpoint", "sagemaker:DeleteEndpointConfig",
        "sagemaker:DeleteModel", "sagemaker:AddTags", "sagemaker:ListTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "LakeFormation",
      "Effect": "Allow",
      "Action": [
        "lakeformation:GetDataLakeSettings",
        "lakeformation:PutDataLakeSettings",
        "lakeformation:GrantPermissions",
        "lakeformation:RevokePermissions",
        "lakeformation:ListPermissions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "STS",
      "Effect": "Allow",
      "Action": ["sts:GetCallerIdentity"],
      "Resource": "*"
    }
  ]
}
```

### Lake Formation setup (one-time)

The project's Glue database is Lake Formation–managed. Your IAM principal must
be a **Data Lake Admin** to create tables in it.

In the AWS console: Lake Formation → *Administrative roles and tasks* → *Data
lake administrators* → **Add** → choose your IAM user/role.

Or via CLI (replace the principal ARN):

```bash
aws lakeformation get-data-lake-settings --region us-west-2 > lf.json
# Edit lf.json: append your principal ARN to DataLakeSettings.DataLakeAdmins
aws lakeformation put-data-lake-settings --region us-west-2 --cli-input-json file://lf.json
```

After becoming an admin, grant yourself table-creation permission on the
project's Glue database (one-time):

```bash
aws lakeformation grant-permissions --region us-west-2 \
  --principal DataLakePrincipalIdentifier=<your-iam-arn> \
  --resource '{"Database":{"Name":"<your-glue-db>"}}' \
  --permissions CREATE_TABLE DESCRIBE
```

### SMUS portal authorization (one-time)

These can only be set in the SMUS portal — not via IAM.

1. **Project membership**: open your project → *Members* → **Add** → choose
   your IAM principal as **Owner**. This is required for steps 3, 5, 6, 7.
2. **Domain unit ownership**: from the Domain page → *Owners* → **Add** your
   IAM principal. Required for step 4 (`CreateGlossary`).
3. **Policy grant** for `CREATE_GLOSSARY` and `CREATE_FORM_TYPE` on the root
   domain unit, granted to your project with designation `OWNER`. Either do
   this in the portal (Domain → Authorization → Policies), or once via CLI:

   ```bash
   aws datazone add-policy-grant --region us-west-2 \
     --domain-identifier <DZ_DOMAIN_ID> \
     --entity-type DOMAIN_UNIT --entity-identifier <root-domain-unit-id> \
     --policy-type CREATE_GLOSSARY \
     --principal '{"project":{"projectIdentifier":"<your-project-id>","projectDesignation":"OWNER"}}' \
     --detail '{"createGlossary":{}}'
   ```

## Setup

```bash
git clone <this-repo> smus-catalog-demo
cd smus-catalog-demo

python -m venv .venv
. .venv/bin/activate    # PowerShell: .venv\Scripts\Activate.ps1

pip install -r requirements.txt

cp .env.example .env
# Fill in DZ_DOMAIN_ID, DZ_PROJECT_NAME, GLUE_DATABASE, PROJECT_BUCKET
```

### Where to find the values for `.env`

- `DZ_DOMAIN_ID` — the SMUS portal URL: `https://dzd_xxxx.sagemaker.<region>.on.aws`. The `dzd_xxxx` is the id.
- `DZ_PROJECT_NAME` — the project name as it appears in the portal (e.g. `SMUS-Demo`).
- `GLUE_DATABASE` — open the project → Environments → **LakeHouseDatabase** → `glueDBName` (typically `glue_db_<envId>`).
- `PROJECT_BUCKET` — same screen, `glueOutputUri` is `s3://<project-bucket>/...`. Use just the bucket name.
- `PROJECT_EXECUTION_ROLE` (only needed for step 8) — Project → Environments → **Tooling** → `userRoleArn`.

## Run the demo

Each step is idempotent and can be re-run.

```bash
python -m scripts.01_upload_data
python -m scripts.02_create_glue_tables
python -m scripts.03_run_data_source       # publishes assets into the SMUS catalog
python -m scripts.04_create_glossary
python -m scripts.05_enrich_assets          # descriptions + glossary tagging
python -m scripts.06_post_lineage           # OpenLineage events
python -m scripts.07_create_data_product    # bundles + publishes the data product
python -m scripts.08_run_training_job       # ~5–7 min; needs PROJECT_EXECUTION_ROLE
```

After step 8 finishes, open the SMUS portal:

- **Browse Assets** — the four retail tables with descriptions, glossary chips, and lineage tab.
- **Browse Data Products** — "Retail Analytics Mart".
- **Glossaries** — "Retail Domain Glossary" with the term hierarchy.
- **Training Jobs** (in your project) → click `retail-line-total-...` → **Register model** → **Deploy**.

## Repo layout

```
.
├── README.md
├── requirements.txt
├── .env.example
├── data/                  # sample retail CSVs
├── smus_demo/
│   ├── __init__.py
│   └── config.py          # env loader + boto3 client factories
└── scripts/
    ├── 01_upload_data.py
    ├── 02_create_glue_tables.py
    ├── 03_run_data_source.py
    ├── 04_create_glossary.py
    ├── 05_enrich_assets.py
    ├── 06_post_lineage.py
    ├── 07_create_data_product.py
    ├── 08_run_training_job.py
    └── training/
        ├── train.py       # SKLearn entry point used by the training job
        └── inference.py   # SageMaker handlers for real-time inference
```

## Troubleshooting

**`AccessDenied` on `glue:CreateTable`** — the project's Glue database is
managed by Lake Formation. Make sure your IAM principal is a Data Lake Admin
and has `CREATE_TABLE` + `DESCRIBE` on the database. Use the LF console
(*Administrative roles and tasks* + *Data permissions*).

**`AccessDenied` on `datazone:CreateGlossary`** — your principal isn't an
owner of the root domain unit. Add it in the SMUS portal under Domain
settings → Owners.

**Step 3 says "Could not find a default Glue data source"** — verify that
`GLUE_DATABASE` matches the value in your project's LakeHouseDatabase
environment. SMUS auto-creates one Glue data source per project per
LakeHouseDatabase environment.

**Step 8 fails with `s3:ListBucket` denied on the demo bucket** — the project
execution role only has access to the project's managed bucket. Step 1 stages
the training CSV into the project bucket; if you skipped step 1, re-run it.

**Step 8 endpoint deploy fails ping check (sklearn version mismatch)** — only
register/deploy via the SMUS Training Jobs UI flow (recommended). If you build
your own `model.tar.gz` outside the training job, make sure the sklearn
version that pickled it matches the SageMaker DLC's sklearn version.

## Cleanup

This repo doesn't include a teardown script. To remove everything:

- SageMaker: delete the endpoint, endpoint config, model, model package, and model package group.
- Training Jobs: cannot be deleted, but you can stop running ones.
- DataZone: delete the data product, then revoke listings, then delete the glossary, then delete the assets.
- Glue: drop the four tables (Lake Formation may require admin grants).
- S3: empty and delete the demo bucket; remove `dev/data/ml/retail-line-total/` from the project bucket.

## Contributing

PRs welcome. Useful additions:

- A teardown script.
- A Terraform variant.
- A notebook version of step 8 to run end-to-end inside SMUS JupyterLab.
