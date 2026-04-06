"use client";

import { Mic, MicOff } from "lucide-react";

interface MicButtonProps {
  isListening: boolean;
  isSupported: boolean;
  onClick: () => void;
}

export function MicButton({ isListening, isSupported, onClick }: MicButtonProps) {
  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
      {!isSupported && (
        <p className="text-xs text-red-400 bg-white px-3 py-1 rounded-full shadow border border-red-100">
          Chrome 또는 Edge가 필요합니다
        </p>
      )}
      <div className="relative">
        {isListening && (
          <span className="absolute inset-0 rounded-full bg-red-400 animate-ping opacity-40" />
        )}
        <button
          onClick={onClick}
          disabled={!isSupported}
          aria-label={isListening ? "녹음 중지" : "녹음 시작"}
          className={`relative w-16 h-16 rounded-full flex items-center justify-center shadow-lg transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed ${
            isListening
              ? "bg-red-500 hover:bg-red-600 text-white"
              : "bg-white hover:bg-gray-50 text-gray-700 border border-gray-200"
          }`}
        >
          {isListening ? (
            <MicOff className="w-6 h-6" />
          ) : (
            <Mic className="w-6 h-6" />
          )}
        </button>
      </div>
    </div>
  );
}
