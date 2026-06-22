"use client";

import { IS_DESKTOP } from "@/lib/constants";
import { desktopAPI } from "@/lib/tauri-api";

export function base64ToBytes(base64: string): Uint8Array<ArrayBuffer> {
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

export function parentDirectory(filePath: string | undefined | null): string | null {
  if (!filePath) return null;
  const normalized = filePath.replace(/\\/g, "/");
  const index = normalized.lastIndexOf("/");
  if (index <= 0) return null;
  return filePath.slice(0, index);
}

function toArrayBuffer(bytes: ArrayBuffer | Uint8Array<ArrayBuffer> | number[]): ArrayBuffer {
  if (bytes instanceof ArrayBuffer) return bytes;
  if (Array.isArray(bytes)) return new Uint8Array(bytes).buffer;
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function toNumberArray(bytes: ArrayBuffer | Uint8Array<ArrayBuffer> | number[]): number[] {
  if (Array.isArray(bytes)) return bytes;
  return Array.from(new Uint8Array(toArrayBuffer(bytes)));
}

export function downloadBlobInBrowser(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function saveBytesAsFile(
  bytes: ArrayBuffer | Uint8Array<ArrayBuffer> | number[],
  filename: string,
  mimeType = "application/octet-stream",
  defaultDirectory?: string | null,
): Promise<void> {
  if (IS_DESKTOP) {
    await desktopAPI.downloadAndSave({
      data: toNumberArray(bytes),
      defaultName: filename,
      defaultDirectory,
    });
    return;
  }

  downloadBlobInBrowser(new Blob([toArrayBuffer(bytes)], { type: mimeType }), filename);
}

export async function saveBlobAsFile(
  blob: Blob,
  filename: string,
  defaultDirectory?: string | null,
): Promise<void> {
  if (IS_DESKTOP) {
    await saveBytesAsFile(await blob.arrayBuffer(), filename, blob.type, defaultDirectory);
    return;
  }

  downloadBlobInBrowser(blob, filename);
}

export async function saveBase64AsFile(
  base64: string,
  filename: string,
  mimeType = "application/octet-stream",
  defaultDirectory?: string | null,
): Promise<void> {
  await saveBytesAsFile(base64ToBytes(base64), filename, mimeType, defaultDirectory);
}
