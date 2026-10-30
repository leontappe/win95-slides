# Notes for Claude

This repo turns deck JSON into slideshows that run inside an emulated Windows 95.

When asked for a presentation:

1. Read DECKS.md for the format, then write `decks/<name>.json`.
2. Run `python3 tools/build_deck.py decks/<name>.json`.
3. Look at `public/decks/<name>/preview/contact-sheet.png` (and single slides where text is dense). Fix overflow by splitting slides or shortening bullets, not by cramming.
4. Hand back the JSON and the preview, and say how to open it: `/?deck=<name>`.

Don't edit `public/disks`, `public/state` or `public/config.json`; they belong to the user's Windows image. `build/SHOW.EXE` only needs rebuilding when `viewer/show.c` changes (`sh viewer/build.sh`).
