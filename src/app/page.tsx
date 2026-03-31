"use client";

import { useCallback, useState } from "react";
import { Header } from "@/components/Header";
import { TranslationDisplay } from "@/components/TranslationDisplay";
import { MicButton } from "@/components/MicButton";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useTranslation } from "@/hooks/useTranslation";
import { getLanguageByCode } from "@/lib/languages";

export default function Home() {
  const [sourceLang, setSourceLang] = useState("ko");
  const [targetLang, setTargetLang] = useState("en");

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
      stopListening();
    } else {
      startListening((finalText) => {
        translate(finalText, sourceLang, targetLang);
      });
    }
  }, [isListening, startListening, stopListening, translate, sourceLang, targetLang]);

  const handleSourceChange = useCallback(
    (code: string) => {
      setSourceLang(code);
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
