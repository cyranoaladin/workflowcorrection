"use client";

import { Bell, Search, User } from "lucide-react";
import { ApiHealthBadge } from "@/components/ApiHealthBadge";

export function TopBar() {
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

        <button className="relative rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-indigo-500 ring-2 ring-white" />
        </button>

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
