import "server-only";
import { sql } from "./db";

/**
 * The one write the dashboard performs.
 *
 * Kept out of lib/companies.ts because nothing here reads a company: it is the
 * same server-only rule (the connection string never reaches the browser), a
 * different subject.
 */
export async function saveFeedback(note: {
  message: string;
  page: string | null;
  codiceFiscale: string | null;
}): Promise<void> {
  // run_id is read here rather than passed in: the labels a reader is judging
  // belong to whichever run is published at the moment they write, and the
  // client has no business asserting which one that was.
  await sql`
    INSERT INTO feedback (message, page, codice_fiscale, run_id)
    VALUES (
      ${note.message},
      ${note.page},
      ${note.codiceFiscale},
      (SELECT run_id FROM published_run WHERE id = 1)
    )
  `;
}
