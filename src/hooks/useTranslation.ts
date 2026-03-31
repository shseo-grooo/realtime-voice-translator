"use client";

import { useCallback, useRef, useState } from "react";
import { TranslationState } from "@/types";

interface QueueItem {
  text: string;
  sourceLang: string;
  targetLang: string;
}

export function useTranslation() {
  const [state, setState] = useState<TranslationState>({
    translatedText: "",
    streamingText: "",
    isTranslating: false,
    error: null,
  });

  const [pendingCount, setPendingCount] = useState(0);

  const queueRef = useRef<QueueItem[]>([]);
  const isProcessingRef = useRef(false);
  // Only used to abort the current request on clearTranslation
  const abortControllerRef = useRef<AbortController | null>(null);

  const processQueue = useCallback(async () => {
    if (isProcessingRef.current) return;
    isProcessingRef.current = true;

    while (queueRef.current.length > 0) {
      const item = queueRef.current.shift()!;
      setPendingCount(queueRef.current.length);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      setState((prev) => ({ ...prev, isTranslating: true, streamingText: "", error: null }));

      try {
        const response = await fetch("/api/translate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(item),
          signal: controller.signal,
        });

        if (!response.ok) throw new Error(`Translation failed: ${response.statusText}`);

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

        const trimmed = accumulated.trim();
        if (trimmed) {
          setState((prev) => ({
            ...prev,
            translatedText: prev.translatedText
              ? prev.translatedText + "\n" + trimmed
              : trimmed,
            streamingText: "",
          }));
        } else {
          setState((prev) => ({ ...prev, streamingText: "" }));
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") break; // clearTranslation called
        setState((prev) => ({
          ...prev,
          streamingText: "",
          error: (err as Error).message,
        }));
      }
    }

    setState((prev) => ({ ...prev, isTranslating: false }));
    setPendingCount(0);
    isProcessingRef.current = false;
  }, []);

  const translate = useCallback(
    (text: string, sourceLang: string, targetLang: string) => {
      if (!text.trim()) return;
      queueRef.current.push({ text, sourceLang, targetLang });
      setPendingCount(queueRef.current.length);
      processQueue();
    },
    [processQueue]
  );

  const clearTranslation = useCallback(() => {
    queueRef.current = [];
    abortControllerRef.current?.abort();
    isProcessingRef.current = false;
    setPendingCount(0);
    setState({ translatedText: "", streamingText: "", isTranslating: false, error: null });
  }, []);

  return { ...state, pendingCount, translate, clearTranslation };
}
