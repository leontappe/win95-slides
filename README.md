# Win95 Slides

Present slides inside a real Windows 95, running in a browser tab.

Windows 95 resumes from a RAM snapshot, so there is no boot screen. Each deck is a CD image, inserted after the snapshot loads. AutoPlay (or a typed Win+R fallback) starts `SHOW.EXE`, a native Win32 slideshow program. `SHOW.EXE` reports the current slide over COM1, so the page shows a slide counter and speaker notes and can drive the show.

Decks are JSON files, so Claude can write them for you. See [DECKS.md](DECKS.md).

```
public/                  static site, serve it from anywhere
  index.html             player, snapshot maker and preview mode
  sync-xhr.js            makes disk reads synchronous (Win95's IDE driver needs this)
  runtime/               v86 emulator (libv86.js + v86.wasm, BSD-2)
  bios/                  SeaBIOS + VGA BIOS from v86
  config.json            written by prepare_disk.mjs
  disks/hd/              your Windows 95 disk in 256 KB parts (generated, not included)
  state/win95.bin.zst    your RAM snapshot (generated, not included)
  decks/<name>/          deck.iso, deck.json, preview/*.png (generated)
decks/                   deck sources (JSON)
tools/                   build_deck.py, prepare_disk.mjs, compress_state.mjs, fonts
viewer/                  SHOW.EXE source (C, no SDK) and build script
build/SHOW.EXE           prebuilt
```

## Requirements

- Python 3 with `pillow numpy pycdlib` (`pip install pillow numpy pycdlib`)
- Node 22.15+ (for zstd compression of the snapshot)
- Your own Windows 95 hard-disk image (raw `.img`) with a working CD-ROM drive. A COM1 port is optional; without it the show still runs, but the page can't follow along.

## Try it without Windows

```sh
python3 -m http.server 8080 -d public
```

Open http://localhost:8080. Without a disk image the player opens in preview mode, with the slide PNGs and your speaker notes.

## Add Windows 95

1. **Prepare the image.** Before you start, inside Windows 95: turn off the screen saver, set the screen to 640×480 (or set `resolution` in your decks to match), and dismiss first-run dialogs.

   ```sh
   node tools/prepare_disk.mjs ~/win95.img            # add --keyboard de for a German Windows
   ```

   This splits the disk into `public/disks/hd/` and writes `public/config.json`.

2. **Make the snapshot.** Serve the site and open http://localhost:8080/?mode=snapshot. Windows cold-boots from your disk. Wait for a quiet desktop, keep the CD drive empty, then click **Save snapshot**.

   ```sh
   node tools/compress_state.mjs ~/Downloads/win95.bin
   ```

3. **Present.** Open http://localhost:8080/?deck=welcome. Use ⛶ for full screen, and **Notes** for the speaker notes window.

The disk parts and the snapshot are a matched pair. If you run `prepare_disk.mjs` again, make a new snapshot.

## During the show

Keys go to Windows, where SHOW.EXE handles them:

- **Right**, **Space**, **Enter** or a click: next slide
- **Left**, **Backspace** or a right-click: previous slide
- A number then **Enter**: jump to that slide
- **B** / **W**: black or white screen
- **Esc**: exit the show

The ◀ ▶ buttons in the taskbar do the same over the serial link. To switch decks, use the **Decks** menu; it reloads the page, which restores a clean snapshot.

## config.json

| Key | Default | |
|---|---|---|
| `memoryMB` | 64 | Must match the RAM used when the snapshot was made |
| `cdDrive` | `D` | Drive letter used by the Win+R fallback |
| `keyboard` | `us` | `us` or `de`; Windows' keyboard layout, used for typing `D:\show.exe` |
| `autorunWaitMs` | 5000 | How long to wait for AutoPlay before using Win+R |

## Hosting

Everything is static files: GitHub Pages, S3 or any web server works, with no special headers. Your Windows 95 image is Microsoft's licensed software, so keep a deployment that includes `disks/` and `state/` private. Don't commit them to a public repo; `.gitignore` already excludes them.

### mittwald mStudio

The live deployment is a container in project `p-clnq5p`, running `nginx:1.27-alpine` with this command:

```sh
sh -c "wget -qO- https://raw.githubusercontent.com/leontappe/win95-slides/main/deploy/start.sh | sh"
```

`deploy/start.sh` downloads this repo's `main` branch, serves `public/` on port 8080 with `deploy/nginx.conf`, and does nothing else. To deploy new decks, push to `main` and restart the container. Set `SITE_REF` to pin a tag or commit. For a self-built image, use the `Dockerfile` instead.

## Rebuilding

```sh
sh viewer/build.sh                       # SHOW.EXE (needs clang, lld-link, llvm-dlltool; pip install pefile)
python3 tools/build_deck.py decks/*.json  # all decks
```

## How it works and credits

The snapshot approach follows [encarta_95_web](https://github.com/benwinding/encarta_95_web). It uses a RAM-only v86 state compressed with zstd, the disk served as 256 KB parts that are fetched on demand, and synchronous reads because Windows 95's `ESDI_506` driver aborts slow I/O. That project patches v86 for the synchronous reads; here `sync-xhr.js` does the same from outside, so the stock v86 build works. The snapshot is saved with the CD drive empty, and each deck's CD is inserted after restore, so one snapshot serves every deck.

Emulator: [v86](https://github.com/copy/v86) (BSD-2). Slide fonts: Liberation Sans and Serif (SIL OFL), metric clones of Arial and Times New Roman, the fonts Windows 95 shipped with.
