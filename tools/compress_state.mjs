#!/usr/bin/env node
// Compress a raw v86 state (saved from /?mode=snapshot) to public/state/win95.bin.zst.
// v86 detects the zstd frame and decompresses it itself.
//   node tools/compress_state.mjs <win95.bin>
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { constants, zstdCompressSync } from "node:zlib";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const src = process.argv[2];
if (!src) {
  console.error("usage: node tools/compress_state.mjs <win95.bin>");
  process.exit(1);
}
if (typeof zstdCompressSync !== "function") {
  console.error("Node 22.15+ is required (zlib zstd). Or run: zstd -19 <in> -o public/state/win95.bin.zst");
  process.exit(1);
}

const raw = await readFile(src);
const out = zstdCompressSync(raw, { params: { [constants.ZSTD_c_compressionLevel]: 19 } });
const dst = path.join(root, "public", "state", "win95.bin.zst");
await mkdir(path.dirname(dst), { recursive: true });
await writeFile(dst, out);
console.log(`${dst}: ${(out.length / 2 ** 20).toFixed(1)} MB (raw ${(raw.length / 2 ** 20).toFixed(1)} MB)`);
