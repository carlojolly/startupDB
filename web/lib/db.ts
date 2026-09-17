import path from "node:path";
import { config } from "dotenv";
import postgres from "postgres";

// The repo keeps one credential file at its root (see .env.example). Next only
// loads .env files from web/, so pull the parent one in when DATABASE_URL has
// not already been supplied by the environment or by web/.env.local.
if (!process.env.DATABASE_URL) {
  config({ path: path.join(process.cwd(), "..", ".env"), quiet: true });
}

const url = process.env.DATABASE_URL;

if (!url) {
  throw new Error(
    "DATABASE_URL is not set. Copy the repo's .env.example to .env at the " +
      "project root and paste the Supabase connection string into it.",
  );
}

// Next reloads modules on every edit in dev, which would leak a pool per edit.
const globalForSql = globalThis as unknown as { sql?: postgres.Sql };

export const sql =
  globalForSql.sql ??
  postgres(url, {
    // Supabase terminates TLS with its own CA, which is not in Node's trust
    // store. Encrypt the connection but skip chain verification, matching what
    // the Python scripts in this repo already do.
    ssl: { rejectUnauthorized: false },
    max: 5,
    idle_timeout: 20,
    prepare: false,
  });

if (process.env.NODE_ENV !== "production") globalForSql.sql = sql;
