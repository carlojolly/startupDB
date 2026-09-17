import Link from "next/link";

export default function NotFound() {
  return (
    <div className="on-navy grid-field flex min-h-dvh flex-col items-center justify-center bg-navy px-6 text-center text-on-navy">
      <p className="eyebrow text-amber">404</p>
      <h1 className="display mt-2 text-2xl">Company not found</h1>
      <p className="mt-2 max-w-sm text-sm text-on-navy-muted">
        No company with that codice fiscale is in the current tag run.
      </p>
      <Link
        href="/"
        className="mt-7 inline-flex h-10 items-center rounded-lg bg-brand-bright px-4 text-[13px] font-semibold text-white hover:bg-brand"
      >
        Back to all companies
      </Link>
    </div>
  );
}
