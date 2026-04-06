"use client";

import { LANGUAGES } from "@/lib/languages";
import { ArrowRight } from "lucide-react";

interface HeaderProps {
  sourceLang: string;
  targetLang: string;
  onSourceChange: (code: string) => void;
  onTargetChange: (code: string) => void;
}

export function Header({
  sourceLang,
  targetLang,
  onSourceChange,
  onTargetChange,
}: HeaderProps) {
  return (
    <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
      <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
        <select
          value={sourceLang}
          onChange={(e) => onSourceChange(e.target.value)}
          className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-300 cursor-pointer"
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>

        <ArrowRight className="w-4 h-4 text-gray-400 shrink-0" />

        <select
          value={targetLang}
          onChange={(e) => onTargetChange(e.target.value)}
          className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-300 cursor-pointer"
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>
      </div>
    </header>
  );
}
