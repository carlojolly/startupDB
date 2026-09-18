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
  // belong to whichever run they were shown, and the client has no business
  // asserting which one that was.
  //
  // Read from current_company_tags, the same view the dashboard reads, rather
  // than from published_run directly — that is the definition of "the run on
  // screen", and it holds whether or not sql/007 has been applied to the
  // database this connects to. LIMIT 1 rides company_tags_run_idx.
  await sql`
    INSERT INTO feedback (message, page, codice_fiscale, run_id)
    VALUES (
      ${note.message},
      ${note.page},
      ${note.codiceFiscale},
      (SELECT run_id FROM current_company_tags LIMIT 1)
    )
  `;
}
