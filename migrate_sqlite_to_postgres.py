#!/usr/bin/env python3
"""
Wispr SQLite to PostgreSQL Migration Script

Usage:
  python3 migrate_sqlite_to_postgres.py --sqlite instance/team_collaboration.db --postgres postgresql://user:password@localhost:5432/wispr

- Requires: pip install psycopg2-binary sqlalchemy
"""
import argparse
import sys
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker

parser = argparse.ArgumentParser(description='Migrate Wispr data from SQLite to PostgreSQL.')
parser.add_argument('--sqlite', required=True, help='Path to SQLite DB (e.g., instance/team_collaboration.db)')
parser.add_argument('--postgres', required=True, help='PostgreSQL URI (e.g., postgresql://user:pass@localhost:5432/wispr)')
args = parser.parse_args()

print(f"Connecting to SQLite: {args.sqlite}")
sqlite_engine = create_engine(f'sqlite:///{args.sqlite}')
sqlite_meta = MetaData(bind=sqlite_engine)
sqlite_meta.reflect()

print(f"Connecting to PostgreSQL: {args.postgres}")
pg_engine = create_engine(args.postgres)
pg_meta = MetaData(bind=pg_engine)
pg_meta.reflect()

Session = sessionmaker(bind=sqlite_engine)
sqlite_session = Session()

pg_conn = pg_engine.connect()
trans = pg_conn.begin()

try:
    for table_name in sqlite_meta.tables:
        print(f"Migrating table: {table_name}")
        src_table = Table(table_name, sqlite_meta, autoload_with=sqlite_engine)
        dest_table = Table(table_name, pg_meta, autoload_with=pg_engine)
        rows = list(sqlite_session.execute(src_table.select()))
        if rows:
            pg_conn.execute(dest_table.delete())  # Clear existing data
            for row in rows:
                row_dict = dict(row._mapping)
                pg_conn.execute(dest_table.insert().values(**row_dict))
        print(f"  {len(rows)} rows migrated.")
    trans.commit()
    print("\n✅ Migration complete!")
except Exception as e:
    print(f"❌ Migration failed: {e}")
    trans.rollback()
    sys.exit(1)
finally:
    pg_conn.close()
    sqlite_session.close() 