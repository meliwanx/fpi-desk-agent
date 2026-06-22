import { access, cp, mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(scriptDir, "..");

async function exists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

async function copyIfExists(source, destination, options = {}) {
  if (!(await exists(source))) {
    console.warn(`[prepare-pdf-assets] Missing optional asset: ${source}`);
    return;
  }
  await mkdir(path.dirname(destination), { recursive: true });
  await cp(source, destination, options);
}

const publicDir = path.join(frontendDir, "public");

await mkdir(publicDir, { recursive: true });

await copyIfExists(
  path.join(frontendDir, "node_modules", "pdfjs-dist", "build", "pdf.worker.min.mjs"),
  path.join(publicDir, "pdf.worker.min.mjs"),
);

await rm(path.join(publicDir, "cmaps"), { recursive: true, force: true });
await rm(path.join(publicDir, "standard_fonts"), { recursive: true, force: true });

await copyIfExists(
  path.join(frontendDir, "node_modules", "pdfjs-dist", "cmaps"),
  path.join(publicDir, "cmaps"),
  { recursive: true },
);
await copyIfExists(
  path.join(frontendDir, "node_modules", "pdfjs-dist", "standard_fonts"),
  path.join(publicDir, "standard_fonts"),
  { recursive: true },
);
