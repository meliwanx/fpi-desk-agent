import { apiFetch } from "./api";
import { API } from "./constants";

const TARGET_SAMPLE_RATE = 16000;

export interface VoiceAssistData {
  transcript: string;
  summary: string;
  text: string;
  summary_failed: boolean;
  summary_error: string;
}

interface VoiceAssistResponse {
  code: number;
  message: string;
  data?: VoiceAssistData;
}

type WindowWithWebkitAudioContext = Window & typeof globalThis & {
  webkitAudioContext?: typeof AudioContext;
};

export interface VoiceRecorder {
  readonly mimeType: string;
  readonly state: "inactive" | "recording";
  start: () => void | Promise<void>;
  stop: () => void | Promise<void>;
  close: () => void | Promise<void>;
}

interface VoiceRecorderHandlers {
  onData: (blob: Blob) => void;
  onStop: () => void;
  onError: (error: unknown) => void;
}

const AUDIO_MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/ogg",
  "audio/mp4",
];

export class VoiceRecordingUnsupportedError extends Error {
  constructor(message = "Microphone recording is not supported in this environment") {
    super(message);
    this.name = "VoiceRecordingUnsupportedError";
  }
}

export function canRequestMicrophone(): boolean {
  return !!navigator.mediaDevices?.getUserMedia;
}

function audioContextCtor(): typeof AudioContext {
  const win = window as WindowWithWebkitAudioContext;
  const ctor = window.AudioContext || win.webkitAudioContext;
  if (!ctor) throw new Error("AudioContext is not available");
  return ctor;
}

function downmixToMono(buffer: AudioBuffer): Float32Array {
  const { numberOfChannels, length } = buffer;
  if (numberOfChannels === 1) {
    return new Float32Array(buffer.getChannelData(0));
  }

  const mono = new Float32Array(length);
  for (let channel = 0; channel < numberOfChannels; channel += 1) {
    const data = buffer.getChannelData(channel);
    for (let i = 0; i < length; i += 1) {
      mono[i] += data[i] / numberOfChannels;
    }
  }
  return mono;
}

function resampleLinear(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return input;
  const outputLength = Math.max(1, Math.round(input.length * toRate / fromRate));
  const output = new Float32Array(outputLength);
  const ratio = (input.length - 1) / Math.max(1, outputLength - 1);

  for (let i = 0; i < outputLength; i += 1) {
    const position = i * ratio;
    const left = Math.floor(position);
    const right = Math.min(left + 1, input.length - 1);
    const weight = position - left;
    output[i] = input[left] * (1 - weight) + input[right] * weight;
  }

  return output;
}

function concatFloat32(chunks: Float32Array[]): Float32Array {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

function encodeWavPcm16(samples: Float32Array, sampleRate: number): Blob {
  const dataBytes = samples.length * 2;
  const buffer = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(buffer);

  const writeString = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, dataBytes, true);

  let offset = 44;
  for (const sample of samples) {
    const clipped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function getSupportedRecordingMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return AUDIO_MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}

function createMediaRecorderVoiceRecorder(
  stream: MediaStream,
  handlers: VoiceRecorderHandlers,
): VoiceRecorder {
  const mimeType = getSupportedRecordingMimeType();
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) {
      handlers.onData(event.data);
    }
  };
  recorder.onstop = () => handlers.onStop();
  recorder.onerror = (event) => handlers.onError(event);

  return {
    mimeType: recorder.mimeType || mimeType || "audio/webm",
    get state() {
      return recorder.state === "inactive" ? "inactive" : "recording";
    },
    start: () => recorder.start(),
    stop: () => {
      if (recorder.state !== "inactive") recorder.stop();
    },
    close: () => {
      recorder.ondataavailable = null;
      recorder.onstop = null;
      recorder.onerror = null;
      if (recorder.state !== "inactive") recorder.stop();
    },
  };
}

