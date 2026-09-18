"use client";

import { usePathname } from "next/navigation";
import { useActionState, useEffect, useRef, useState } from "react";
import { submitFeedback } from "@/app/actions";
import { MAX_FEEDBACK, type FeedbackState } from "@/lib/model";

const IDLE: FeedbackState = { status: "idle" };

export type FeedbackCompany = { name: string; codiceFiscale: string };

function SpeechIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 14 14"
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
    >
      <path
        d="M2.5 3.5h9a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H6l-2.5 2v-2h-1a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1Z"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * The panel is a separate component so that closing it unmounts the action
 * state: a note that was sent never greets the next person who opens the box.
 */
function Panel({
  company,
  page,
  onDone,
}: {
  company?: FeedbackCompany;
  page: string;
  onDone: () => void;
}) {
  const [state, action, pending] = useActionState(submitFeedback, IDLE);
  // Controlled, so that a send which fails hands the note back rather than
  // making someone who already wrote it write it again.
  const [text, setText] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    box.current?.focus();
  }, []);

  // A confirmation nobody has to dismiss. Long enough to read, short enough
  // that the header does not keep a panel open over the results.
  useEffect(() => {
    if (state.status !== "sent") return;
    const timer = setTimeout(onDone, 1800);
    return () => clearTimeout(timer);
  }, [state.status, onDone]);

  if (state.status === "sent") {
    return (
      <p className="flex items-center gap-2 px-4 py-6 text-[13px] text-ink">
        <svg
          aria-hidden
          viewBox="0 0 14 14"
          className="h-4 w-4 text-brand"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
        >
          <path d="m3 7.5 3 3 5-7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Thanks, that is saved.
      </p>
    );
  }

  return (
    <form action={action} className="p-4">
      <input type="hidden" name="page" value={page} />
      {company ? (
        <input type="hidden" name="company" value={company.codiceFiscale} />
      ) : null}

      <label htmlFor="feedback-message" className="text-[13px] font-medium">
        {company ? `Feedback on ${company.name}` : "Feedback"}
      </label>
      <p className="mt-1 text-2xs leading-relaxed text-ink-muted">
        {company
          ? "A wrong label, a missing company, anything that looks off."
          : "What is missing, wrong, or hard to use? It reaches the person who builds this."}
      </p>

      <textarea
        ref={box}
        id="feedback-message"
        name="message"
        rows={4}
        maxLength={MAX_FEEDBACK}
        required
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={
          company
            ? "e.g. this is a B2C marketplace, not B2B software."
            : "e.g. I need to filter by region and sector at once."
        }
        className="mt-2.5 w-full resize-y rounded-lg border border-line bg-page px-3 py-2 text-[13px] leading-relaxed placeholder:text-ink-faint focus:border-brand focus:outline-none"
      />

      {state.status === "error" ? (
        <p role="alert" className="mt-2 text-2xs text-[#9b3448]">
          {state.error}
        </p>
      ) : null}

      <div className="mt-3 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onDone}
          className="h-8 rounded-lg px-3 text-[13px] text-ink-muted transition-colors hover:text-ink"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={pending}
          className="h-8 rounded-lg bg-brand px-3.5 text-[13px] font-semibold text-white transition-colors hover:bg-brand-bright disabled:opacity-60"
        >
          {pending ? "Sending…" : "Send"}
        </button>
      </div>
    </form>
  );
}

/**
 * Feedback from a reader who has no account and no reason to write an email:
 * a box in the header that writes one row and closes.
 */
export function Feedback({ company }: { company?: FeedbackCompany }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    function onClick(event: MouseEvent) {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  return (
    <div ref={wrap} className="relative ml-auto">
      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        aria-expanded={open}
        className={`inline-flex h-8 items-center gap-2 rounded-full border px-3 text-[12px] font-medium transition-colors ${
          open
            ? "border-on-navy-faint bg-panel-raised text-on-navy"
            : "border-panel-line bg-panel text-on-navy-muted hover:border-on-navy-faint hover:text-on-navy"
        }`}
      >
        <SpeechIcon />
        Feedback
      </button>

      {open ? (
        <div className="on-light absolute top-full right-0 z-50 mt-2 w-[min(21rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-line bg-page text-ink shadow-[0_12px_32px_rgb(3_16_26/0.28)]">
          <Panel
            company={company}
            page={pathname}
            onDone={() => setOpen(false)}
          />
        </div>
      ) : null}
    </div>
  );
}
