import type { Metadata } from "next";
import Header from "@/components/Header";
import "./globals.css";

export const metadata: Metadata = {
  title: "Healthtech Startup Dashboard",
  description:
    "A human-reviewed repository of newly funded and newly surfaced US healthcare-technology startups.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1">{children}</main>
        <footer
          className="flex flex-col items-center justify-center gap-2 border-t px-4 py-6 text-center text-sm sm:flex-row sm:gap-4"
          style={{ borderColor: "var(--color-border)", color: "var(--color-text-muted)" }}
        >
          <span>Data from public SEC filings &amp; trade press · MIT licensed</span>
          <a href="/methodology" style={{ color: "var(--color-text-muted)" }}>
            Methodology
          </a>
        </footer>
      </body>
    </html>
  );
}
