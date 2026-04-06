export interface Language {
  code: string;
  label: string;
  bcp47: string; // Web Speech API lang attribute
  ollamaName: string; // human-readable name for LLM prompt
}

export interface SpeechRecognitionState {
  isListening: boolean;
  interimTranscript: string;
  finalTranscript: string;
  error: string | null;
  isSupported: boolean;
}

export interface TranslationState {
  translatedText: string;
  streamingText: string; // current segment being streamed (not yet committed)
  isTranslating: boolean;
  error: string | null;
}
