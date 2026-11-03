"use server";

import { saveFeedback } from "@/lib/feedback";
import { exportCompanies } from "@/lib/companies";
import { companiesToCsv } from "@/lib/export-csv";
import { MAX_FEEDBACK, type FeedbackState } from "@/lib/model";
import { parseFilters, parseSort } from "@/lib/search-params";

/** Export every match in the current published run; pagination is ignored. */
export async function exportFilteredCompanies(query: string): Promise<string> {
  if (typeof query !== "string" || query.length > 4096) {
    throw new Error("The export filters are too long. Refresh and try again.");
  }
  const params = Object.fromEntries(new URLSearchParams(query));
  const companies = await exportCompanies(parseFilters(params), parseSort(params));
  return companiesToCsv(companies);
}

/**
 * Server action behind the header's feedback form. There is no API route and
 * none is needed: the browser posts to this function and the SQL stays on the
 * server.
 */
export async function submitFeedback(
  _previous: FeedbackState,
  form: FormData,
): Promise<FeedbackState> {
  const message = String(form.get("message") ?? "").trim();
  const page = String(form.get("page") ?? "").trim() || null;
  const codiceFiscale = String(form.get("company") ?? "").trim() || null;

  if (!message) {
    return { status: "error", error: "Write something first." };
  }
  if (message.length > MAX_FEEDBACK) {
    return {
      status: "error",
      error: `That is longer than ${MAX_FEEDBACK.toLocaleString("en-GB")} characters.`,
    };
  }

  try {
    await saveFeedback({ message, page, codiceFiscale });
  } catch (cause) {
    // Reported, never swallowed: the writer is told their note was not kept,
    // and the reason lands in the server log rather than in the browser.
    console.error("feedback insert failed:", cause);
    return {
      status: "error",
      error: "That did not save, so nothing was recorded. Try again in a moment.",
    };
  }
  return { status: "sent" };
}
