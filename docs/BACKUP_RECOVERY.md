# Database Backup and Recovery Plan -- CloudCost

Course: CS 701 -- Special Projects in Computer Science
Project: Cloud Infrastructure Cost Optimization Platform
Date: 2026-03-27

---

## 1. Overview

This document defines the backup, recovery, and disaster recovery strategy for the CloudCost platform's data stores: PostgreSQL 15 (primary database) and Redis 7 (cache layer).

### Objectives

| Metric | Target |
|---|---|
| Recovery Point Objective (RPO) | 1 hour (maximum data loss window) |
| Recovery Time Objective (RTO) | 4 hours (maximum downtime to restore service) |
| Backup Verification | Quarterly restore test |
| Retention | 30 days for daily backups, 12 months for monthly snapshots |

---

## 2. PostgreSQL Backup Strategy

### 2.1 Logical Backups (pg_dump)

Daily full logical backups capture the entire database schema and data in a portable format.

**Schedule:** Daily at 03:00 UTC (after recommendation generation completes at 02:00 UTC)

```bash
# Full database dump (custom format for selective restore)
pg_dump \
  --host=db.cloudcost.internal \
  --port=5432 \
  --username=cloudcost \
  --dbname=cloudcost \
  --format=custom \
  --compress=9 \
  --file="/backups/cloudcost_$(date +%Y%m%d_%H%M%S).dump"
```

**Retention policy:**
- Daily backups: retained for 30 days
- Monthly snapshots (first of month): retained for 12 months
- Annual snapshots (January 1): retained indefinitely

### 2.2 Continuous Archiving (WAL)

Write-Ahead Log (WAL) archiving enables point-in-time recovery (PITR) to any moment within the retention window.

**PostgreSQL configuration (`postgresql.conf`):**

```ini
wal_level = replica
archive_mode = on
archive_command = 'az storage blob upload --account-name cloudcostbackups --container-name wal-archive --file %p --name %f --overwrite'
archive_timeout = 300   # Force archive every 5 minutes at minimum
```

This provides an RPO of approximately 5 minutes under normal operation.

### 2.3 Azure Database for PostgreSQL (Managed Service)

When deployed to Azure Database for PostgreSQL Flexible Server:

- **Automatic backups:** Azure performs daily snapshots with 7-35 day retention (configurable)
- **Geo-redundant backup storage:** Backups replicated to paired Azure region
- **Point-in-time restore:** Any second within the retention period
- **No manual configuration required:** Managed by Azure platform

### 2.4 Backup Verification

Quarterly restore tests validate backup integrity:

```bash
# Restore to a verification database
pg_restore \
  --host=verify-db.cloudcost.internal \
  --port=5432 \
  --username=cloudcost \
  --dbname=cloudcost_verify \
  --clean \
  --if-exists \
  "/backups/cloudcost_latest.dump"

# Verify row counts match production
psql -h verify-db.cloudcost.internal -U cloudcost -d cloudcost_verify \
  -c "SELECT 'users' AS tbl, COUNT(*) FROM users
      UNION ALL SELECT 'billing_records', COUNT(*) FROM billing_records
      UNION ALL SELECT 'anomalies', COUNT(*) FROM anomalies
      UNION ALL SELECT 'recommendations', COUNT(*) FROM recommendations;"
```

---

## 3. Redis Backup Strategy

Redis serves as a **cache-only** data store in CloudCost. It holds:

- Recommendation cache entries (24-hour TTL)
- Daily LLM call counters (midnight expiry)
- Job deduplication keys

**Data loss impact:** Low. All Redis data is regenerable. A full cache loss triggers:
- Recommendation cache misses on next dashboard load (re-fetched from PostgreSQL)
- LLM call counter reset (may allow extra calls on the day of failure)

### 3.1 RDB Snapshots

```ini
# redis.conf
save 900 1      # Snapshot if 1+ keys changed in 15 minutes
save 300 10     # Snapshot if 10+ keys changed in 5 minutes
save 60 10000   # Snapshot if 10,000+ keys changed in 1 minute
dbfilename dump.rdb
dir /data/redis
```

### 3.2 Cache Rebuild Procedure

Since all Redis data is derived, a full rebuild requires no restore:

1. Restart Redis with empty state
2. Recommendation cache rebuilds on next page load (cache miss -> PostgreSQL query)
3. Daily counter resets naturally at midnight UTC
4. No user-facing impact beyond slightly slower first page loads

---

## 4. Recovery Procedures

### 4.1 Full Database Restore from pg_dump

**When to use:** Complete database loss, corruption across all tables, or migration to new infrastructure.

```bash
# Step 1: Stop the API service to prevent writes during restore
az containerapp update --name cloudcost-api --resource-group cloudcost-rg \
  --min-replicas 0 --max-replicas 0

# Step 2: Drop and recreate the database
psql -h db.cloudcost.internal -U postgres \
  -c "DROP DATABASE IF EXISTS cloudcost;"
psql -h db.cloudcost.internal -U postgres \
  -c "CREATE DATABASE cloudcost OWNER cloudcost;"

# Step 3: Restore from the latest backup
pg_restore \
  --host=db.cloudcost.internal \
  --port=5432 \
  --username=cloudcost \
  --dbname=cloudcost \
  --clean \
  --if-exists \
  --no-owner \
  "/backups/cloudcost_latest.dump"

# Step 4: Verify Alembic migration state
cd backend && alembic current

# Step 5: Restart API service
az containerapp update --name cloudcost-api --resource-group cloudcost-rg \
  --min-replicas 1 --max-replicas 3
```

### 4.2 Point-in-Time Recovery (PITR)

**When to use:** Accidental data deletion or corruption at a known timestamp.

