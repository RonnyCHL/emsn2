---
name: fix-db-permissions
description: Herstel database permissies voor EMSN tabellen. Gebruik na tabel recreatie of bij permission denied errors.
allowed-tools: Bash
---

# Database Permissies Fix

## Wanneer Gebruiken

- Na "permission denied for table" errors
- Na database migraties/recreaties
- Na nieuwe tabel creaties
- Periodieke check

## Quick Fix - Alle EMSN Tabellen

```bash
PGPASSWORD=IwnadBon2iN psql -h 192.168.1.25 -p 5433 -U postgres -d emsn << 'EOF'
-- Geef birdpi_zolder rechten op alle EMSN tabellen
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO birdpi_zolder;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO birdpi_zolder;

-- Geef birdpi_berging leesrechten
GRANT SELECT ON ALL TABLES IN SCHEMA public TO birdpi_berging;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO birdpi_berging;

-- Geef meteopi leesrechten
GRANT SELECT ON ALL TABLES IN SCHEMA public TO meteopi;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO meteopi;

-- Readonly user
GRANT SELECT ON ALL TABLES IN SCHEMA public TO emsn_readonly;

-- Admin user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO emsn_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO emsn_admin;

-- Default privileges voor toekomstige tabellen
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO birdpi_zolder;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO birdpi_zolder;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO birdpi_berging;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO meteopi;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO emsn_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO emsn_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO emsn_admin;

SELECT 'Permissies hersteld!' as status;
EOF
```

## Check Huidige Permissies

```bash
PGPASSWORD=IwnadBon2iN psql -h 192.168.1.25 -p 5433 -U postgres -d emsn -c "
SELECT relname as tabel, relacl as permissies
FROM pg_class
WHERE relname LIKE 'nestbox%' OR relname LIKE 'bird%' OR relname LIKE 'weather%'
ORDER BY relname;"
```

## Database Users Overzicht

| User | Rol | Gebruikt door |
|------|-----|---------------|
| postgres | Superuser | Migraties, admin |
| birdpi_zolder | Full access | Pi Zolder scripts |
| birdpi_berging | Read + write detecties | Pi Berging scripts |
| meteopi | Read + write weather | Pi Meteo scripts |
| emsn_readonly | Read only | Grafana dashboards |
| emsn_admin | Full access | Admin tools |
