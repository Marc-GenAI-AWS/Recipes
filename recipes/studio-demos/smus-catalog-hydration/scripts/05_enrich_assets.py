"""Step 5: Apply README descriptions and glossary terms to the four retail assets."""
import sys

from smus_demo.config import load_config, datazone_client


GLOSSARY_NAME = "Retail Domain Glossary"

DESCRIPTIONS = {
    "customers": (
        "CUSTOMERS — authoritative master record of every retail customer.\n\n"
        "Source of truth for the Customer entity. One row per customer_id. Contains direct PII "
        "(first_name, last_name, email) and is therefore tagged Confidential.\n\n"
        "Owner: Retail Data Platform team | Refresh: Daily 02:00 UTC | Subscription: approval required."
    ),
    "orders": (
        "ORDERS — header-level fact table; one row per customer order.\n\n"
        "Joins to customers on customer_id and to order_items on order_id.\n\n"
        "Owner: Retail Data Platform team | Refresh: Hourly | Grain: order."
    ),
    "order_items": (
        "ORDER_ITEMS — line-item detail for each order.\n\n"
        "Joins to orders on order_id; product_sku links to the (external) product master.\n\n"
        "Owner: Retail Data Platform team | Refresh: Hourly | Grain: order_item."
    ),
    "order_items_enriched": (
        "ORDER_ITEMS_ENRICHED — denormalized analytics fact (the 'mart').\n\n"
        "Produced by the daily_retail_etl job. Pre-computes line_total = quantity * unit_price.\n\n"
        "Owner: Analytics Engineering | SLA: 04:00 UTC daily | Use: revenue, AOV, country analytics."
    ),
}

ASSET_TERMS = {
    "customers": ["PII", "Confidential", "Customer", "Email Address", "Customer Name"],
    "orders": ["Internal", "Order", "Revenue"],
    "order_items": ["Internal", "Order", "Product"],
    "order_items_enriched": [
        "Internal", "Analytics Mart", "Revenue", "Average Order Value", "Customer", "Order", "Product",
    ],
}


def find_glossary_id(dz, domain_id, project_id) -> str:
    res = dz.search(domainIdentifier=domain_id, searchScope="GLOSSARY",
                    owningProjectIdentifier=project_id)
    for item in res.get("items", []):
        g = item.get("glossaryItem")
        if g and g["name"] == GLOSSARY_NAME:
            return g["id"]
    raise SystemExit(f"Glossary '{GLOSSARY_NAME}' not found. Run step 4 first.")


def main() -> int:
    cfg = load_config()
    dz = datazone_client(cfg)

    gid = find_glossary_id(dz, cfg.domain_id, cfg.project_id)
    terms: dict[str, str] = {}
    for page in dz.get_paginator("search").paginate(
        domainIdentifier=cfg.domain_id,
        searchScope="GLOSSARY_TERM",
        filters={"filter": {"attribute": "glossaryId", "value": gid}},
    ):
        for item in page["items"]:
            t = item.get("glossaryTermItem")
            if t:
                terms[t["name"]] = t["id"]

    res = dz.search(
        domainIdentifier=cfg.domain_id,
        searchScope="ASSET",
        owningProjectIdentifier=cfg.project_id,
        maxResults=50,
    )
    assets = {i["assetItem"]["name"]: i["assetItem"] for i in res["items"] if "assetItem" in i}

    for name, desc in DESCRIPTIONS.items():
        if name not in assets:
            print(f"  ! asset '{name}' not in catalog — did step 3 succeed?")
            continue
        full = dz.get_asset(domainIdentifier=cfg.domain_id, identifier=assets[name]["identifier"])
        forms = [
            {
                "formName": f["formName"],
                "typeIdentifier": f["typeName"],
                "typeRevision": f["typeRevision"],
                "content": f.get("content", ""),
            }
            for f in full["formsOutput"] if f.get("content")
        ]
        glossary_term_ids = [terms[t] for t in ASSET_TERMS.get(name, []) if t in terms]
        rev = dz.create_asset_revision(
            domainIdentifier=cfg.domain_id,
            identifier=assets[name]["identifier"],
            name=full["name"],
            description=desc,
            formsInput=forms,
            glossaryTerms=glossary_term_ids,
        )
        print(f"  enriched {name}: revision {rev['revision']} with {len(glossary_term_ids)} terms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
