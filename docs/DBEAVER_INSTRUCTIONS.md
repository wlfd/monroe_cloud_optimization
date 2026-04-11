# DBeaver ERD Instructions — CloudCost Database

Step-by-step guide for connecting DBeaver to the local CloudCost PostgreSQL database and generating a Crow's Foot Entity-Relationship Diagram.

---

## 1. Prerequisites

- **DBeaver Community Edition** (free) — download from https://dbeaver.io/download/
  - Choose the installer for your OS (macOS .dmg, Windows .exe, or Linux .deb/.rpm)
  - Install and launch DBeaver before proceeding
- **Docker Desktop** must be running — the database lives inside a Docker container

---

## 2. Start the Database

Open a terminal, navigate to the project root, and start only the database container:

```bash
cd /Users/wlfd/Developer/monroe_cloud_optimization
docker compose up -d db
```

Verify the database is ready (you should see `healthy`):

```bash
docker compose ps db
```

Expected output:
```
NAME                              IMAGE         STATUS
monroe_cloud_optimization-db-1   postgres:15   Up X seconds (healthy)
```

The database is now accepting connections on `localhost:5432`.

---

## 3. Connect DBeaver to the Database

1. Open DBeaver.
2. In the top menu, click **Database** > **New Database Connection** (or press `Ctrl+Shift+N` / `Cmd+Shift+N`).
3. In the connection wizard, select **PostgreSQL** and click **Next**.
4. Fill in the connection settings exactly as shown:

   | Field    | Value           |
   |----------|-----------------|
   | Host     | `localhost`     |
   | Port     | `5432`          |
   | Database | `cloudcost`     |
   | Username | `cloudcost`     |
   | Password | `localdev`      |

5. Click **Test Connection**. If DBeaver prompts you to download the PostgreSQL JDBC driver, click **Download** and let it finish.
6. A dialog should say **"Connected"**. Click **OK**, then **Finish**.

The connection `cloudcost` will now appear in the **Database Navigator** panel on the left.

---

## 4. Generate an ERD in Crow's Foot Notation

### 4.1 Open the ER Diagram

1. In the **Database Navigator** panel, expand the connection tree:
   ```
   cloudcost
   └── Databases
       └── cloudcost
           └── Schemas
               └── public
                   └── Tables
   ```
2. Right-click **public** (the schema node, not the Tables folder).
3. Select **View Schema** (some DBeaver versions label this **ER Diagram** or **View Diagram**).

The ER Diagram editor will open in the main area. You will see all 16 tables:

`alert_events`, `allocation_rules`, `anomalies`, `billing_records`, `budget_thresholds`, `budgets`, `ingestion_alerts`, `ingestion_runs`, `notification_channels`, `notification_deliveries`, `recommendations`, `tenant_attributions`, `tenant_profiles`, `user_sessions`, `users`, `alembic_version`

### 4.2 Switch to Crow's Foot Notation

DBeaver defaults to **IDEF1X** notation. To switch to Crow's Foot:

1. With the ERD diagram tab active, look at the toolbar at the top of the diagram editor.
2. Click the **Notation** dropdown (it may show "IDEF1X" or display a small connector-style icon).
3. Select **Crow's Foot** from the list.

If you do not see a Notation dropdown in the toolbar:

- Click **View** in the top menu > **Toolbar** > ensure the ERD toolbar is enabled, or
- Right-click on an empty area of the diagram canvas > **Notation** > **Crow's Foot**

The relationship lines will update to show Crow's Foot symbols (the "many" end shows three lines fanning out like a crow's foot; the "one" end shows a single line or vertical bar).

### 4.3 Arrange the Diagram

DBeaver's auto-layout is often cluttered. Improve readability:

1. Right-click on the diagram canvas (empty area) > **Layout** > **Auto Layout** or **Arrange** to trigger an automatic layout.
2. Drag individual table boxes to group related entities — for example, group budget/threshold tables together, and tenant/user tables together.
3. Use the scroll wheel to zoom in and out, or use the zoom controls in the bottom-right corner of the diagram.

### 4.4 Export the ERD as an Image

1. With the ERD diagram tab active, click **File** > **Save ERD Diagram As Image...**  
   (Some DBeaver versions: right-click the canvas > **Save Diagram As Image**)
2. Choose **PNG** format for best quality.
3. Select a save location and click **Save**.

---

## 5. Alternative: ERD from Specific Tables Only

If you want a focused diagram covering only a subset of tables (for example, just the budgeting or user-management tables):

1. In the **Database Navigator**, expand `cloudcost > Databases > cloudcost > Schemas > public > Tables`.
2. Hold `Ctrl` (Windows/Linux) or `Cmd` (macOS) and click each table you want to include.
3. Right-click the selected tables > **View Diagram**.
4. A new ERD tab opens containing only those tables.
5. To manually add a related table later: drag it from the Database Navigator directly onto the open diagram canvas.
6. To hide a relationship line: right-click the connector line > **Hide Relation** (the foreign key still exists in the database; this only hides it visually).

---

## 6. Important Notes

- **Stop the database when you are done** to free system resources:
  ```bash
  cd /Users/wlfd/Developer/monroe_cloud_optimization
  docker compose down
  ```
  To also delete the data volume (resets the database entirely):
  ```bash
  docker compose down -v
  ```

- **The exported SQL schema** is saved at:
  ```
  docs/DB_SCHEMA.sql
  ```
  This file contains the full `CREATE TABLE` statements and foreign key constraints for all 16 tables. You can import it into another PostgreSQL instance or use it to recreate the schema without Docker:
  ```bash
  psql -U <your_pg_user> -d <target_database> -f docs/DB_SCHEMA.sql
  ```

- **DBeaver reads the live database** — it will automatically reflect any future migrations you run (`docker compose up migrate`) without needing to reconnect.

- If the **Test Connection** step fails, confirm Docker Desktop is running and the container is healthy:
  ```bash
  docker compose ps db
  ```
