"use client";

import { useEffect, useSyncExternalStore } from "react";

/**
 * Filter and sort changes are server round trips. The controls that start them
 * are separate components, so they report into this one small store and the
 * results area reads it back — enough to show the list is being refreshed
 * without flashing a skeleton over data that is still on screen.
 */
let count = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Call from a hook that owns a transition; mirrors its pending flag. */
export function useReportPending(pending: boolean) {
  useEffect(() => {
    if (!pending) return;
    count += 1;
    emit();
    return () => {
      count = Math.max(0, count - 1);
      emit();
    };
  }, [pending]);
}

export function usePending(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => count > 0,
    () => false,
  );
}

/** A hairline of brand blue while the next page of results is on its way. */
export function PendingBar() {
  const pending = usePending();
  return (
    <span
      aria-hidden
      className={`pointer-events-none absolute inset-x-0 bottom-0 h-[2px] origin-left bg-brand-bright transition-opacity duration-150 ${
        pending ? "opacity-100" : "opacity-0"
      }`}
    />
  );
}

/** Fades the results while they are stale, so the change is visibly in flight. */
export function PendingDim({ children }: { children: React.ReactNode }) {
  const pending = usePending();
  return (
    <div
      aria-busy={pending}
      className={`transition-opacity duration-150 ${pending ? "opacity-55" : "opacity-100"}`}
    >
      {children}
    </div>
  );
}
