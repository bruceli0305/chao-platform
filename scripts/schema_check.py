import os
import sys

import psycopg
from dotenv import load_dotenv


REQUIRED_TABLES = [
    "tasks",
    "task_routes",
    "historian_records",
    "gate_results",
    "context_chunks",
    "confirmations",
    "task_events",
    "tool_calls",
    "artifacts",
    "data_assets",
    "storage_policies",
]

REQUIRED_VIEWS = [
    "artifact_records",
]

REQUIRED_EXTENSIONS = [
    "vector",
]

REQUIRED_STORAGE_POLICIES = [
    "D0_PUBLIC_KNOWLEDGE",
    "D1_INTERNAL_ENGINEERING_KNOWLEDGE",
    "D2_SENSITIVE_ENGINEERING_DATA",
    "D3_STRICT_SECRET_DATA",
    "D4_TEMP_EXECUTION_DATA",
]


def main() -> int:
    load_dotenv()

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://chao:chao_dev_password@localhost:5432/chao",
    )

    errors: list[str] = []

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select tablename
                from pg_tables
                where schemaname = 'public'
                """
            )
            existing_tables = {row[0] for row in cur.fetchall()}

            for table in REQUIRED_TABLES:
                if table not in existing_tables:
                    errors.append(f"missing table: {table}")

            cur.execute(
                """
                select viewname
                from pg_views
                where schemaname = 'public'
                """
            )
            existing_views = {row[0] for row in cur.fetchall()}

            for view in REQUIRED_VIEWS:
                if view not in existing_views:
                    errors.append(f"missing view: {view}")

            cur.execute("select extname from pg_extension")
            existing_extensions = {row[0] for row in cur.fetchall()}

            for extension in REQUIRED_EXTENSIONS:
                if extension not in existing_extensions:
                    errors.append(f"missing extension: {extension}")

            cur.execute("select policy_name from storage_policies")
            existing_policies = {row[0] for row in cur.fetchall()}

            for policy in REQUIRED_STORAGE_POLICIES:
                if policy not in existing_policies:
                    errors.append(f"missing storage policy: {policy}")

    if errors:
        print("schema check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("schema check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
