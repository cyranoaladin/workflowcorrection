import "./globals.css";
import Link from "next/link";
import { ApiHealthBadge } from "@/components/ApiHealthBadge";

export const metadata = {
  title: "LaboCorriger · Correction IA",
  description: "Plateforme de correction assistée par IA pour l'enseignement des mathématiques"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-slate-50">
        {/* ── Topbar ─────────────────────────────────────────────── */}
        <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur-sm shadow-sm">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 sm:px-6 h-14">

            {/* Logo */}
            <Link href="/" className="flex items-center gap-2 group">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-indigo-500 shadow-sm group-hover:shadow-indigo-200 transition-shadow">
                <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              </div>
              <span className="font-bold text-slate-900 tracking-tight">LaboCorriger</span>
            </Link>

            {/* Nav */}
            <nav className="flex items-center gap-1">
              <Link
                href="/"
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
              >
                Tableau de bord
              </Link>
              <Link
                href="/exams"
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
              >
                Examens
              </Link>
            </nav>

            {/* Right side */}
            <div className="flex items-center gap-3">
              <ApiHealthBadge />
            </div>
          </div>
        </header>

        {/* ── Main content ───────────────────────────────────────── */}
        <main className="mx-auto max-w-6xl px-4 sm:px-6 py-8 animate-fade-in">
          {children}
        </main>

        {/* ── Footer ─────────────────────────────────────────────── */}
        <footer className="mt-16 border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-400">
          LaboCorriger · Correction assistée par IA · maths.labomaths.tn
        </footer>
      </body>
    </html>
  );
}

