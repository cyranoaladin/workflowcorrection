import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "Math Correction MVP",
  description: "MVP de correction assistée (upload + pages)"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <div className="border-b bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <Link href="/" className="font-semibold">
              Math Correction MVP
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link className="text-slate-700 hover:text-slate-900" href="/exams">
                Exams
              </Link>
            </nav>
          </div>
        </div>
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}

