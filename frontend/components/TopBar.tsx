"use client";

import { useState, useRef, useEffect } from "react";
import { Bell, Search, User, CheckCircle2, Sparkles, X } from "lucide-react";
import { ApiHealthBadge } from "@/components/ApiHealthBadge";

const notifications = [
  { id: 1, title: "Correction terminée", desc: "audit-test-exam — 2 copies corrigées", time: "Il y a 5 min", read: false, icon: Sparkles, color: "text-indigo-500 bg-indigo-50" },
  { id: 2, title: "Système opérationnel", desc: "Tous les services sont actifs", time: "Il y a 1h", read: true, icon: CheckCircle2, color: "text-emerald-500 bg-emerald-50" },
];

export function TopBar() {
  const [showNotifs, setShowNotifs] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifs(false);
      }
    }
    if (showNotifs) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showNotifs]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-200/80 bg-white/80 backdrop-blur-md px-6">
      {/* Search */}
      <div className="relative w-full max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Rechercher un examen, un élève…"
          className="w-full rounded-lg border border-gray-200 bg-gray-50/80 py-2 pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-indigo-300 focus:bg-white focus:ring-2 focus:ring-indigo-100 focus:outline-none transition-all"
        />
        <kbd className="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-gray-200 bg-gray-100 px-1.5 py-0.5 text-2xs text-gray-400 font-mono hidden sm:inline">
          ⌘K
        </kbd>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-3 ml-4">
        <ApiHealthBadge />

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setShowNotifs(!showNotifs)}
            className="relative rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-indigo-500 ring-2 ring-white" />
            )}
          </button>

          {showNotifs && (
            <div className="fixed top-[72px] right-[80px] w-80 rounded-xl border border-gray-200 bg-white shadow-xl z-[9999] overflow-hidden">
              <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
                <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
                <button onClick={() => setShowNotifs(false)} className="rounded p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="p-6 text-center text-sm text-gray-400">Aucune notification</div>
                ) : (
                  notifications.map((n) => (
                    <div key={n.id} className={`flex items-start gap-3 px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ${!n.read ? "bg-indigo-50/30" : ""}`}>
                      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${n.color}`}>
                        <n.icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">{n.title}</div>
                        <div className="text-xs text-gray-500 truncate">{n.desc}</div>
                        <div className="text-2xs text-gray-400 mt-0.5">{n.time}</div>
                      </div>
                      {!n.read && <div className="mt-2 h-2 w-2 shrink-0 rounded-full bg-indigo-500" />}
                    </div>
                  ))
                )}
              </div>
              <div className="border-t border-gray-100 px-4 py-2.5 text-center">
                <button className="text-xs font-medium text-indigo-600 hover:text-indigo-700 transition-colors">
                  Tout marquer comme lu
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="h-6 w-px bg-gray-200" />

        <button className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-gray-100 transition-colors">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 shadow-sm">
            <User className="h-4 w-4 text-white" />
          </div>
          <div className="hidden sm:block text-left">
            <div className="text-sm font-semibold text-gray-800">Admin</div>
            <div className="text-2xs text-gray-500">Enseignant</div>
          </div>
        </button>
      </div>
    </header>
  );
}
