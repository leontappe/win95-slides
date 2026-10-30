#!/usr/bin/env node
// Split a Windows 95 hard-disk image into 256 KB parts the player streams on demand,
// and write public/config.json.
//   node tools/prepare_disk.mjs <win95.img> [--memory 64] [--keyboard us|de] [--cd-drive D]
import { mkdir, open, readFile, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CHUNK = 256 * 1024;

const args = process.argv.slice(2);
const opt = (name, def) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args.splice(i, 2)[1] : def;
};
const memory = Number(opt("memory", 64));
const keyboard = opt("keyboard", undefined);
const cdDrive = opt("cd-drive", undefined);
const image = args[0];
if (!image) {
  console.error("usage: node tools/prepare_disk.mjs <win95.img> [--memory 64] [--keyboard us|de] [--cd-drive D]");
  process.exit(1);
}

const { size } = await stat(image);
if (size % 512) console.warn(`warning: ${size} bytes is not a multiple of 512; is this a raw disk image?`);

const outDir = path.join(root, "public", "disks", "hd");
await rm(outDir, { recursive: true, force: true }); // parts must match the snapshot exactly
await mkdir(outDir, { recursive: true });

// Last part is padded to a full chunk: v86 always requests fixed-size parts.
const fh = await open(image, "r");
const buf = Buffer.alloc(CHUNK);
let parts = 0;
for (let off = 0; off < size; off += CHUNK) {
  buf.fill(0);
  await fh.read(buf, 0, Math.min(CHUNK, size - off), off);
  await writeFile(path.join(outDir, `${off}-${off + CHUNK}.img`), buf);
  if (++parts % 200 === 0) process.stdout.write(`\r${parts} parts`);
}
await fh.close();

const cfgPath = path.join(root, "public", "config.json");
let cfg = {};
try { cfg = JSON.parse(await readFile(cfgPath, "utf8")); } catch {}
cfg = {
  state: "state/win95.bin.zst",
  vgaMB: 8,
  cdDrive: "D",
  keyboard: "us",
  autorunWaitMs: 5000,
  ...cfg,
  disk: { url: "disks/hd/.img", size, chunk: CHUNK },
  memoryMB: memory,
  ...(keyboard && { keyboard }),
  ...(cdDrive && { cdDrive: cdDrive.replace(/:$/, "").toUpperCase() }),
};
await writeFile(cfgPath, JSON.stringify(cfg, null, 2) + "\n");
console.log(`\r${parts} parts (${(size / 2 ** 20).toFixed(0)} MB) -> public/disks/hd/; wrote public/config.json`);
console.log("Old snapshots no longer match this disk. Make a new one: open /?mode=snapshot");
