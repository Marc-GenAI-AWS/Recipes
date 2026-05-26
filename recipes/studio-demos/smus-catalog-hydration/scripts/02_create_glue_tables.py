"""Step 2: Create the four retail Glue tables in the project's Glue database.

The project's Glue database is Lake Formation-managed; if your IAM principal is
not already a Lake Formation admin, this script will fail with an
AccessDeniedException. Add the principal as a Lake Formation Data Lake admin
(LF console -> Administrative roles and tasks) before running.
"""
import sys

from smus_demo.config import load_config, glue_client


TABLE_SPECS = {
    "customers": [
        ("customer_id", "bigint"), ("first_name", "string"), ("last_name", "string"),
        ("email", "string"), ("country", "string"), ("signup_date", "string"),
    ],
    "orders": [
        ("order_id", "bigint"), ("customer_id", "bigint"),
        ("order_date", "string"), ("total_amount", "double"), ("status", "string"),
    ],
    "order_items": [
        ("order_item_id", "bigint"), ("order_id", "bigint"),
        ("product_sku", "string"), ("quantity", "int"), ("unit_price", "double"),
    ],
    "order_items_enriched": [
        ("order_item_id", "bigint"), ("order_id", "bigint"), ("customer_id", "bigint"),
        ("country", "string"), ("product_sku", "string"), ("quantity", "int"),
        ("unit_price", "double"), ("line_total", "double"), ("order_date", "string"),
    ],
}


def make_table_input(name: str, columns, location: str) -> dict:
    return {
        "Name": name,
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "classification": "csv",
            "skip.header.line.count": "1",
            "delimiter": ",",
        },
        "StorageDescriptor": {
            "Columns": [{"Name": n, "Type": t} for n, t in columns],
            "Location": location,
            "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe",
                "Parameters": {
                    "field.delim": ",",
                    "separatorChar": ",",
                    "skip.header.line.count": "1",
                },
            },
        },
    }


def main() -> int:
    cfg = load_config()
    glue = glue_client(cfg)

    for name, columns in TABLE_SPECS.items():
        location = f"s3://{cfg.demo_bucket}/retail/{name}/"
        try:
            glue.create_table(
                DatabaseName=cfg.glue_database,
                TableInput=make_table_input(name, columns, location),
            )
            print(f"  created glue table {cfg.glue_database}.{name}")
        except glue.exceptions.AlreadyExistsException:
            glue.update_table(
                DatabaseName=cfg.glue_database,
                TableInput=make_table_input(name, columns, location),
            )
            print(f"  updated existing glue table {cfg.glue_database}.{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
