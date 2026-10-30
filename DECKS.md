# Deck format

A deck is one JSON file in `decks/`. Build it with:

```sh
python3 tools/build_deck.py decks/my-talk.json
```

This writes `public/decks/my-talk/` (the CD image, speaker notes and PNG previews) and refreshes the deck menu. Open `preview/contact-sheet.png` to review every slide at once.

## Top level

| Field | Default | Meaning |
|---|---|---|
| `name` | file name | URL name: `/?deck=my-talk` |
| `title` | name | Shown in the taskbar and deck menu |
| `theme` | `teal` | `teal`, `navy`, `paper` or `window` (see below) |
| `transition` | `none` | Default transition: `none`, `wipe`, `blinds`, `box`, `dissolve` |
| `footer` | `""` | Small text bottom-left on every slide |
| `slide_numbers` | `true` | Slide number bottom-right |
| `resolution` | `[640, 480]` | Match your Windows 95 screen size for 1:1 pixels; anything else is stretched |
| `clock` | `"10:19 AM"` | Taskbar clock text in the `window` theme |
| `slides` | — | 1–999 slide objects |

Every slide may also have `notes` (speaker notes in the player) and `transition` (overrides the default for moving onto that slide).

## Themes

- **teal**: PowerPoint 95 look. Dithered teal-to-navy background, yellow serif titles with drop shadows.
- **navy**: navy-to-black dither, white serif titles, red rule and diamond bullets.
- **paper**: white overhead-projector style, navy titles, maroon rule.
- **window**: every slide is a Windows 95 window on the teal desktop. The slide title goes in the caption bar; content sits in a white client area; there's a status bar and a taskbar.

All themes use only the 16 standard VGA colours and no anti-aliasing, so slides look the same in every Windows 95 display mode.

## Layouts

### `title`
```json
{ "layout": "title", "title": "Q3 Review", "subtitle": "What shipped and what's next", "byline": "Platform team" }
```

### `section`
```json
{ "layout": "section", "number": 2, "title": "Results", "subtitle": "Optional line" }
```

### `bullets`
A nested array is a group of sub-bullets under the previous bullet. Text shrinks to fit (26 px down to 14 px), but 4–6 bullets of one line or two is the comfortable maximum.
```json
{ "layout": "bullets", "title": "Agenda", "bullets": ["Numbers", ["Revenue", "Churn"], "Roadmap"] }
```

### `two-column`
```json
{ "layout": "two-column", "title": "Before vs. after",
  "left":  { "heading": "Before", "bullets": ["Manual deploys"] },
  "right": { "heading": "After",  "bullets": ["One click"] } }
```

### `statement`
One big sentence, with an optional attribution.
```json
{ "layout": "statement", "text": "Ship small, ship often.", "attribution": "Team motto" }
```

### `chart`
3D bar charts in the Excel 95 style, or a tilted pie with a legend.
```json
{ "layout": "chart", "title": "Signups", "chart": {
    "type": "bar", "labels": ["Jan", "Feb", "Mar"], "values": [120, 180, 260],
    "unit": "", "multicolor": false } }
```
- `type`: `bar` or `pie`
- `unit`: appended to values, for example `"%"` or `" ms"`
- `multicolor`: one colour per bar (bars are all blue otherwise)
- `colors`: an explicit list of colour names (from the 16 below)

### `table`
The first row is the header unless `"header": false`. Numeric cells are right-aligned.
```json
{ "layout": "table", "title": "Pricing", "rows": [["Plan", "Price"], ["Basic", "$5"], ["Pro", "$12"]] }
```

### `image`
The path is relative to the deck JSON. The image is scaled to fit and Floyd–Steinberg dithered to 16 colours, which is what it would have looked like on a 1995 VGA screen.
```json
{ "layout": "image", "title": "The office, 1995", "image": "img/office.jpg", "caption": "Optional caption" }
```

## Colour names

`black maroon green olive navy purple teal silver gray red lime yellow blue fuchsia aqua white`

## Writing decks with Claude

Give Claude this file plus what the talk is about, and ask for a deck JSON. Good prompts name the audience, the length (slide count) and a theme. Claude should build it with `tools/build_deck.py` and check `contact-sheet.png` for overflowing text before handing it over.
