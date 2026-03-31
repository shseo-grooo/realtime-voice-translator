"use client";

import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";

interface TranslationDisplayProps {
  finalTranscript: string;
  interimTranscript: string;
  translatedText: string;
  isTranslating: boolean;
}

export function TranslationDisplay({
  finalTranscript,
  interimTranscript,
  translatedText,
  isTranslating,
}: TranslationDisplayProps) {
  const originalEndRef = useRef<HTMLDivElement>(null);
  const translatedEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    originalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [finalTranscript, interimTranscript]);

  useEffect(() => {
    translatedEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [translatedText]);

  const isEmpty = !finalTranscript && !interimTranscript && !translatedText;

  return (
    <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-6 pb-28 grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Original text panel */}
      <div className="flex flex-col rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="px-4 py-2 border-b border-gray-100 text-xs font-medium text-gray-400 uppercase tracking-wider">
          Original
        </div>
        <div className="flex-1 p-4 text-base leading-relaxed min-h-48 overflow-y-auto">
          {isEmpty ? (
            <p className="text-gray-300 select-none">
              마이크 버튼을 눌러 시작하세요
            </p>
          ) : (
            <>
              <span className="text-gray-800 whitespace-pre-wrap">{finalTranscript}</span>
              {interimTranscript && (
                <span className="text-gray-400">{interimTranscript}</span>
              )}
            </>
          )}
          <div ref={originalEndRef} />
        </div>
      </div>

      {/* Translation panel */}
      <div className="flex flex-col rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="px-4 py-2 border-b border-gray-100 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Translation
          </span>
          {isTranslating && (
            <Loader2 className="w-3 h-3 text-gray-400 animate-spin" />
          )}
        </div>
        <div className="flex-1 p-4 text-base leading-relaxed min-h-48 overflow-y-auto">
          {isEmpty ? (
            <p className="text-gray-300 select-none">번역이 여기 표시됩니다</p>
          ) : (
            <span className="text-gray-800 whitespace-pre-wrap">{translatedText}</span>
          )}
          <div ref={translatedEndRef} />
        </div>
      </div>
    </main>
  );
}
