"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SpeechRecognitionState } from "@/types";

const STT_WS_URL =
  process.env.NEXT_PUBLIC_STT_WS_URL ?? "ws://localhost:8000/ws";

// Record in 2-second complete clips (stop → restart).
// Each clip is a self-contained WebM file that faster-whisper can decode.
const CHUNK_MS = 2000;

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

  // ------------------------------------------------------------------
  // Record one CHUNK_MS clip, send it, then immediately start the next
  // ------------------------------------------------------------------
  const recordChunk = useCallback(
    (stream: MediaStream, ws: WebSocket, mimeType: string) => {
      if (!isListeningRef.current || ws.readyState !== WebSocket.OPEN) return;

      const chunks: Blob[] = [];
      let recorder: MediaRecorder;

      try {
        recorder = new MediaRecorder(stream, { mimeType });
      } catch {
        setState((prev) => ({ ...prev, error: "MediaRecorder 초기화 실패" }));
        return;
      }

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      recorder.onstop = async () => {
        // Send this clip to STT server
        if (chunks.length > 0 && ws.readyState === WebSocket.OPEN) {
          const blob = new Blob(chunks, { type: mimeType });
          if (blob.size >= 1_000) {
            try {
              ws.send(await blob.arrayBuffer());
            } catch {
              // WebSocket closed — stop loop
              return;
            }
          }
        }
        // Start next clip immediately
        if (isListeningRef.current) {
          recordChunk(stream, ws, mimeType);
        }
      };

      recorder.start();
      chunkTimerRef.current = setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, CHUNK_MS);
    },
    []
  );

  // ------------------------------------------------------------------
  // startListening
  // ------------------------------------------------------------------
  const startListening = useCallback(
    async (onFinal: (text: string) => void) => {
      onFinalRef.current = onFinal;

      // Clean up any previous session
      isListeningRef.current = false;
      if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);
      wsRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());

      setState((prev) => ({ ...prev, isListening: true, error: null }));

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

      // 2. WebSocket to STT server
      let ws: WebSocket;
      try {
        ws = await new Promise<WebSocket>((resolve, reject) => {
          const socket = new WebSocket(
            `${STT_WS_URL}?lang=${langRef.current}`
          );
          socket.binaryType = "arraybuffer";
          const timer = setTimeout(
            () => reject(new Error("STT 서버 연결 시간 초과 (localhost:8000)")),
            5000
          );
          socket.onopen = () => { clearTimeout(timer); resolve(socket); };
          socket.onerror = () => {
            clearTimeout(timer);
            reject(new Error("STT 서버에 연결할 수 없습니다 (python stt_server.py 실행 필요)"));
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

      // 3. Handle incoming transcriptions
      ws.onmessage = (event) => {
        const text = (event.data as string).trim();
        if (!text) return;
        setState((prev) => ({
          ...prev,
          finalTranscript: prev.finalTranscript
            ? prev.finalTranscript + "\n" + text
            : text,
        }));
        onFinalRef.current?.(text);
      };

      ws.onclose = () => {
        if (isListeningRef.current) {
          setState((prev) => ({
            ...prev,
            error: "STT 서버 연결이 끊겼습니다",
          }));
        }
      };

      // 4. Start recording
      isListeningRef.current = true;
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      recordChunk(stream, ws, mimeType);
    },
    [recordChunk]
  );

  // ------------------------------------------------------------------
  // stopListening
  // ------------------------------------------------------------------
  const stopListening = useCallback(() => {
    isListeningRef.current = false;
    onFinalRef.current = null;
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);
    wsRef.current?.close();
    wsRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setState((prev) => ({ ...prev, isListening: false, interimTranscript: "" }));
  }, []);

  const clearTranscripts = useCallback(() => {
    setState((prev) => ({ ...prev, finalTranscript: "", interimTranscript: "" }));
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isListeningRef.current = false;
      if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);
      wsRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { ...state, startListening, stopListening, clearTranscripts };
}
