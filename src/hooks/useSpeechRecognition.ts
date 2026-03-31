"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SpeechRecognitionState } from "@/types";

export function useSpeechRecognition(lang: string) {
  const [state, setState] = useState<SpeechRecognitionState>({
    isListening: false,
    interimTranscript: "",
    finalTranscript: "",
    error: null,
    isSupported: false,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);
  const isListeningRef = useRef(false);
  const onFinalRef = useRef<((text: string) => void) | null>(null);

  useEffect(() => {
    const supported =
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
    setState((prev) => ({ ...prev, isSupported: supported }));
  }, []);

  const initRecognition = useCallback(
    (currentLang: string) => {
      if (
        typeof window === "undefined" ||
        (!("SpeechRecognition" in window) &&
          !("webkitSpeechRecognition" in window))
      ) {
        return null;
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const SpeechRecognitionAPI: any =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new SpeechRecognitionAPI();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = currentLang;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onresult = (event: any) => {
        let interim = "";
        let final = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            final += result[0].transcript;
          } else {
            interim += result[0].transcript;
          }
        }

        if (final) {
          setState((prev) => ({
            ...prev,
            finalTranscript: prev.finalTranscript
              ? prev.finalTranscript + "\n" + final
              : final,
            interimTranscript: interim,
          }));
          onFinalRef.current?.(final.trim());
        } else {
          setState((prev) => ({ ...prev, interimTranscript: interim }));
        }
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onerror = (event: any) => {
        if (event.error === "no-speech") return;
        setState((prev) => ({ ...prev, error: event.error }));
      };

      recognition.onend = () => {
        // Auto-restart if user hasn't stopped
        if (isListeningRef.current) {
          try {
            recognition.start();
          } catch {
            // ignore
          }
        } else {
          setState((prev) => ({ ...prev, isListening: false, interimTranscript: "" }));
        }
      };

      return recognition;
    },
    []
  );

  const startListening = useCallback(
    (onFinal: (text: string) => void) => {
      onFinalRef.current = onFinal;
      isListeningRef.current = true;

      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }

      const recognition = initRecognition(lang);
      if (!recognition) return;

      recognitionRef.current = recognition;
      setState((prev) => ({
        ...prev,
        isListening: true,
        error: null,
        interimTranscript: "",
      }));

      try {
        recognition.start();
      } catch {
        setState((prev) => ({
          ...prev,
          isListening: false,
          error: "Failed to start microphone",
        }));
      }
    },
    [lang, initRecognition]
  );

  const stopListening = useCallback(() => {
    isListeningRef.current = false;
    onFinalRef.current = null;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
    setState((prev) => ({
      ...prev,
      isListening: false,
      interimTranscript: "",
    }));
  }, []);

  const clearTranscripts = useCallback(() => {
    setState((prev) => ({
      ...prev,
      finalTranscript: "",
      interimTranscript: "",
    }));
  }, []);

  useEffect(() => {
    return () => {
      isListeningRef.current = false;
      recognitionRef.current?.stop();
    };
  }, []);

  return { ...state, startListening, stopListening, clearTranscripts };
}
