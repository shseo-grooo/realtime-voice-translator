import { NextRequest } from "next/server";
import { getLanguageByCode } from "@/lib/languages";

const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
const OLLAMA_MODEL = process.env.OLLAMA_MODEL || "gemma3n:e2b";

export async function POST(req: NextRequest) {
  const { text, sourceLang, targetLang } = await req.json();

  if (!text?.trim()) {
    return new Response("Missing text", { status: 400 });
  }

  const source = getLanguageByCode(sourceLang);
  const target = getLanguageByCode(targetLang);

  if (!source || !target) {
    return new Response("Invalid language code", { status: 400 });
  }

  const prompt = `Translate the following ${source.ollamaName} text to ${target.ollamaName}. Return only the translated text with no explanations, no quotes, no extra formatting:\n\n${text.trim()}`;

  try {
    const ollamaRes = await fetch(`${OLLAMA_BASE_URL}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: OLLAMA_MODEL,
        prompt,
        stream: true,
      }),
    });

    if (!ollamaRes.ok) {
      return new Response(
        `Ollama error: ${ollamaRes.status} ${ollamaRes.statusText}`,
        { status: 502 }
      );
    }

    // Stream the translated tokens back to the client
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const reader = ollamaRes.body?.getReader();
        if (!reader) {
          controller.close();
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";

            for (const line of lines) {
              if (!line.trim()) continue;
              try {
                const json = JSON.parse(line);
                if (json.response) {
                  controller.enqueue(encoder.encode(json.response));
                }
                if (json.done) {
                  controller.close();
                  return;
                }
              } catch {
                // skip malformed lines
              }
            }
          }
        } finally {
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Transfer-Encoding": "chunked",
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return new Response(`Failed to connect to Ollama: ${message}`, {
      status: 502,
    });
  }
}
