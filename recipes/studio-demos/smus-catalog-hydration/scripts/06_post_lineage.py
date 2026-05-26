"""Step 6: Post OpenLineage events showing customers + orders + order_items
flowing into order_items_enriched via the daily_retail_etl job.
"""
import json
import sys
import uuid
from datetime import datetime, timezone

from smus_demo.config import load_config, datazone_client


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_dataset(namespace: str, name: str, fields: list[dict], extra_facets: dict | None = None) -> dict:
    facets = {
        "schema": {
            "_producer": "https://github.com/Marc-GenAI-AWS/Recipes",
            "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json",
            "fields": fields,
        }
    }
    if extra_facets:
        facets.update(extra_facets)
    return {"namespace": namespace, "name": name, "facets": facets}


def main() -> int:
    cfg = load_config()
    dz = datazone_client(cfg)
    namespace = f"awsglue://{cfg.account_id}.{cfg.region}/{cfg.glue_database}"

    customers = make_dataset(namespace, "customers", [
        {"name": "customer_id", "type": "bigint"},
        {"name": "first_name", "type": "string"},
        {"name": "last_name", "type": "string"},
        {"name": "email", "type": "string"},
        {"name": "country", "type": "string"},
        {"name": "signup_date", "type": "string"},
    ])
    orders = make_dataset(namespace, "orders", [
        {"name": "order_id", "type": "bigint"},
        {"name": "customer_id", "type": "bigint"},
        {"name": "order_date", "type": "string"},
        {"name": "total_amount", "type": "double"},
        {"name": "status", "type": "string"},
    ])
    order_items = make_dataset(namespace, "order_items", [
        {"name": "order_item_id", "type": "bigint"},
        {"name": "order_id", "type": "bigint"},
        {"name": "product_sku", "type": "string"},
        {"name": "quantity", "type": "int"},
        {"name": "unit_price", "type": "double"},
    ])

    column_lineage = {
        "_producer": "https://github.com/Marc-GenAI-AWS/Recipes",
        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ColumnLineageDatasetFacet.json",
        "fields": {
            "order_item_id": {"inputFields": [{"namespace": namespace, "name": "order_items", "field": "order_item_id"}]},
            "order_id":      {"inputFields": [{"namespace": namespace, "name": "order_items", "field": "order_id"}]},
            "product_sku":   {"inputFields": [{"namespace": namespace, "name": "order_items", "field": "product_sku"}]},
            "quantity":      {"inputFields": [{"namespace": namespace, "name": "order_items", "field": "quantity"}]},
            "unit_price":    {"inputFields": [{"namespace": namespace, "name": "order_items", "field": "unit_price"}]},
            "line_total": {
                "inputFields": [
                    {"namespace": namespace, "name": "order_items", "field": "quantity"},
                    {"namespace": namespace, "name": "order_items", "field": "unit_price"},
                ],
                "transformationDescription": "quantity * unit_price",
                "transformationType": "DERIVATION",
            },
            "customer_id":  {"inputFields": [{"namespace": namespace, "name": "orders", "field": "customer_id"}]},
            "order_date":   {"inputFields": [{"namespace": namespace, "name": "orders", "field": "order_date"}]},
            "country":      {"inputFields": [{"namespace": namespace, "name": "customers", "field": "country"}]},
        },
    }

    enriched = make_dataset(namespace, "order_items_enriched", [
        {"name": "order_item_id", "type": "bigint"},
        {"name": "order_id", "type": "bigint"},
        {"name": "customer_id", "type": "bigint"},
        {"name": "country", "type": "string"},
        {"name": "product_sku", "type": "string"},
        {"name": "quantity", "type": "int"},
        {"name": "unit_price", "type": "double"},
        {"name": "line_total", "type": "double"},
        {"name": "order_date", "type": "string"},
    ], extra_facets={"columnLineage": column_lineage})

    job = {
        "namespace": "smus-demo",
        "name": "daily_retail_etl",
        "facets": {
            "documentation": {
                "_producer": "https://github.com/Marc-GenAI-AWS/Recipes",
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationJobFacet.json",
                "description": "Joins customers, orders, and order_items into a denormalized fact table.",
            },
            "sourceCode": {
                "_producer": "https://github.com/Marc-GenAI-AWS/Recipes",
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SourceCodeJobFacet.json",
                "language": "sql",
                "sourceCode": (
                    "INSERT INTO order_items_enriched\n"
                    "SELECT oi.order_item_id, oi.order_id, o.customer_id, c.country,\n"
                    "       oi.product_sku, oi.quantity, oi.unit_price,\n"
                    "       oi.quantity * oi.unit_price AS line_total, o.order_date\n"
                    "FROM order_items oi\n"
                    "JOIN orders o ON oi.order_id = o.order_id\n"
                    "JOIN customers c ON o.customer_id = c.customer_id;"
                ),
            },
        },
    }

    run_id = str(uuid.uuid4())
    base = {
        "eventTime": now_iso(),
        "producer": "https://github.com/Marc-GenAI-AWS/Recipes",
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent",
        "run": {"runId": run_id},
        "job": job,
        "inputs": [customers, orders, order_items],
        "outputs": [enriched],
    }
    for event_type in ("START", "COMPLETE"):
        ev = dict(base, eventType=event_type, eventTime=now_iso())
        resp = dz.post_lineage_event(domainIdentifier=cfg.domain_id, event=json.dumps(ev))
        print(f"  posted {event_type}: id={resp.get('id')}")
    print(f"Run id: {run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
