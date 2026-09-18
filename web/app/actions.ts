"use server";

import { saveFeedback } from "@/lib/feedback";
import { MAX_FEEDBACK, type FeedbackState } from "@/lib/model";

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
      error: "That did not save — nothing was recorded. Try again in a moment.",
    };
  }
  return { status: "sent" };
}
