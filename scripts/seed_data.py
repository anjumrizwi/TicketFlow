"""CLI entrypoint for the seed-data skill (specs/seed-data.md, FR-SEED-04).

Usage: python scripts/seed_data.py <users> <tickets>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from common.db import get_connection, init_schema
from features.seed_data.service import SeedError, SeedGuardError, seed_demo_data


def main(argv):
    if len(argv) != 2:
        print("Usage: python scripts/seed_data.py <users> <tickets>", file=sys.stderr)
        return 2

    try:
        num_users, num_tickets = int(argv[0]), int(argv[1])
    except ValueError:
        print("<users> and <tickets> must be integers.", file=sys.stderr)
        return 2

    load_dotenv()
    conn = get_connection()
    try:
        init_schema(conn)
        summary = seed_demo_data(conn, num_users, num_tickets)
    except (SeedGuardError, SeedError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(f"Seeded {summary['users']} demo users.")
    print("Tickets by status:")
    for status, count in summary["tickets_by_status"].items():
        print(f"  {status}: {count}")
    print("To clear seeded data without recreating it, re-run with: 0 0")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