```bash
# Step 1: Identify the target recovery time
TARGET_TIME="2026-03-27 14:30:00 UTC"

# Step 2: Stop PostgreSQL
pg_ctl stop -D /var/lib/postgresql/data

# Step 3: Create recovery.signal and configure recovery target
cat > /var/lib/postgresql/data/recovery.signal <<EOF
EOF

cat >> /var/lib/postgresql/data/postgresql.auto.conf <<EOF
restore_command = 'az storage blob download --account-name cloudcostbackups --container-name wal-archive --name %f --file %p'
recovery_target_time = '${TARGET_TIME}'
recovery_target_action = 'promote'
EOF

# Step 4: Start PostgreSQL (enters recovery mode)
pg_ctl start -D /var/lib/postgresql/data

# Step 5: Verify recovery completed
psql -U cloudcost -d cloudcost -c "SELECT pg_is_in_recovery();"
# Should return 'f' (false) after promotion
```

### 4.3 Table-Level Selective Restore

**When to use:** Single table corruption or accidental truncation.

```bash
# Restore only the billing_records table from a backup
pg_restore \
  --host=db.cloudcost.internal \
  --port=5432 \
  --username=cloudcost \
  --dbname=cloudcost \
  --table=billing_records \
  --data-only \
  --clean \
  "/backups/cloudcost_latest.dump"
```

---

## 5. Disaster Recovery Runbook

### 5.1 Scenario: Database Corruption

1. Confirm corruption: `pg_amcheck --all cloudcost`
2. Identify affected tables from PostgreSQL error logs
3. If isolated to one table: use table-level selective restore (Section 4.3)
4. If widespread: perform full database restore (Section 4.1)
5. Verify Alembic migration head: `alembic current` should match `alembic heads`
6. Run smoke tests against restored database

### 5.2 Scenario: Accidental Data Deletion

1. Identify the deletion time from application logs or audit trail
2. Perform PITR to 1 minute before deletion (Section 4.2)
3. Alternatively, restore to a temporary database and selectively copy data:
   ```bash
   pg_restore --dbname=cloudcost_temp "/backups/cloudcost_latest.dump"
   # Copy missing rows
   psql -c "INSERT INTO cloudcost.billing_records
             SELECT * FROM cloudcost_temp.billing_records
             WHERE id NOT IN (SELECT id FROM cloudcost.billing_records);"
   ```

### 5.3 Scenario: Complete Infrastructure Failure

**Recovery sequence (order matters due to dependencies):**

1. **PostgreSQL** -- Provision new instance, restore from latest backup
2. **Redis** -- Provision new instance (no restore needed, cache rebuilds)
3. **Run Alembic migrations** -- `alembic upgrade head` (idempotent, safe to run on restored DB)
4. **Seed admin user** -- `python -m app.scripts.seed_admin` (idempotent)
5. **Start API service** -- FastAPI with APScheduler will resume jobs automatically
6. **Start frontend** -- Static build, no state dependency

```bash
# Full recovery script
docker compose up -d db redis          # Step 1-2: Start data stores
docker compose up migrate              # Step 3: Run migrations
docker compose up seed                 # Step 4: Seed admin
docker compose up -d api frontend      # Step 5-6: Start application
```

### 5.4 Alembic Migration State Recovery

If the `alembic_version` table is corrupted or missing:

```bash
# Check current migration state
alembic current

# If alembic_version table is missing but schema is intact:
# Stamp the database at the correct revision without running migrations
alembic stamp head

# If schema needs to be rebuilt:
alembic upgrade head
```

---

## 6. Backup Storage and Security

### 6.1 Encryption

- **At rest:** AES-256 encryption via Azure Storage Service Encryption (SSE)
- **In transit:** TLS 1.2+ for all backup transfers to Azure Blob Storage
- **Backup files:** pg_dump custom format with compression level 9

### 6.2 Storage Architecture

```
Azure Blob Storage (cloudcostbackups)
  |-- daily/              # Daily pg_dump backups (30-day retention)
  |-- monthly/            # Monthly snapshots (12-month retention)
  |-- wal-archive/        # Continuous WAL segments (7-day retention)
  |-- annual/             # Annual snapshots (indefinite retention)
```

**Geo-redundancy:** Azure GRS (Geo-Redundant Storage) replicates backups to the paired Azure region.

### 6.3 Access Controls

- Backup write access: Service principal with `Storage Blob Data Contributor` role only
- Backup read access: Limited to platform administrators and the restore service principal
- No public access to backup storage containers
- Azure AD authentication (no shared access keys)

---

## 7. Monitoring and Alerting

| Check | Frequency | Alert Condition |
|---|---|---|
| pg_dump exit code | Daily | Non-zero exit code |
| Backup file size | Daily | Size < 50% of previous day (possible truncation) |
| WAL archive lag | Every 5 minutes | Archive lag > 30 minutes |
| Backup storage utilization | Daily | > 80% of allocated storage |
| Restore test | Quarterly | Restore fails or row count mismatch > 1% |

**Alert channels:** Budget threshold and ingestion failure alerts route through the existing CloudCost notification system (email and webhook channels).

---

## 8. Summary

| Component | Backup Method | Frequency | Retention | Recovery Method |
|---|---|---|---|---|
| PostgreSQL (schema + data) | pg_dump custom format | Daily 03:00 UTC | 30 days daily, 12 months monthly | pg_restore |
| PostgreSQL (continuous) | WAL archiving | Every 5 minutes | 7 days | PITR |
| PostgreSQL (managed) | Azure automatic backup | Continuous | 7-35 days | Azure portal restore |
| Redis (cache) | RDB snapshots | Every 15 minutes | Current only | Restart (cache rebuilds) |
