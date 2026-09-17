"use client";

import { useCallback, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { withParams } from "@/lib/search-params";
import { useReportPending } from "./pending";

/**
 * Filter state lives in the URL: it is shareable, survives a refresh, and the
 * back button works. Every control goes through this hook, which patches the
 * query string and lets the server component re-render.
 */
export function useQueryNav() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();
  useReportPending(pending);

  const patch = useCallback(
    (values: Record<string, string | null>) => {
      const url = pathname + withParams(params, values);
      startTransition(() => router.replace(url, { scroll: false }));
    },
    [pathname, params, router],
  );

  /** Adds or removes one value from a comma-separated facet. */
  const toggle = useCallback(
    (key: string, value: string) => {
      const current = (params.get(key) ?? "").split(",").filter(Boolean);
      const next = current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value];
      patch({ [key]: next.join(",") || null });
    },
    [params, patch],
  );

  return { params, patch, toggle, pending };
}
