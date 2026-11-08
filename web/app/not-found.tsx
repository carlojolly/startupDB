import Link from "next/link";
import { GlimpseLogo } from "@/components/glimpse-logo";

export default function NotFound() {
  return (
    <div className="atlas-field on-navy flex min-h-dvh flex-col items-center justify-center px-6 text-center text-on-navy">
      <GlimpseLogo />
      <p className="eyebrow mt-10 text-brand">404 · off the map</p>
      <h1 className="display mt-3 text-3xl sm:text-4xl">Company not found</h1>
      <p className="mt-3 max-w-sm text-sm text-on-navy-muted">
        No company with that codice fiscale is in the published tag run.
      </p>
      <Link
        href="/"
        className="mt-8 inline-flex h-12 items-center bg-brand px-5 text-[13px] font-semibold text-navy hover:bg-brand-bright"
      >
        Return to atlas
      </Link>
    </div>
  );
}
