import type { Metadata } from "next";
import { Source_Sans_3, Urbanist } from "next/font/google";
import "./globals.css";

/**
 * UI body face for this Operate/Read directory: Source Sans 3 keeps dense
 * company rows readable without Inter (anti.inter-everywhere) or other
 * over-used "expressive" defaults Impeccable flags for brand faces.
 */
const sourceSans = Source_Sans_3({
  variable: "--font-source-sans",
  subsets: ["latin"],
  display: "swap",
});

const urbanist = Urbanist({
  variable: "--font-urbanist",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Glimpse — Discover Italian startups",
  description:
    "Search and filter the Italian innovative-startup registry by sector, product type, customer model and VC relevance.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${sourceSans.variable} ${urbanist.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-page text-ink">{children}</body>
    </html>
  );
}
