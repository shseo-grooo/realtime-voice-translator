import { Language } from "@/types";

export const LANGUAGES: Language[] = [
  { code: "ko", label: "한국어", bcp47: "ko-KR", ollamaName: "Korean" },
  { code: "en", label: "English", bcp47: "en-US", ollamaName: "English" },
  { code: "ja", label: "日本語", bcp47: "ja-JP", ollamaName: "Japanese" },
  { code: "zh", label: "中文", bcp47: "zh-CN", ollamaName: "Chinese (Simplified)" },
  { code: "es", label: "Español", bcp47: "es-ES", ollamaName: "Spanish" },
  { code: "fr", label: "Français", bcp47: "fr-FR", ollamaName: "French" },
  { code: "de", label: "Deutsch", bcp47: "de-DE", ollamaName: "German" },
  { code: "pt", label: "Português", bcp47: "pt-PT", ollamaName: "Portuguese" },
  { code: "it", label: "Italiano", bcp47: "it-IT", ollamaName: "Italian" },
  { code: "ru", label: "Русский", bcp47: "ru-RU", ollamaName: "Russian" },
  { code: "ar", label: "العربية", bcp47: "ar-SA", ollamaName: "Arabic" },
  { code: "vi", label: "Tiếng Việt", bcp47: "vi-VN", ollamaName: "Vietnamese" },
  { code: "th", label: "ภาษาไทย", bcp47: "th-TH", ollamaName: "Thai" },
  { code: "id", label: "Bahasa Indonesia", bcp47: "id-ID", ollamaName: "Indonesian" },
];

export function getLanguageByCode(code: string): Language | undefined {
  return LANGUAGES.find((l) => l.code === code);
}
