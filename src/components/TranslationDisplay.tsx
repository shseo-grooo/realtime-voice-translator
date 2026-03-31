"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

interface TranslationDisplayProps {
  finalTranscript: string;
  interimTranscript: string;
  translatedText: string;
  streamingText: string;
  isTranslating: boolean;
  pendingCount: number;
}

export function TranslationDisplay({
  finalTranscript,
  interimTranscript,
  translatedText,
  streamingText,
  isTranslating,
  pendingCount,
}: TranslationDisplayProps) {
  const originalEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Local editable copy of the translation.
  // We append only newly committed content to preserve user edits.
  const [editableText, setEditableText] = useState("");
  const prevTranslatedRef = useRef("");

  useEffect(() => {
    originalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [finalTranscript, interimTranscript]);

  useEffect(() => {
    const prev = prevTranslatedRef.current;

    if (translatedText === "") {
      // Reset (language change or clear)
      setEditableText("");
    } else if (translatedText.startsWith(prev) && translatedText.length > prev.length) {
      // New segment appended — add only the new part to preserve user edits
      const newPart = translatedText.slice(prev.length);
      setEditableText((cur) => cur + newPart);
    } else {
      // Full replacement (shouldn't normally happen)
      setEditableText(translatedText);
    }

    prevTranslatedRef.current = translatedText;
  }, [translatedText]);

  // Auto-scroll textarea to bottom when content grows
  useEffect(() => {
    const el = textareaRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [editableText, streamingText]);

  const isEmpty = !finalTranscript && !interimTranscript && !translatedText && !streamingText;

  return (
    <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-6 pb-28 grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Original text panel */}
      <div className="flex flex-col rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="px-4 py-2 border-b border-gray-100 text-xs font-medium text-gray-400 uppercase tracking-wider">
          Original
        </div>
        <div className="flex-1 p-4 text-base leading-relaxed min-h-48 overflow-y-auto">
          {isEmpty ? (
            <p className="text-gray-300 select-none">마이크 버튼을 눌러 시작하세요</p>
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
          <div className="flex items-center gap-2">
            {pendingCount > 0 && (
              <span className="text-xs text-gray-400">{pendingCount} 대기</span>
            )}
            {isTranslating && (
              <Loader2 className="w-3 h-3 text-gray-400 animate-spin" />
            )}
          </div>
        </div>

        <div className="flex flex-col flex-1 min-h-48">
          {isEmpty ? (
            <p className="p-4 text-base text-gray-300 select-none">번역이 여기 표시됩니다</p>
          ) : (
            <>
              <textarea
                ref={textareaRef}
                value={editableText}
                onChange={(e) => setEditableText(e.target.value)}
                className="flex-1 p-4 text-base text-gray-800 leading-relaxed resize-none focus:outline-none min-h-36 bg-transparent"
                spellCheck={false}
              />
              {streamingText && (
                <p className="px-4 pb-3 text-base text-gray-400 leading-relaxed whitespace-pre-wrap border-t border-gray-50">
                  {streamingText}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
