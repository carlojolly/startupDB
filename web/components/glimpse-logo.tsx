import Image from "next/image";

/** Scalable Glint artwork paired with the approved geometric wordmark. */
export function GlimpseLogo({ className = "" }: { className?: string }) {
  return (
    <span aria-label="Glimpse" className={`inline-flex items-center gap-2.5 text-white ${className}`}>
      <Image src="/glimpse-mark.svg" alt="" width={29} height={30} aria-hidden />
      <span aria-hidden className="glimpse-wordmark text-[34px] leading-none">glimpse</span>
    </span>
  );
}
