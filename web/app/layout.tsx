import type { Metadata } from "next";
import { Inter, Urbanist } from "next/font/google";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });

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
    <html lang="en" className={`${inter.variable} ${urbanist.variable} h-full antialiased`}>
      <body className="min-h-full bg-page text-ink">{children}</body>
    </html>
  );
}
