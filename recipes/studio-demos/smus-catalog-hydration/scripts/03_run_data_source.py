"""Step 3: Run the SMUS project's default Glue data source so the new tables
appear as catalog assets in the SMUS-Demo project.

V2 SMUS domains auto-create a default Glue data source per project named
'<account>-AwsDataCatalog-<glueDb>-default-datasource'. This script finds it
and triggers a run.
"""
import sys
import time

from smus_demo.config import load_config, datazone_client


def find_default_glue_data_source(dz, domain_id: str, project_id: str, glue_db: str) -> str:
    expected_suffix = f"-AwsDataCatalog-{glue_db}-default-datasource"
    paginator = dz.get_paginator("list_data_sources")
    for page in paginator.paginate(domainIdentifier=domain_id, projectIdentifier=project_id):
        for ds in page["items"]:
            if ds["type"] == "GLUE" and ds["name"].endswith(expected_suffix):
                return ds["dataSourceId"]
    raise SystemExit(
        f"Could not find a default Glue data source ending with '{expected_suffix}'.\n"
        f"Verify GLUE_DATABASE matches the project's LakeHouseDatabase environment."
    )


def main() -> int:
    cfg = load_config()
    dz = datazone_client(cfg)

    ds_id = find_default_glue_data_source(dz, cfg.domain_id, cfg.project_id, cfg.glue_database)
    print(f"Found data source: {ds_id}")

    run = dz.start_data_source_run(domainIdentifier=cfg.domain_id, dataSourceIdentifier=ds_id)
    run_id = run["id"]
    print(f"Started run: {run_id}")

    while True:
        info = dz.get_data_source_run(domainIdentifier=cfg.domain_id, identifier=run_id)
        status = info["status"]
        if status in ("SUCCESS", "PARTIALLY_SUCCEEDED", "FAILED"):
            print(f"Run finished with status={status}; stats={info.get('runStatisticsForAssets')}")
            return 0 if status != "FAILED" else 1
        print(f"  status={status}, waiting...")
        time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