function createPcmVoiceRecorder(
  stream: MediaStream,
  handlers: VoiceRecorderHandlers,
): VoiceRecorder {
  const Ctor = audioContextCtor();
  const context = new Ctor();
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];
  let state: VoiceRecorder["state"] = "inactive";
  let closed = false;

  processor.onaudioprocess = (event) => {
    for (let channel = 0; channel < event.outputBuffer.numberOfChannels; channel += 1) {
      event.outputBuffer.getChannelData(channel).fill(0);
    }
    if (state !== "recording") return;
    chunks.push(downmixToMono(event.inputBuffer));
  };

  source.connect(processor);
  processor.connect(context.destination);

  const cleanup = async () => {
    if (closed) return;
    closed = true;
    processor.onaudioprocess = null;
    try {
      processor.disconnect();
    } catch {
      // Node may already be disconnected.
    }
    try {
      source.disconnect();
    } catch {
      // Node may already be disconnected.
    }
    if (typeof context.close === "function") {
      await context.close().catch(() => undefined);
    }
  };

  return {
    mimeType: "audio/wav",
    get state() {
      return state;
    },
    start: async () => {
      if (closed) return;
      if (context.state === "suspended") {
        await context.resume();
      }
      state = "recording";
    },
    stop: async () => {
      if (state === "inactive") return;
      state = "inactive";
      try {
        const samples = concatFloat32(chunks);
        if (samples.length > 0) {
          const resampled = resampleLinear(samples, context.sampleRate, TARGET_SAMPLE_RATE);
          handlers.onData(encodeWavPcm16(resampled, TARGET_SAMPLE_RATE));
        }
        await cleanup();
        handlers.onStop();
      } catch (error) {
        await cleanup();
        handlers.onError(error);
      }
    },
    close: async () => {
      state = "inactive";
      chunks.length = 0;
      await cleanup();
    },
  };
}

export async function createVoiceRecorder(
  stream: MediaStream,
  handlers: VoiceRecorderHandlers,
): Promise<VoiceRecorder> {
  if (typeof MediaRecorder !== "undefined") {
    return createMediaRecorderVoiceRecorder(stream, handlers);
  }
  try {
    return createPcmVoiceRecorder(stream, handlers);
  } catch (error) {
    throw new VoiceRecordingUnsupportedError(
      error instanceof Error ? error.message : undefined,
    );
  }
}

export async function recordedAudioToWavBlob(blob: Blob): Promise<Blob> {
  if (blob.type === "audio/wav" || blob.type === "audio/x-wav") {
    return blob;
  }
  const Ctor = audioContextCtor();
  const context = new Ctor();
  try {
    const audioBuffer = await context.decodeAudioData(await blob.arrayBuffer());
    const mono = downmixToMono(audioBuffer);
    const resampled = resampleLinear(mono, audioBuffer.sampleRate, TARGET_SAMPLE_RATE);
    return encodeWavPcm16(resampled, TARGET_SAMPLE_RATE);
  } finally {
    if (typeof context.close === "function") {
      void context.close();
    }
  }
}

function responseMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "message" in payload) {
    const message = (payload as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

export async function transcribeVoiceInput(blob: Blob, languageHint = "zh"): Promise<VoiceAssistData> {
  const wavBlob = await recordedAudioToWavBlob(blob);
  const formData = new FormData();
  formData.append("audio", new File([wavBlob], "voice.wav", { type: "audio/wav" }));
  formData.append("language_hint", languageHint);

  const res = await apiFetch(API.VOICE.TRANSCRIBE, {
    method: "POST",
    body: formData,
    timeoutMs: 120_000,
  });

  const payload = await res.json().catch(() => null) as VoiceAssistResponse | null;
  if (!res.ok) {
    throw new Error(responseMessage(payload, `Voice transcription failed: ${res.status}`));
  }
  if (!payload?.data?.text && !payload?.data?.transcript) {
    throw new Error(responseMessage(payload, "Voice transcription returned no text"));
  }
  return payload.data;
}
