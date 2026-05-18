import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";

export const metadata = {
  title: "LaboCorriger · Correction IA",
  description: "Plateforme de correction assistée par IA pour l'enseignement des mathématiques"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <head>
        <script dangerouslySetInnerHTML={{ __html: `
          if ('serviceWorker' in navigator) {
            navigator.serviceWorker.getRegistrations().then(function(regs) {
              regs.forEach(function(reg) { reg.unregister(); });
            });
            caches.keys().then(function(keys) {
              keys.forEach(function(k) { caches.delete(k); });
            });
          }
        `}} />
      </head>
      <body className="min-h-screen bg-gray-50/80">
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar */}
          <Sidebar />

          {/* Main area */}
          <div className="flex flex-1 flex-col overflow-hidden">
            <TopBar />
            <main className="flex-1 overflow-y-auto">
              <div className="mx-auto max-w-[1400px] px-6 py-8 animate-in">
                {children}
              </div>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}

