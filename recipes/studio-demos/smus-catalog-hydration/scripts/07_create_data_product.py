"""Step 7: Bundle the four retail assets into a 'Retail Analytics Mart' data product
and publish it so it appears in Browse Data Products.
"""
import sys

from smus_demo.config import load_config, datazone_client


PRODUCT_NAME = "Retail Analytics Mart"
ASSETS_TO_BUNDLE = ["customers", "orders", "order_items", "order_items_enriched"]
PRODUCT_TERMS = ["Analytics Mart", "Revenue", "Average Order Value", "Customer", "Order", "Product"]
GLOSSARY_NAME = "Retail Domain Glossary"


def main() -> int:
    cfg = load_config()
    dz = datazone_client(cfg)

    asset_search = dz.search(
        domainIdentifier=cfg.domain_id,
        searchScope="ASSET",
        owningProjectIdentifier=cfg.project_id,
        maxResults=50,
    )
    assets = {i["assetItem"]["name"]: i["assetItem"]
              for i in asset_search["items"] if "assetItem" in i}
    items = [
        {"identifier": assets[n]["identifier"], "itemType": "ASSET"}
        for n in ASSETS_TO_BUNDLE if n in assets
    ]
    if len(items) < len(ASSETS_TO_BUNDLE):
        missing = [n for n in ASSETS_TO_BUNDLE if n not in assets]
        print(f"  ! missing assets: {missing} (run step 3 first)", file=sys.stderr)
        return 1

    glossary_search = dz.search(
        domainIdentifier=cfg.domain_id, searchScope="GLOSSARY",
        owningProjectIdentifier=cfg.project_id,
    )
    gid = next((i["glossaryItem"]["id"] for i in glossary_search["items"]
                if i.get("glossaryItem", {}).get("name") == GLOSSARY_NAME), None)
    terms: dict[str, str] = {}
    if gid:
        for page in dz.get_paginator("search").paginate(
            domainIdentifier=cfg.domain_id, searchScope="GLOSSARY_TERM",
            filters={"filter": {"attribute": "glossaryId", "value": gid}},
        ):
            for i in page["items"]:
                t = i.get("glossaryTermItem")
                if t:
                    terms[t["name"]] = t["id"]

    # Idempotency: re-running should not create a second "Retail Analytics Mart".
    existing = next(
        (i["dataProductItem"]["identifier"]
         for i in dz.search(
             domainIdentifier=cfg.domain_id, searchScope="DATA_PRODUCT",
             owningProjectIdentifier=cfg.project_id,
         ).get("items", [])
         if i.get("dataProductItem", {}).get("name") == PRODUCT_NAME),
        None,
    )
    if existing:
        print(f"Data product '{PRODUCT_NAME}' already exists: {existing} (skipping create)")
        return 0

    dp = dz.create_data_product(
        domainIdentifier=cfg.domain_id,
        owningProjectIdentifier=cfg.project_id,
        name=PRODUCT_NAME,
        description=(
            "Curated retail analytics package. Bundles the customer master, orders, order items, "
            "and the denormalized order_items_enriched fact for revenue, AOV, and country analytics. "
            "Subscribe to this product to receive grants on all four assets in one approval. "
            "Owned by Analytics Engineering. SLA: order_items_enriched available by 04:00 UTC daily."
        ),
        items=items,
        glossaryTerms=[terms[t] for t in PRODUCT_TERMS if t in terms],
    )
    print(f"Created data product: {dp['id']} with {len(items)} items")

    publish = dz.create_listing_change_set(
        domainIdentifier=cfg.domain_id,
        entityType="DATA_PRODUCT",
        entityIdentifier=dp["id"],
        action="PUBLISH",
    )
    print(f"Published listing: {publish['listingId']} ({publish['status']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
