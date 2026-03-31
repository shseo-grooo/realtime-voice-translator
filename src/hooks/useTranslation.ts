"use client";

import { useCallback, useRef, useState } from "react";
import { TranslationState } from "@/types";

export function useTranslation() {
  const [state, setState] = useState<TranslationState>({
    translatedText: "",
    isTranslating: false,
    error: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const translate = useCallback(
    (text: string, sourceLang: string, targetLang: string) => {
      if (!text.trim()) return;

      // Cancel previous debounce
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(async () => {
        // Abort previous in-flight request
        abortControllerRef.current?.abort();
        const controller = new AbortController();
        abortControllerRef.current = controller;

        setState((prev) => ({ ...prev, isTranslating: true, error: null }));

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

          // Read streaming response
          const reader = response.body?.getReader();
          if (!reader) throw new Error("No response body");

          const decoder = new TextDecoder();
          let chunk = "";

          // Append a newline separator between segments
          setState((prev) => ({
            ...prev,
            translatedText: prev.translatedText
              ? prev.translatedText + "\n"
              : "",
          }));

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            chunk = decoder.decode(value, { stream: true });
            setState((prev) => ({
              ...prev,
              translatedText: prev.translatedText + chunk,
            }));
          }

          setState((prev) => ({ ...prev, isTranslating: false }));
        } catch (err) {
          if ((err as Error).name === "AbortError") return;
          setState((prev) => ({
            ...prev,
            isTranslating: false,
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
    setState({ translatedText: "", isTranslating: false, error: null });
  }, []);

  return { ...state, translate, clearTranslation };
}
