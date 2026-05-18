"use client";

import { useState } from "react";
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
  X,
  Mail,
  MessageCircle,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", icon: LayoutDashboard, label: "Tableau de bord" },
  { href: "/exams", icon: BookOpen, label: "Examens" },
];

export function Sidebar() {
  const pathname = usePathname();
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
  const [showHelp, setShowHelp] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  function isActive(href: string) {
    const fullPath = pathname.replace(basePath, "");
    if (href === "/") return fullPath === "/" || fullPath === "";
    return fullPath.startsWith(href);
  }

  return (
    <>
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
          <button
            onClick={() => setShowHelp(true)}
            className="w-full flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors"
          >
            <HelpCircle className="h-4 w-4 text-gray-400" />
            Aide &amp; Support
          </button>
          <button
            onClick={() => setShowSettings(true)}
            className="w-full flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors"
          >
            <Settings className="h-4 w-4 text-gray-400" />
            Paramètres
          </button>
        </div>
      </aside>

      {/* Help Modal */}
      {showHelp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={() => setShowHelp(false)}>
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50">
                  <HelpCircle className="h-5 w-5 text-indigo-600" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-gray-900">Aide &amp; Support</h2>
                  <p className="text-xs text-gray-500">Comment pouvons-nous vous aider ?</p>
                </div>
              </div>
              <button onClick={() => setShowHelp(false)} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-3">
              <a href="mailto:support@labomaths.tn" className="flex items-center gap-3 rounded-xl border border-gray-200 p-4 hover:border-indigo-200 hover:bg-indigo-50/30 transition-all">
                <Mail className="h-5 w-5 text-indigo-500" />
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-900">Contacter le support</div>
                  <div className="text-xs text-gray-500">support@labomaths.tn</div>
                </div>
                <ExternalLink className="h-4 w-4 text-gray-300" />
              </a>
              <div className="rounded-xl border border-gray-200 p-4">
                <div className="flex items-center gap-3 mb-3">
                  <MessageCircle className="h-5 w-5 text-emerald-500" />
                  <div className="text-sm font-medium text-gray-900">Guide rapide</div>
                </div>
                <ol className="space-y-2 text-xs text-gray-600 list-decimal list-inside">
                  <li>Créez un examen avec titre, niveau et session</li>
                  <li>Uploadez le sujet, corrigé et barème (PDF)</li>
                  <li>Importez les copies des élèves</li>
                  <li>L&apos;IA corrige automatiquement chaque copie</li>
                  <li>Validez les notes et consultez le bilan classe</li>
                </ol>
              </div>
            </div>
            <div className="mt-4 rounded-xl bg-gray-50 p-3 text-center">
              <p className="text-xs text-gray-500">Version 1.0 · Moteur IA GPT-4.1</p>
            </div>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={() => setShowSettings(false)}>
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100">
                  <Settings className="h-5 w-5 text-gray-600" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-gray-900">Paramètres</h2>
                  <p className="text-xs text-gray-500">Configuration de l&apos;application</p>
                </div>
              </div>
              <button onClick={() => setShowSettings(false)} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="rounded-xl border border-gray-200 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-gray-900">Correction automatique</div>
                    <div className="text-xs text-gray-500">Lancer la correction IA après upload</div>
                  </div>
                  <div className="h-6 w-10 rounded-full bg-indigo-500 p-0.5 cursor-pointer">
                    <div className="h-5 w-5 rounded-full bg-white shadow-sm translate-x-4" />
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-gray-200 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-gray-900">Notifications</div>
                    <div className="text-xs text-gray-500">Alertes quand la correction est terminée</div>
                  </div>
                  <div className="h-6 w-10 rounded-full bg-indigo-500 p-0.5 cursor-pointer">
                    <div className="h-5 w-5 rounded-full bg-white shadow-sm translate-x-4" />
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-gray-200 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-gray-900">Modèle IA</div>
                    <div className="text-xs text-gray-500">Modèle utilisé pour la correction</div>
                  </div>
                  <span className="rounded-lg bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">GPT-4.1</span>
                </div>
              </div>
              <div className="rounded-xl border border-gray-200 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-gray-900">Langue</div>
                    <div className="text-xs text-gray-500">Langue de l&apos;interface</div>
                  </div>
                  <span className="rounded-lg bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">Français</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
