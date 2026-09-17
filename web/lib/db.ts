import path from "node:path";
import { config } from "dotenv";
import postgres from "postgres";

function databaseUrl(): string {
  // The repo keeps one credential file at its root (see .env.example). Next only
  // loads .env files from web/, so pull the parent one in when DATABASE_URL has
  // not already been supplied. On a hosted deploy the platform supplies it and
  // there is no file to find, so this is a no-op there.
  if (!process.env.DATABASE_URL) {
    config({ path: path.join(process.cwd(), "..", ".env"), quiet: true });
  }
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      "DATABASE_URL is not set. Locally, copy the repo's .env.example to .env " +
        "at the project root. On a hosted deploy, set it as an environment " +
        "variable — and use Supabase's pooler host, because the direct " +
        "db.<ref>.supabase.co host resolves over IPv6 only and will time out " +
        "from most hosting providers.",
    );
  }
  return url;
}

// Next reloads modules on every edit in dev, which would leak a pool per edit.
const globalForSql = globalThis as unknown as { sql?: postgres.Sql };

function open(): postgres.Sql {
  const client =
    globalForSql.sql ??
    postgres(databaseUrl(), {
      // Supabase terminates TLS with its own CA, which is not in Node's trust
      // store. Encrypt the connection but skip chain verification, matching what
      // the Python scripts in this repo already do.
      ssl: { rejectUnauthorized: false },
      max: 5,
      idle_timeout: 20,
      // Also what lets the transaction pooler (port 6543) work, since it does
      // not support prepared statements.
      prepare: false,
    });
  if (process.env.NODE_ENV !== "production") globalForSql.sql = client;
  return client;
}

let client: postgres.Sql | undefined;

/**
 * Opened on the first query, not on import.
 *
 * `next build` evaluates every route module to collect its config, so a
 * connection demanded at import time fails the build on any machine without the
 * credentials — which is every build machine. Nothing here needs the database
 * until a request actually runs a query.
 */
export const sql = ((...args: Parameters<postgres.Sql>) =>
  (client ??= open())(...args)) as unknown as postgres.Sql;
