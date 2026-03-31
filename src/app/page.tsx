"use client";

import { useCallback, useRef, useState } from "react";
import { Header } from "@/components/Header";
import { TranslationDisplay } from "@/components/TranslationDisplay";
import { MicButton } from "@/components/MicButton";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useTranslation } from "@/hooks/useTranslation";
import { getLanguageByCode } from "@/lib/languages";

// Split text on sentence-ending punctuation, keeping the delimiter attached.
// e.g. "Hello world. How are you? Fine" → ["Hello world.", "How are you?", "Fine"]
function splitBySentence(text: string): string[] {
  const results: string[] = [];
  const regex = /[^.!?。！？\n]*[.!?。！？\n]+/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    const s = match[0].trim();
    if (s) results.push(s);
    lastIndex = regex.lastIndex;
  }
  const remainder = text.slice(lastIndex).trim();
  if (remainder) results.push(remainder);
  return results;
}

export default function Home() {
  const [sourceLang, setSourceLang] = useState("ko");
  const [targetLang, setTargetLang] = useState("en");
  // Buffer for incomplete sentences (no ending punctuation yet)
  const sentenceBufferRef = useRef("");

  const sourceBcp47 = getLanguageByCode(sourceLang)?.bcp47 ?? "ko-KR";

  const {
    isListening,
    isSupported,
    interimTranscript,
    finalTranscript,
    error: speechError,
    startListening,
    stopListening,
    clearTranscripts,
  } = useSpeechRecognition(sourceBcp47);

  const {
    translatedText,
    streamingText,
    isTranslating,
    pendingCount,
    error: translateError,
    translate,
    clearTranslation,
  } = useTranslation();

  const handleMicToggle = useCallback(() => {
    if (isListening) {
      // Flush any remaining buffered text before stopping
      const remaining = sentenceBufferRef.current.trim();
      if (remaining) {
        translate(remaining, sourceLang, targetLang);
        sentenceBufferRef.current = "";
      }
      stopListening();
    } else {
      sentenceBufferRef.current = "";
      startListening((finalText) => {
        // Combine with previous incomplete sentence
        const combined = sentenceBufferRef.current
          ? sentenceBufferRef.current + " " + finalText
          : finalText;

        const parts = splitBySentence(combined);
        const lastPart = parts[parts.length - 1] ?? "";

        // Check if the last part ends with punctuation (complete sentence)
        const lastIsComplete = /[.!?。！？\n]$/.test(lastPart);

        if (lastIsComplete) {
          // All parts are complete — translate them all, clear buffer
          parts.forEach((s) => translate(s, sourceLang, targetLang));
          sentenceBufferRef.current = "";
        } else {
          // Translate all complete sentences, buffer the last incomplete one
          parts.slice(0, -1).forEach((s) => translate(s, sourceLang, targetLang));
          sentenceBufferRef.current = lastPart;
        }
      });
    }
  }, [isListening, startListening, stopListening, translate, sourceLang, targetLang]);

  const handleSourceChange = useCallback(
    (code: string) => {
      setSourceLang(code);
      sentenceBufferRef.current = "";
      if (isListening) stopListening();
      clearTranscripts();
      clearTranslation();
    },
    [isListening, stopListening, clearTranscripts, clearTranslation]
  );

  const handleTargetChange = useCallback(
    (code: string) => {
      setTargetLang(code);
      clearTranslation();
    },
    [clearTranslation]
  );

  const error = speechError || translateError;

  return (
    <div className="flex flex-col min-h-screen">
      <Header
        sourceLang={sourceLang}
        targetLang={targetLang}
        onSourceChange={handleSourceChange}
        onTargetChange={handleTargetChange}
      />

      {error && (
        <div className="max-w-4xl mx-auto w-full px-4 pt-4">
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">
            {error}
          </div>
        </div>
      )}

      <TranslationDisplay
        finalTranscript={finalTranscript}
        interimTranscript={interimTranscript}
        translatedText={translatedText}
        streamingText={streamingText}
        isTranslating={isTranslating}
        pendingCount={pendingCount}
      />

      <MicButton
        isListening={isListening}
        isSupported={isSupported}
        onClick={handleMicToggle}
      />
    </div>
  );
}
