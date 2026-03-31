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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);
  const isListeningRef = useRef(false);
  const onFinalRef = useRef<((text: string) => void) | null>(null);
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  // Tracks the current lang inside onend closures without stale closure issues
  const langRef = useRef(lang);
  useEffect(() => { langRef.current = lang; }, [lang]);

  useEffect(() => {
    const supported =
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
    setState((prev) => ({ ...prev, isSupported: supported }));
  }, []);

  // createInstance always makes a fresh SpeechRecognition object.
  // Referenced via ref so onend closures can call the latest version.
  const createInstanceRef = useRef<() => void>(() => {});

  createInstanceRef.current = () => {
    if (
      typeof window === "undefined" ||
      (!("SpeechRecognition" in window) && !("webkitSpeechRecognition" in window))
    ) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const API: any = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const recognition: any = new API();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = langRef.current;

    recognitionRef.current = recognition;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) final += result[0].transcript;
        else interim += result[0].transcript;
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
      // aborted = we called stop/abort intentionally; no-speech = silence, not an error
      if (event.error === "no-speech" || event.error === "aborted") return;
      setState((prev) => ({ ...prev, error: event.error }));
    };

    recognition.onend = () => {
      // Only restart if the user hasn't clicked stop
      if (!isListeningRef.current) {
        setState((prev) => ({ ...prev, isListening: false, interimTranscript: "" }));
        return;
      }
      // Delay before restarting — browser needs a tick to fully reset
      restartTimerRef.current = setTimeout(() => {
        if (isListeningRef.current) {
          createInstanceRef.current();
        }
      }, 150);
    };

    try {
      recognition.start();
    } catch {
      // InvalidStateError etc. — retry once after a short delay
      restartTimerRef.current = setTimeout(() => {
        if (isListeningRef.current) {
          createInstanceRef.current();
        }
      }, 300);
    }
  };

  const startListening = useCallback(async (onFinal: (text: string) => void) => {
    onFinalRef.current = onFinal;

    // Abort existing instance cleanly first so old onend won't restart.
    isListeningRef.current = false;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch { /* ignore */ }
      recognitionRef.current = null;
    }

    // Request mic with noise suppression + echo cancellation.
    // This configures the browser audio pipeline before SpeechRecognition starts,
    // so both share the same processed audio track.
    try {
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      audioStreamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch {
      // Permission denied or unsupported — continue anyway without the stream
      audioStreamRef.current = null;
    }

    isListeningRef.current = true;
    setState((prev) => ({ ...prev, isListening: true, error: null, interimTranscript: "" }));

    // Small delay to ensure the aborted instance has fully settled
    restartTimerRef.current = setTimeout(() => {
      if (isListeningRef.current) createInstanceRef.current();
    }, 50);
  }, []);

  const stopListening = useCallback(() => {
    isListeningRef.current = false;
    onFinalRef.current = null;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch { /* ignore */ }
      recognitionRef.current = null;
    }
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((t) => t.stop());
      audioStreamRef.current = null;
    }
    setState((prev) => ({ ...prev, isListening: false, interimTranscript: "" }));
  }, []);

  const clearTranscripts = useCallback(() => {
    setState((prev) => ({ ...prev, finalTranscript: "", interimTranscript: "" }));
  }, []);

  useEffect(() => {
    return () => {
      isListeningRef.current = false;
      if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
      try { recognitionRef.current?.abort(); } catch { /* ignore */ }
      audioStreamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { ...state, startListening, stopListening, clearTranscripts };
}
