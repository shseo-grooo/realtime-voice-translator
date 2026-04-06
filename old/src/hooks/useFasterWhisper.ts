"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SpeechRecognitionState } from "@/types";

const STT_WS_URL =
  process.env.NEXT_PUBLIC_STT_WS_URL ?? "ws://localhost:8000/ws";

const CHUNK_MS = 5000; // 5-second clips — gives whisper enough context

export function useFasterWhisper(lang: string) {
  const [state, setState] = useState<SpeechRecognitionState>({
    isListening: false,
    interimTranscript: "",
    finalTranscript: "",
    error: null,
    isSupported: false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // Keep a strong ref to prevent GC
  const recorderRef = useRef<MediaRecorder | null>(null);
  const isListeningRef = useRef(false);
  const onFinalRef = useRef<((text: string) => void) | null>(null);
  const chunkTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const langRef = useRef(lang);
  useEffect(() => { langRef.current = lang; }, [lang]);

  useEffect(() => {
    const supported =
      typeof window !== "undefined" &&
      typeof window.MediaRecorder !== "undefined" &&
      typeof window.WebSocket !== "undefined";
    setState((prev) => ({ ...prev, isSupported: supported }));
  }, []);

  // Use a ref to allow onstop to call the latest version without stale closures
  const startChunkRef = useRef<() => void>(() => {});

  startChunkRef.current = () => {
    const ws = wsRef.current;
    const stream = streamRef.current;
    if (!isListeningRef.current || !ws || !stream) return;
    if (ws.readyState !== WebSocket.OPEN) return;

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "";

    if (!mimeType) {
      setState((prev) => ({ ...prev, error: "지원하지 않는 오디오 형식입니다" }));
      return;
    }

    const chunks: Blob[] = [];
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType });
    } catch (e) {
      setState((prev) => ({ ...prev, error: `MediaRecorder 오류: ${e}` }));
      return;
    }
    recorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    recorder.onstop = async () => {
      recorderRef.current = null;

      if (chunks.length > 0 && ws.readyState === WebSocket.OPEN) {
        const blob = new Blob(chunks, { type: mimeType });
        // Only skip truly empty clips (< 500 bytes = headers only)
        if (blob.size >= 500) {
          setState((prev) => ({ ...prev, interimTranscript: "인식 중..." }));
          try {
            ws.send(await blob.arrayBuffer());
          } catch {
            // ws closed
          }
        }
      }

      // Start next clip immediately after sending
      if (isListeningRef.current) {
        startChunkRef.current();
      }
    };

    try {
      recorder.start();
    } catch (e) {
      setState((prev) => ({ ...prev, error: `녹음 시작 오류: ${e}` }));
      return;
    }

    // Stop after CHUNK_MS to finalize and send the clip
    chunkTimerRef.current = setTimeout(() => {
      if (recorderRef.current?.state === "recording") {
        recorderRef.current.stop();
      }
    }, CHUNK_MS);
  };

  const startListening = useCallback(async (onFinal: (text: string) => void) => {
    onFinalRef.current = onFinal;

    // Tear down any existing session
    isListeningRef.current = false;
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
    wsRef.current?.close();
    streamRef.current?.getTracks().forEach((t) => t.stop());

    setState((prev) => ({ ...prev, isListening: true, error: null, interimTranscript: "" }));

    // 1. Microphone
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;
    } catch {
      setState((prev) => ({
        ...prev,
        isListening: false,
        error: "마이크 접근 권한이 필요합니다",
      }));
      return;
    }

    // 2. WebSocket
    let ws: WebSocket;
    try {
      ws = await new Promise<WebSocket>((resolve, reject) => {
        const socket = new WebSocket(`${STT_WS_URL}?lang=${langRef.current}`);
        socket.binaryType = "arraybuffer";
        const timer = setTimeout(
          () => reject(new Error("STT 서버 연결 시간 초과 — python stt_server.py 실행 여부 확인")),
          5000
        );
        socket.onopen = () => { clearTimeout(timer); resolve(socket); };
        socket.onerror = () => {
          clearTimeout(timer);
          reject(new Error("STT 서버 연결 실패 (localhost:8000) — python stt_server.py 실행 필요"));
        };
      });
      wsRef.current = ws;
    } catch (err) {
      stream.getTracks().forEach((t) => t.stop());
      setState((prev) => ({
        ...prev,
        isListening: false,
        error: (err as Error).message,
      }));
      return;
    }

    // 3. Incoming transcription
    ws.onmessage = (event) => {
      const text = (event.data as string).trim();
      if (!text) return;
      setState((prev) => ({
        ...prev,
        interimTranscript: "",
        finalTranscript: prev.finalTranscript
          ? prev.finalTranscript + "\n" + text
          : text,
      }));
      onFinalRef.current?.(text);
    };

    ws.onclose = () => {
      if (isListeningRef.current) {
        setState((prev) => ({ ...prev, error: "STT 서버 연결이 끊겼습니다" }));
      }
    };

    // 4. Start first chunk
    isListeningRef.current = true;
    startChunkRef.current();
  }, []);

  const stopListening = useCallback(() => {
    isListeningRef.current = false;
    onFinalRef.current = null;
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
    wsRef.current?.close();
    wsRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setState((prev) => ({ ...prev, isListening: false, interimTranscript: "" }));
  }, []);

  const clearTranscripts = useCallback(() => {
    setState((prev) => ({ ...prev, finalTranscript: "", interimTranscript: "" }));
  }, []);

  useEffect(() => {
    return () => {
      isListeningRef.current = false;
      if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);
      recorderRef.current?.stop();
      wsRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { ...state, startListening, stopListening, clearTranscripts };
}
