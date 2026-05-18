"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  BookOpen,
  GraduationCap,
  Settings,
  Sparkles,
  HelpCircle,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", icon: LayoutDashboard, label: "Tableau de bord" },
  { href: "/exams", icon: BookOpen, label: "Examens" },
];

const secondaryItems = [
  { href: "#", icon: HelpCircle, label: "Aide & Support" },
  { href: "#", icon: Settings, label: "Paramètres" },
];

export function Sidebar() {
  const pathname = usePathname();
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

  function isActive(href: string) {
    const fullPath = pathname.replace(basePath, "");
    if (href === "/") return fullPath === "/" || fullPath === "";
    return fullPath.startsWith(href);
  }

  return (
    <aside className="hidden lg:flex w-[260px] flex-col border-r border-gray-200/80 bg-white">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-6 border-b border-gray-100">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 shadow-md shadow-indigo-200">
          <GraduationCap className="h-5 w-5 text-white" />
        </div>
        <div>
          <span className="text-base font-bold text-gray-900 tracking-tight">LaboCorriger</span>
          <div className="flex items-center gap-1">
            <Sparkles className="h-3 w-3 text-indigo-500" />
            <span className="text-2xs text-gray-500 font-medium">Correction IA</span>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <div className="px-3 pb-2">
          <span className="text-2xs font-semibold text-gray-400 uppercase tracking-widest">Menu principal</span>
        </div>
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150",
              isActive(item.href)
                ? "bg-indigo-50 text-indigo-700 shadow-sm shadow-indigo-100"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
            )}
          >
            <item.icon className={cn("h-[18px] w-[18px]", isActive(item.href) ? "text-indigo-600" : "text-gray-400")} />
            {item.label}
            {isActive(item.href) && (
              <div className="ml-auto h-1.5 w-1.5 rounded-full bg-indigo-500" />
            )}
          </Link>
        ))}
      </nav>

      {/* Stats mini */}
      <div className="mx-3 mb-3 rounded-xl bg-gradient-to-br from-indigo-50 to-violet-50 p-4 border border-indigo-100">
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 className="h-4 w-4 text-indigo-600" />
          <span className="text-xs font-semibold text-indigo-900">IA Active</span>
        </div>
        <p className="text-2xs text-indigo-700/80 leading-relaxed">
          Correction automatique disponible avec GPT-4.1
        </p>
        <div className="mt-2 flex items-center gap-1.5">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-2xs font-medium text-emerald-700">Système opérationnel</span>
        </div>
      </div>

      {/* Secondary nav */}
      <div className="border-t border-gray-100 px-3 py-3 space-y-0.5">
        {secondaryItems.map((item) => (
          <Link
            key={item.label}
            href={item.href}
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors"
          >
            <item.icon className="h-4 w-4 text-gray-400" />
            {item.label}
          </Link>
        ))}
      </div>
    </aside>
  );
}
