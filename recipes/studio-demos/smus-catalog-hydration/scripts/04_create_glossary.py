"""Step 4: Create the Retail Domain Glossary, terms, and term hierarchy.

Requires the calling principal to be a domain-unit owner (root domain unit) in
the SMUS domain. Add ownership in the portal: Domain settings -> Owners.
"""
import sys

from smus_demo.config import load_config, datazone_client


GLOSSARY_NAME = "Retail Domain Glossary"

# (term_name, short_description, long_description_or_None)
TERMS = [
    ("PII", "Personally Identifiable Information — fields that directly identify an individual.", None),
    ("Confidential", "Data classified Confidential per the data handling policy.", None),
    ("Internal", "Data classified Internal — usable across the organization, not external.", None),
    ("Public", "Data approved for public release. No access controls required.", None),
    ("Restricted", "Highest sensitivity. Requires named approval and is audited per request.",
     "Restricted data includes payment instruments, government IDs, and regulated financial records."),
    ("Customer", "Person or entity that has purchased from the retailer.", None),
    ("Order", "A purchase transaction by a customer; one-to-many with order items.", None),
    ("Product", "A SKU offered for sale. Identified by product_sku in transactional tables.", None),
    ("Revenue", "Monetary value from completed sales (line_total / total_amount).", None),
    ("Average Order Value",
     "Mean revenue per order over a defined period. AOV = total_revenue / order_count.", None),
    ("Analytics Mart", "Curated, denormalized dataset designed for analytics consumption.", None),
    ("Data Classification",
     "Top-level governance label that determines how data may be accessed, shared, retained.", None),
    ("Entity", "A real-world object the business tracks (customer, product, order).", None),
    ("Financial Metric", "Quantitative monetary measure used in reporting.", None),
    ("PII Field", "A column that constitutes Personally Identifiable Information.", None),
    ("Email Address", "Electronic mail address — direct PII identifier.", None),
    ("Customer Name", "Given name and family name of a customer — direct PII identifier.", None),
]

# parent --classifies--> children;  child --isA--> parent.
HIERARCHY = {
    "Data Classification": {"classifies": ["Public", "Internal", "Confidential", "Restricted"]},
    "Public": {"isA": ["Data Classification"]},
    "Internal": {"isA": ["Data Classification"]},
    "Confidential": {"isA": ["Data Classification"]},
    "Restricted": {"isA": ["Data Classification"]},
    "Entity": {"classifies": ["Customer", "Order", "Product"]},
    "Customer": {"isA": ["Entity"]},
    "Order": {"isA": ["Entity"]},
    "Product": {"isA": ["Entity"]},
    "Financial Metric": {"classifies": ["Revenue", "Average Order Value"]},
    "Revenue": {"isA": ["Financial Metric"]},
    "Average Order Value": {"isA": ["Financial Metric"]},
    "PII": {"classifies": ["PII Field"]},
    "PII Field": {"isA": ["PII"], "classifies": ["Email Address", "Customer Name"]},
    "Email Address": {"isA": ["PII Field"]},
    "Customer Name": {"isA": ["PII Field"]},
}


def find_glossary(dz, domain_id: str, project_id: str, name: str) -> str | None:
    res = dz.search(
        domainIdentifier=domain_id,
        searchScope="GLOSSARY",
        owningProjectIdentifier=project_id,
    )
    for item in res.get("items", []):
        g = item.get("glossaryItem")
        if g and g["name"] == name:
            return g["id"]
    return None


def main() -> int:
    cfg = load_config()
    dz = datazone_client(cfg)

    gid = find_glossary(dz, cfg.domain_id, cfg.project_id, GLOSSARY_NAME)
    if gid:
        print(f"Glossary '{GLOSSARY_NAME}' already exists: {gid}")
    else:
        g = dz.create_glossary(
            domainIdentifier=cfg.domain_id,
            owningProjectIdentifier=cfg.project_id,
            name=GLOSSARY_NAME,
            description="Business glossary for retail data assets.",
            status="ENABLED",
        )
        gid = g["id"]
        print(f"Created glossary: {gid}")

    # Enumerate existing terms by name.
    existing: dict[str, str] = {}
    for page in dz.get_paginator("search").paginate(
        domainIdentifier=cfg.domain_id,
        searchScope="GLOSSARY_TERM",
        filters={"filter": {"attribute": "glossaryId", "value": gid}},
    ):
        for item in page["items"]:
            t = item.get("glossaryTermItem")
            if t:
                existing[t["name"]] = t["id"]

    for name, short, long_desc in TERMS:
        if name in existing:
            continue
        kwargs = {
            "domainIdentifier": cfg.domain_id,
            "glossaryIdentifier": gid,
            "name": name,
            "shortDescription": short,
            "status": "ENABLED",
        }
        if long_desc:
            kwargs["longDescription"] = long_desc
        t = dz.create_glossary_term(**kwargs)
        existing[name] = t["id"]
        print(f"  + term {name}")

    # Apply hierarchy.
    for name, rels in HIERARCHY.items():
        if name not in existing:
            continue
        cur = dz.get_glossary_term(domainIdentifier=cfg.domain_id, identifier=existing[name])
        relations = {}
        if "classifies" in rels:
            relations["classifies"] = [existing[c] for c in rels["classifies"] if c in existing]
        if "isA" in rels:
            relations["isA"] = [existing[c] for c in rels["isA"] if c in existing]
        kwargs = {
            "domainIdentifier": cfg.domain_id,
            "identifier": existing[name],
            "name": cur["name"],
            "status": cur.get("status", "ENABLED"),
            "termRelations": relations,
        }
        if cur.get("shortDescription"):
            kwargs["shortDescription"] = cur["shortDescription"]
        if cur.get("longDescription"):
            kwargs["longDescription"] = cur["longDescription"]
        dz.update_glossary_term(**kwargs)
        print(f"  ~ linked {name}: {relations}")

    print(f"\nGlossary id: {gid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
