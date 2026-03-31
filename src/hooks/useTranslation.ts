"use client";

import { useCallback, useRef, useState } from "react";
import { TranslationState } from "@/types";

export function useTranslation() {
  const [state, setState] = useState<TranslationState>({
    translatedText: "",
    streamingText: "",
    isTranslating: false,
    error: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const translate = useCallback(
    (text: string, sourceLang: string, targetLang: string) => {
      if (!text.trim()) return;

      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(async () => {
        abortControllerRef.current?.abort();
        const controller = new AbortController();
        abortControllerRef.current = controller;

        setState((prev) => ({
          ...prev,
          isTranslating: true,
          streamingText: "",
          error: null,
        }));

        try {
          const response = await fetch("/api/translate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, sourceLang, targetLang }),
            signal: controller.signal,
          });

          if (!response.ok) {
            throw new Error(`Translation failed: ${response.statusText}`);
          }

          const reader = response.body?.getReader();
          if (!reader) throw new Error("No response body");

          const decoder = new TextDecoder();
          let accumulated = "";

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            accumulated += chunk;
            setState((prev) => ({ ...prev, streamingText: accumulated }));
          }

          // Commit trimmed result to translatedText, clear streamingText
          const trimmed = accumulated.trim();
          setState((prev) => ({
            ...prev,
            translatedText: prev.translatedText
              ? prev.translatedText + "\n" + trimmed
              : trimmed,
            streamingText: "",
            isTranslating: false,
          }));
        } catch (err) {
          if ((err as Error).name === "AbortError") return;
          setState((prev) => ({
            ...prev,
            isTranslating: false,
            streamingText: "",
            error: (err as Error).message,
          }));
        }
      }, 300);
    },
    []
  );

  const clearTranslation = useCallback(() => {
    abortControllerRef.current?.abort();
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    setState({ translatedText: "", streamingText: "", isTranslating: false, error: null });
  }, []);

  return { ...state, translate, clearTranslation };
}
