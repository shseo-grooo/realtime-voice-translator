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
  const isActiveRef = useRef(false);    // true between onstart ~ onend
  const isRestartingRef = useRef(false); // prevents concurrent restart attempts
  const onFinalRef = useRef<((text: string) => void) | null>(null);
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const watchdogRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const langRef = useRef(lang);
  useEffect(() => { langRef.current = lang; }, [lang]);

  useEffect(() => {
    const supported =
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
    setState((prev) => ({ ...prev, isSupported: supported }));
  }, []);

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

    recognition.onstart = () => {
      isActiveRef.current = true;
      isRestartingRef.current = false;
    };

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
      if (event.error === "no-speech" || event.error === "aborted") return;
      if (event.error === "network") {
        // Network blip — retry after 1s
        scheduleRestart(1000);
        return;
      }
      setState((prev) => ({ ...prev, error: event.error }));
    };

    recognition.onend = () => {
      isActiveRef.current = false;
      if (!isListeningRef.current) {
        setState((prev) => ({ ...prev, isListening: false, interimTranscript: "" }));
        return;
      }
      scheduleRestart(50);
    };

    try {
      recognition.start();
    } catch {
      scheduleRestart(300);
    }
  };

  function scheduleRestart(delay: number) {
    if (!isListeningRef.current || isRestartingRef.current) return;
    isRestartingRef.current = true;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    restartTimerRef.current = setTimeout(() => {
      if (isListeningRef.current) createInstanceRef.current();
    }, delay);
  }

  // Watchdog: every 2s, if we should be listening but recognition isn't active
  // and no restart is scheduled, force a new instance.
  const startWatchdog = useCallback(() => {
    if (watchdogRef.current) clearInterval(watchdogRef.current);
    watchdogRef.current = setInterval(() => {
      if (!isListeningRef.current) {
        clearInterval(watchdogRef.current!);
        watchdogRef.current = null;
        return;
      }
      if (!isActiveRef.current && !isRestartingRef.current) {
        createInstanceRef.current();
      }
    }, 2000);
  }, []);

  const startListening = useCallback(async (onFinal: (text: string) => void) => {
    onFinalRef.current = onFinal;

    // Stop previous instance without triggering auto-restart
    isListeningRef.current = false;
    isRestartingRef.current = false;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch { /* ignore */ }
      recognitionRef.current = null;
    }

    try {
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      audioStreamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch {
      audioStreamRef.current = null;
    }

    isListeningRef.current = true;
    setState((prev) => ({ ...prev, isListening: true, error: null, interimTranscript: "" }));

    restartTimerRef.current = setTimeout(() => {
      if (isListeningRef.current) {
        createInstanceRef.current();
        startWatchdog();
      }
    }, 50);
  }, [startWatchdog]);

  const stopListening = useCallback(() => {
    isListeningRef.current = false;
    isRestartingRef.current = false;
    onFinalRef.current = null;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    if (watchdogRef.current) { clearInterval(watchdogRef.current); watchdogRef.current = null; }
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
      if (watchdogRef.current) clearInterval(watchdogRef.current);
      try { recognitionRef.current?.abort(); } catch { /* ignore */ }
      audioStreamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { ...state, startListening, stopListening, clearTranscripts };
}
