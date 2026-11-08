import type { Metadata } from "next";
import { JetBrains_Mono, Source_Sans_3, Urbanist } from "next/font/google";
import "./globals.css";

/**
 * UI body for the Operate/Read directory. Source Sans 3 avoids Inter defaults;
 * Urbanist stays the brand/display face tied to the Glimpse wordmark;
 * JetBrains Mono is reserved for survey codes (C.F., run ids), not headlines.
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

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
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
      className={`${sourceSans.variable} ${urbanist.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-page text-ink">{children}</body>
    </html>
  );
}
