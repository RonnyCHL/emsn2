#!/usr/bin/env python3
"""
EMSN Database Permissies - Automatisch Herstel

Zorgt dat alle database users de juiste rechten hebben.
Draait dagelijks via timer of na migraties.

Voorkomt "permission denied" errors na tabel recreaties.
"""

import sys
from pathlib import Path

import psycopg2

# Voeg project root toe voor imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import get_postgres_config


def get_superuser_config() -> dict:
    """Haal superuser credentials op (postgres user)."""
    config = get_postgres_config()
    # Override user naar postgres voor GRANT statements
    config['user'] = 'postgres'
    return config

# Permissie definities per user
USER_PERMISSIONS = {
    'birdpi_zolder': {
        'tables': 'ALL',
        'sequences': 'ALL',
        'description': 'Pi Zolder - full access'
    },
    'birdpi_berging': {
        'tables': 'SELECT, INSERT, UPDATE',
        'sequences': 'USAGE, SELECT',
        'description': 'Pi Berging - read + write detecties'
    },
    'meteopi': {
        'tables': 'SELECT, INSERT, UPDATE',
        'sequences': 'USAGE, SELECT',
        'description': 'Pi Meteo - read + write weather'
    },
    'emsn_readonly': {
        'tables': 'SELECT',
        'sequences': 'SELECT',
        'description': 'Grafana - read only'
    },
    'emsn_admin': {
        'tables': 'ALL',
        'sequences': 'ALL',
        'description': 'Admin tools - full access'
    }
}


def ensure_permissions(verbose: bool = False) -> dict:
    """Herstel alle database permissies."""
    stats = {'users_updated': 0, 'errors': []}

    conn = psycopg2.connect(**get_superuser_config())
    conn.autocommit = True
    cur = conn.cursor()

    try:
        for user, perms in USER_PERMISSIONS.items():
            if verbose:
                print(f"[{user}] {perms['description']}")

            try:
                # Check of user bestaat
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
                if not cur.fetchone():
                    if verbose:
                        print(f"  SKIP: user bestaat niet")
                    continue

                # Grant op bestaande tabellen
                if perms['tables'] == 'ALL':
                    cur.execute(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {user}")
                else:
                    cur.execute(f"GRANT {perms['tables']} ON ALL TABLES IN SCHEMA public TO {user}")

                # Grant op bestaande sequences
                if perms['sequences'] == 'ALL':
                    cur.execute(f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {user}")
                else:
                    cur.execute(f"GRANT {perms['sequences']} ON ALL SEQUENCES IN SCHEMA public TO {user}")

                # Default privileges voor toekomstige tabellen
                if perms['tables'] == 'ALL':
                    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {user}")
                else:
                    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT {perms['tables']} ON TABLES TO {user}")

                if perms['sequences'] == 'ALL':
                    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {user}")
                else:
                    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT {perms['sequences']} ON SEQUENCES TO {user}")

                stats['users_updated'] += 1
                if verbose:
                    print(f"  OK: permissies ingesteld")

            except Exception as e:
                error_msg = f"{user}: {e}"
                stats['errors'].append(error_msg)
                if verbose:
                    print(f"  ERROR: {e}")

    finally:
        cur.close()
        conn.close()

    return stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='EMSN Database Permissies Herstel')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Geen output')
    args = parser.parse_args()

    if not args.quiet:
        print("EMSN Database Permissies Check")
        print("=" * 40)

    stats = ensure_permissions(verbose=args.verbose and not args.quiet)

    if not args.quiet:
        print()
        print(f"Users bijgewerkt: {stats['users_updated']}")
        if stats['errors']:
            print(f"Errors: {len(stats['errors'])}")
            for err in stats['errors']:
                print(f"  - {err}")
        else:
            print("Geen errors - alle permissies OK")


if __name__ == '__main__':
    main()
