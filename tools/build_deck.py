#!/usr/bin/env python3
"""Compile a deck JSON into a Windows 95 slideshow CD.

    python3 tools/build_deck.py decks/example.json [--out public/decks]

Writes <out>/<name>/deck.iso (SHOW.EXE + AUTORUN.INF + DECK.INI + SLIDEnnn.BMP),
deck.json (titles + speaker notes for the web player) and preview PNGs.
Slides use only the 16 standard VGA colours and no anti-aliasing, so they look
native and identical in every Windows 95 display mode. See DECKS.md for the format.
"""
import argparse
import io
import json
import re
import struct
import sys
from pathlib import Path

import numpy as np
import pycdlib
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "tools" / "fonts"
SHOW_EXE = ROOT / "build" / "SHOW.EXE"

# Standard Windows 16-colour palette, in VGA index order.
VGA = [
    ("black", (0, 0, 0)), ("maroon", (128, 0, 0)), ("green", (0, 128, 0)), ("olive", (128, 128, 0)),
    ("navy", (0, 0, 128)), ("purple", (128, 0, 128)), ("teal", (0, 128, 128)), ("silver", (192, 192, 192)),
    ("gray", (128, 128, 128)), ("red", (255, 0, 0)), ("lime", (0, 255, 0)), ("yellow", (255, 255, 0)),
    ("blue", (0, 0, 255)), ("fuchsia", (255, 0, 255)), ("aqua", (0, 255, 255)), ("white", (255, 255, 255)),
]
C = {name: i for i, (name, _) in enumerate(VGA)}
PALETTE = [v for _, rgb in VGA for v in rgb]
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 + 1 / 32

SERIES = ["blue", "red", "lime", "yellow", "fuchsia", "aqua", "olive", "purple"]

THEMES = {
    # PowerPoint 95 "blue diagonal" mood: dithered teal->navy, yellow shadowed serif titles
    "teal": dict(bg=("teal", "navy"), title="yellow", text="white", sub="silver", bullet="yellow",
                 accent="aqua", shadow="black", title_font="serif", rule=None, chart_axis="white",
                 chart_bg=None, footer="silver", bullet_shape="square"),
    "navy": dict(bg=("navy", "black"), title="white", text="white", sub="silver", bullet="red",
                 accent="yellow", shadow="black", title_font="serif", rule="red", chart_axis="silver",
                 chart_bg=None, footer="gray", bullet_shape="diamond"),
    "paper": dict(bg=("white", "white"), title="navy", text="black", sub="gray", bullet="maroon",
                  accent="maroon", shadow=None, title_font="serif", rule="maroon", chart_axis="black",
                  chart_bg=None, footer="gray", bullet_shape="square"),
    # every slide is a Windows 95 window on the teal desktop
    "window": dict(bg=("teal", "teal"), title="white", text="black", sub="gray", bullet="navy",
                   accent="navy", shadow=None, title_font="sans", rule=None, chart_axis="black",
                   chart_bg="white", footer="white", bullet_shape="square"),
}


class Font:
    _cache = {}

    @classmethod
    def get(cls, family, size, bold=False, italic=False):
        style = "Bold" if bold else ("Italic" if italic else "Regular")
        name = {"serif": "LiberationSerif", "sans": "LiberationSans"}[family]
        key = (name, style, size)
        if key not in cls._cache:
            cls._cache[key] = ImageFont.truetype(str(FONTS / f"{name}-{style}.ttf"), size)
        return cls._cache[key]


def wrap(text, font, width):
    """Greedy word wrap by pixel width; splits words that are wider than a line."""
    lines = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split():
            cand = f"{line} {word}" if line else word
            if font.getlength(cand) <= width:
                line = cand
                continue
            if line:
                lines.append(line)
            while font.getlength(word) > width and len(word) > 1:
                cut = len(word)
                while cut > 1 and font.getlength(word[:cut]) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            line = word
        lines.append(line)
    return lines


class Slide:
    """One 16-colour slide canvas plus the theme's drawing helpers."""

    def __init__(self, w, h, theme, deck, number, total):
        self.w, self.h, self.t = w, h, theme
        self.s = w / 640
        self.deck, self.number, self.total = deck, number, total
        self.img = Image.new("P", (w, h), C[theme["bg"][0]])
        self.img.putpalette(PALETTE)
        self.d = ImageDraw.Draw(self.img)
        self.d.fontmode = "1"  # no anti-aliasing, like Windows 95 GDI
        self.background()

    def px(self, v):
        return int(round(v * self.s))

    def col(self, key_or_name):
        return C[self.t.get(key_or_name, key_or_name)]

    # --- background and chrome -------------------------------------------------
    def background(self):
        top, bottom = self.t["bg"]
        if top != bottom:
            y = np.linspace(0, 1, self.h)[:, None]
            thresh = np.tile(BAYER4, (self.h // 4 + 1, self.w // 4 + 1))[: self.h, : self.w]
            arr = np.where(thresh > y, C[top], C[bottom]).astype(np.uint8)
            bg = Image.fromarray(arr, "P")
            bg.putpalette(PALETTE)
            self.img.paste(bg)
        if self.t is THEMES["window"]:
            self.window_chrome()
        else:
            self.content = (self.px(40), self.px(112), self.w - self.px(40), self.h - self.px(36))
            self.title_box = (self.px(40), self.px(24), self.w - self.px(40), self.px(96))

    def bevel(self, box, raised=True, depth=2):
        x0, y0, x1, y1 = box
        hi, lo = (C["white"], C["black"]) if raised else (C["gray"], C["white"])
        hi2, lo2 = (C["silver"], C["gray"]) if raised else (C["black"], C["silver"])
        d = self.d
        d.line([(x0, y1 - 1), (x0, y0), (x1 - 1, y0)], fill=hi2 if raised else hi)
        d.line([(x0, y1), (x1, y1), (x1, y0)], fill=lo)
        if depth > 1:
            d.line([(x0 + 1, y1 - 2), (x0 + 1, y0 + 1), (x1 - 2, y0 + 1)], fill=hi if raised else hi2)
            d.line([(x0 + 1, y1 - 1), (x1 - 1, y1 - 1), (x1 - 1, y0 + 1)], fill=lo2)

    def window_chrome(self):
        p, d = self.px, self.d
        win = (p(20), p(16), self.w - p(20), self.h - p(40))
        d.rectangle(win, fill=C["silver"])
        self.bevel(win)
        bar_h = p(30)
        bar = (win[0] + 4, win[1] + 4, win[2] - 4, win[1] + 4 + bar_h)
        d.rectangle(bar, fill=C["navy"])
        # caption buttons: _ [] x
        bs = bar_h - p(8)
        bx = bar[2] - p(4) - bs
        for i, glyph in enumerate(["x", "max", "min"]):
            x0 = bx - i * (bs + p(4)) - (p(4) if i else 0)
            box = (x0, bar[1] + p(4), x0 + bs, bar[1] + p(4) + bs)
            d.rectangle(box, fill=C["silver"])
            self.bevel(box)
            cx0, cy0, cx1, cy1 = box[0] + p(6), box[1] + p(6), box[2] - p(7), box[3] - p(7)
            if glyph == "x":
                for o in range(2):
                    d.line([(cx0 + o, cy0), (cx1 + o - 1, cy1)], fill=0)
                    d.line([(cx0 + o, cy1), (cx1 + o - 1, cy0)], fill=0)
            elif glyph == "max":
                d.rectangle((cx0, cy0, cx1, cy1), outline=0)
                d.line([(cx0, cy0 + 1), (cx1, cy0 + 1)], fill=0)
            else:
                d.rectangle((cx0, cy1 - 1, cx0 + (cx1 - cx0) * 2 // 3, cy1), fill=0)
        self.caption_box = (bar[0] + p(8), bar[1], bx - 2 * (bs + p(4)) - p(8), bar[3])
        # status bar
        sb = (win[0] + p(6), win[3] - p(26), win[2] - p(6), win[3] - p(6))
        self.bevel(sb, raised=False, depth=1)
        self.status_box = sb
        # client area
        client = (win[0] + p(6), bar[3] + p(6), win[2] - p(6), sb[1] - p(6))
        d.rectangle(client, fill=C["white"])
        self.bevel((client[0] - 2, client[1] - 2, client[2] + 1, client[3] + 1), raised=False)
        self.title_box = None
        self.content = (client[0] + p(24), client[1] + p(20), client[2] - p(24), client[3] - p(16))
        # taskbar with Start button and clock
        tb = (0, self.h - p(28), self.w, self.h)
        d.rectangle(tb, fill=C["silver"])
        d.line([(0, tb[1] + 1), (self.w, tb[1] + 1)], fill=C["white"])
        start = (p(2), tb[1] + p(4), p(64), self.h - p(3))
        self.bevel(start)
        f = Font.get("sans", p(13), bold=True)
        flag = start[0] + p(6)
        for i, c in enumerate(["red", "lime", "blue", "yellow"]):
            fx, fy = flag + (i % 2) * p(7), start[1] + p(4) + (i // 2) * p(7)
            d.rectangle((fx, fy, fx + p(5), fy + p(5)), fill=C[c])
        d.text((flag + p(18), (start[1] + start[3]) // 2), "Start", font=f, fill=0, anchor="lm")
        tray = (self.w - p(70), start[1], self.w - p(3), start[3])
        self.bevel(tray, raised=False, depth=1)
        self.tray_box = tray

    # --- text helpers -------------------------------------------------------------
    def text(self, xy, s, font, fill, anchor="la", shadow=None):
        if shadow is not None:
            o = max(1, self.px(2))
            self.d.text((xy[0] + o, xy[1] + o), s, font=font, fill=C[shadow], anchor=anchor)
        self.d.text(xy, s, font=font, fill=self.col(fill), anchor=anchor)

    def fit_lines(self, text, family, sizes, width, max_h, bold=False, spacing=1.15):
        for size in sizes:
            f = Font.get(family, self.px(size), bold=bold)
            lines = wrap(text, f, width)
            lh = int(f.size * spacing)
            if len(lines) * lh <= max_h:
                return f, lines, lh
        return f, lines, lh

    def draw_title(self, title):
        if not title:
            return
        if self.title_box is None:  # window theme: caption bar
            x0, y0, x1, y1 = self.caption_box
            f = Font.get("sans", self.px(17), bold=True)
            s = title
            while f.getlength(s) > x1 - x0 and len(s) > 4:
                s = s[:-2].rstrip() + "…" if not s.endswith("…") else s[:-2] + "…"
            self.text((x0, (y0 + y1) // 2), s, f, "white", anchor="lm")
            return
        x0, y0, x1, y1 = self.title_box
        f, lines, lh = self.fit_lines(title, self.t["title_font"], [40, 36, 32, 28, 24], x1 - x0, y1 - y0, bold=True)
        y = (y0 + y1) // 2 - len(lines) * lh // 2
        for ln in lines:
            self.text((x0, y), ln, f, "title", shadow=self.t["shadow"])
            y += lh
        if self.t["rule"]:
            self.d.rectangle((x0, y1 + self.px(2), x1, y1 + self.px(4)), fill=self.col("rule"))

    def footer(self, text=None):
        f = Font.get("sans", self.px(12))
        num = f"{self.number}" if self.deck.get("slide_numbers", True) else ""
        foot = text if text is not None else self.deck.get("footer", "")
        if self.t is THEMES["window"]:
            x0, y0, x1, y1 = self.status_box
            if foot:
                self.text((x0 + self.px(6), (y0 + y1) // 2), foot, f, "black", anchor="lm")
            if num:
                self.text((x1 - self.px(6), (y0 + y1) // 2), f"Slide {self.number} of {self.total}", f, "black", anchor="rm")
            tx0, ty0, tx1, ty1 = self.tray_box
            self.text(((tx0 + tx1) // 2, (ty0 + ty1) // 2), self.deck.get("clock", "10:19 AM"), f, "black", anchor="mm")
            return
        y = self.h - self.px(18)
        if foot:
            self.text((self.px(40), y), foot, f, "footer", anchor="lm")
        if num:
            self.text((self.w - self.px(40), y), num, f, "footer", anchor="rm")

    def bullet_mark(self, x, y, size, level):
        d, c = self.d, self.col("bullet") if level == 0 else self.col("sub")
        r = max(2, size // 2)
        if level > 0:
            d.rectangle((x, y - 1, x + r, y), fill=c)  # en-dash
            return
        if self.t["bullet_shape"] == "diamond":
            d.polygon([(x + r // 2, y - r // 2), (x + r, y), (x + r // 2, y + r // 2), (x, y)], fill=c)
        else:
            d.rectangle((x, y - r // 2, x + r - 1, y + r // 2 - 1), fill=c)

    def bullets(self, items, box, sizes=(26, 24, 22, 20, 18, 16, 14)):
        """Draw (nested) bullets in box, shrinking the font until everything fits."""
        flat = []
        for it in items:
            if isinstance(it, list):
                flat += [(1, str(x)) for x in it]
            else:
                flat.append((0, str(it)))
        x0, y0, x1, y1 = box
        for size in sizes:
            f0 = Font.get("sans", self.px(size))
            f1 = Font.get("sans", self.px(size * 0.85))
            indent0, indent1 = self.px(size * 1.2), self.px(size * 2.4)
            laid, h = [], 0
            for level, txt in flat:
                f = f0 if level == 0 else f1
                ind = indent0 if level == 0 else indent1
                lines = wrap(txt, f, x1 - x0 - ind)
                lh = int(f.size * 1.18)
                gap = int(f.size * (0.45 if level == 0 else 0.35))
                laid.append((level, f, ind, lines, lh, gap))
                h += len(lines) * lh + gap
            if h <= y1 - y0:
                break
        y = y0
        for level, f, ind, lines, lh, gap in laid:
            mark_x = x0 + (0 if level == 0 else indent0)
            self.bullet_mark(mark_x, y + lh // 2, int(f.size * 0.45), level)
            for ln in lines:
                self.text((x0 + ind, y), ln, f, "text" if level == 0 else "sub")
                y += lh
            y += gap
        return y


# --- layouts -----------------------------------------------------------------------
def layout_title(sl, spec):
    x0, y0, x1, y1 = sl.content if sl.title_box is None else (sl.px(48), sl.px(40), sl.w - sl.px(48), sl.h - sl.px(40))
    if sl.title_box is None:
        sl.draw_title(spec.get("caption", sl.deck.get("title", "")))
    fam = sl.t["title_font"]
    ft, tl, tlh = sl.fit_lines(spec.get("title", ""), fam, [52, 46, 40, 34, 28], x1 - x0, (y1 - y0) // 2, bold=True)
    fs, sls, slh = sl.fit_lines(spec.get("subtitle", ""), "sans", [24, 22, 20, 18], x1 - x0, (y1 - y0) // 3)
    if not spec.get("subtitle"):
        sls = []
    rule = sl.px(28)
    total = len(tl) * tlh + rule + len(sls) * slh
    y = (y0 + y1) // 2 - total // 2
    cx = (x0 + x1) // 2
    title_col = "title" if sl.title_box is not None else "navy"
    for ln in tl:
        sl.text((cx, y), ln, ft, title_col, anchor="ma", shadow=sl.t["shadow"])
        y += tlh
    sl.d.rectangle((cx - sl.px(90), y + rule // 2 - 1, cx + sl.px(90), y + rule // 2 + 1), fill=sl.col("accent"))
    y += rule
    for ln in sls:
        sl.text((cx, y), ln, fs, "text", anchor="ma")
        y += slh
    if spec.get("byline"):
        fb = Font.get("sans", sl.px(16), italic=True)
        sl.text((cx, y1 - sl.px(8)), spec["byline"], fb, "sub", anchor="md")
    sl.footer(text=spec.get("footer", ""))


def layout_section(sl, spec):
    x0, y0, x1, y1 = sl.content if sl.title_box is None else (sl.px(48), sl.px(60), sl.w - sl.px(48), sl.h - sl.px(60))
    if sl.title_box is None:
        sl.draw_title(spec.get("caption", sl.deck.get("title", "")))
    fam = sl.t["title_font"]
    y = (y0 + y1) // 2
    if spec.get("number") is not None:
        fn = Font.get(fam, sl.px(110), bold=True)
        sl.text((x0, y), str(spec["number"]), fn, "accent", anchor="lm", shadow=sl.t["shadow"])
        x0 += int(fn.getlength(str(spec["number"]))) + sl.px(28)
        sl.d.rectangle((x0 - sl.px(14), y - sl.px(60), x0 - sl.px(12), y + sl.px(60)), fill=sl.col("accent"))
    ft, lines, lh = sl.fit_lines(spec.get("title", ""), fam, [44, 38, 32, 28], x1 - x0, sl.px(200), bold=True)
    ty = y - len(lines) * lh // 2
    title_col = "title" if sl.title_box is not None else "navy"
    for ln in lines:
        sl.text((x0, ty), ln, ft, title_col, shadow=sl.t["shadow"])
        ty += lh
    if spec.get("subtitle"):
        fs = Font.get("sans", sl.px(20))
        sl.text((x0, ty + sl.px(6)), spec["subtitle"], fs, "sub")
    sl.footer()


def layout_bullets(sl, spec):
    sl.draw_title(spec.get("title", ""))
    sl.bullets(spec.get("bullets", []), sl.content)
    sl.footer()


def layout_two_column(sl, spec):
    sl.draw_title(spec.get("title", ""))
    x0, y0, x1, y1 = sl.content
    gap = sl.px(28)
    mid = (x0 + x1) // 2
    for col, (cx0, cx1) in zip([spec.get("left", {}), spec.get("right", {})], [(x0, mid - gap // 2), (mid + gap // 2, x1)]):
        y = y0
        if col.get("heading"):
            fh = Font.get("sans", sl.px(21), bold=True)
            sl.text((cx0, y), col["heading"], fh, "accent")
            y += int(fh.size * 1.3)
            sl.d.rectangle((cx0, y, cx1, y + sl.px(1)), fill=sl.col("accent"))
            y += sl.px(10)
        sl.bullets(col.get("bullets", []), (cx0, y, cx1, y1), sizes=(22, 20, 18, 16, 14, 12))
    sl.footer()


def layout_statement(sl, spec):
    if sl.title_box is None:
        sl.draw_title(spec.get("title", sl.deck.get("title", "")))
        box = sl.content
    else:
        box = (sl.px(64), sl.px(40), sl.w - sl.px(64), sl.h - sl.px(56))
    x0, y0, x1, y1 = box
    fam = sl.t["title_font"]
    f, lines, lh = sl.fit_lines(spec.get("text", ""), fam, [44, 40, 36, 32, 28, 24, 20], x1 - x0 - sl.px(40), int((y1 - y0) * 0.7), bold=True)
    attr = spec.get("attribution")
    total = len(lines) * lh + (sl.px(50) if attr else 0) - sl.px(40)
    y = (y0 + y1) // 2 - total // 2
    # oversized opening quote mark, above the text block
    fq = Font.get(fam, sl.px(110), bold=True)
    sl.text(((x0 + x1) // 2, y - sl.px(8)), "“", fq, "accent", anchor="ms")
    y += sl.px(16)
    cx = (x0 + x1) // 2
    col = "title" if sl.title_box is not None else "navy"
    for ln in lines:
        sl.text((cx, y), ln, f, col, anchor="ma", shadow=sl.t["shadow"])
        y += lh
    if attr:
        fa = Font.get("sans", sl.px(20), italic=True)
        sl.text((cx, y + sl.px(18)), f"— {attr}", fa, "sub", anchor="ma")
    sl.footer()


def axis_ticks(vmax, n=4):
    """Round tick step (1/2/5 x 10^k) so that n steps cover vmax."""
    if vmax <= 0:
        return 1, 1
    raw = vmax / n
    mag = 10 ** np.floor(np.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
    steps = int(np.ceil(vmax / step - 1e-9))
    return step, steps


def fmt_num(v, unit=""):
    s = f"{v:,.1f}".rstrip("0").rstrip(".") if isinstance(v, float) and not float(v).is_integer() else f"{int(v):,}"
    return f"{s}{unit}"


def layout_chart(sl, spec):
    sl.draw_title(spec.get("title", ""))
    ch = spec.get("chart", {})
    kind = ch.get("type", "bar")
    x0, y0, x1, y1 = sl.content
    if kind == "pie":
        return chart_pie(sl, ch, (x0, y0, x1, y1))
    labels, values = ch.get("labels", []), [float(v) for v in ch.get("values", [])]
    unit = ch.get("unit", "")
    f = Font.get("sans", sl.px(14))
    fv = Font.get("sans", sl.px(14), bold=True)
    axis = sl.col("chart_axis")
    step, steps = axis_ticks(max(values) if values else 1)
    top = step * steps
    tick_labels = [fmt_num(round(step * i, 6), unit) for i in range(steps + 1)]
    left = x0 + int(max(f.getlength(t) for t in tick_labels) + sl.px(12))
    base = y1 - sl.px(30)
    plot_top = y0 + sl.px(24)
    depth = sl.px(10)
    # gridlines + axis labels
    for i, lab in enumerate(tick_labels):
        y = base - (base - plot_top) * i / steps
        if i:
            for xx in range(left, x1, 4):
                sl.d.point((xx, int(y)), fill=C["gray"] if sl.t["text"] != "black" else C["silver"])
        sl.text((left - sl.px(8), int(y)), lab, f, "chart_axis", anchor="rm")
    sl.d.line([(left, plot_top), (left, base), (x1, base)], fill=axis, width=max(1, sl.px(2)))
    n = max(1, len(values))
    slot = (x1 - left - depth) / n
    bw = int(slot * 0.58)
    colors = ch.get("colors") or ([SERIES[0]] * n if not ch.get("multicolor", False) else SERIES)
    for i, (lab, v) in enumerate(zip(labels, values)):
        bx = int(left + slot * i + (slot - bw) / 2 + depth / 2)
        h = int((base - plot_top) * v / top)
        cname = colors[i % len(colors)]
        front = (bx, base - h, bx + bw, base)
        dark = {"blue": "navy", "red": "maroon", "lime": "green", "yellow": "olive", "fuchsia": "purple",
                "aqua": "teal", "olive": "black", "purple": "black", "navy": "black", "teal": "black",
                "green": "black", "maroon": "black", "gray": "black", "silver": "gray", "white": "silver",
                "black": "gray"}[cname]
        if h > 0:
            sl.d.polygon([(bx + bw, base), (bx + bw + depth, base - depth), (bx + bw + depth, base - h - depth), (bx + bw, base - h)], fill=C[dark], outline=0)
            sl.d.polygon([(bx, base - h), (bx + depth, base - h - depth), (bx + bw + depth, base - h - depth), (bx + bw, base - h)], fill=C[cname], outline=0)
            sl.d.rectangle(front, fill=C[cname], outline=0)
        sl.text((bx + bw // 2 + depth // 2, base - h - depth - sl.px(4)), fmt_num(v, unit), fv, "chart_axis", anchor="md")
        for j, ln in enumerate(wrap(lab, f, slot - 4)[:2]):
            sl.text((bx + bw // 2, base + sl.px(6) + j * int(f.size * 1.1)), ln, f, "text", anchor="ma")
    sl.footer()


def chart_pie(sl, ch, box):
    x0, y0, x1, y1 = box
    labels, values = ch.get("labels", []), [float(v) for v in ch.get("values", [])]
    unit = ch.get("unit", "")
    total = sum(values) or 1
    r = min((x1 - x0) // 2 - sl.px(40), (y1 - y0) // 2 - sl.px(8))
    cx, cy = x0 + r + sl.px(16), (y0 + y1) // 2
    tilt = sl.px(14)
    colors = ch.get("colors") or SERIES
    dark = {"blue": "navy", "red": "maroon", "lime": "green", "yellow": "olive", "fuchsia": "purple", "aqua": "teal"}
    ell = (cx - r, cy - int(r * 0.62), cx + r, cy + int(r * 0.62))
    # 3D rim: draw the dark pie a few px lower, then the top
    for dy in range(tilt, 0, -1):
        a = -90
        for i, v in enumerate(values):
            sweep = 360 * v / total
            cn = colors[i % len(colors)]
            sl.d.pieslice((ell[0], ell[1] + dy, ell[2], ell[3] + dy), a, a + sweep, fill=C[dark.get(cn, "black")])
            a += sweep
    a = -90
    for i, v in enumerate(values):
        sweep = 360 * v / total
        sl.d.pieslice(ell, a, a + sweep, fill=C[colors[i % len(colors)]], outline=0)
        a += sweep
    # legend
    f = Font.get("sans", sl.px(17))
    lx = cx + r + sl.px(40)
    ly = cy - len(values) * sl.px(30) // 2
    for i, (lab, v) in enumerate(zip(labels, values)):
        sw = sl.px(16)
        sl.d.rectangle((lx, ly + i * sl.px(30), lx + sw, ly + i * sl.px(30) + sw), fill=C[colors[i % len(colors)]], outline=0)
        pct = f" ({100 * v / total:.0f}%)" if not unit else f" ({fmt_num(v, unit)})"
        sl.text((lx + sw + sl.px(10), ly + i * sl.px(30) + sw // 2), f"{lab}{pct}", f, "text", anchor="lm")
    sl.footer()


def layout_table(sl, spec):
    sl.draw_title(spec.get("title", ""))
    rows = [[str(c) for c in r] for r in spec.get("rows", [])]
    if not rows:
        return sl.footer()
    x0, y0, x1, y1 = sl.content
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    header = spec.get("header", True)
    for size in (20, 18, 16, 14, 13, 12):
        f = Font.get("sans", sl.px(size))
        fb = Font.get("sans", sl.px(size), bold=True)
        pad = sl.px(8)
        widths = [max((fb if (header and ri == 0) else f).getlength(r[c]) for ri, r in enumerate(rows)) + 2 * pad for c in range(ncol)]
        rh = int(f.size * 1.6)
        if sum(widths) <= x1 - x0 and rh * len(rows) <= y1 - y0:
            break
    extra = (x1 - x0 - sum(widths)) / ncol if sum(widths) < x1 - x0 else 0
    widths = [w + extra for w in widths]
    on_dark = sl.t["text"] == "white"
    grid = C["silver"] if on_dark else C["black"]
    y = y0
    for ri, r in enumerate(rows):
        x = x0
        is_head = header and ri == 0
        for ci, cell in enumerate(r):
            box = (int(x), y, int(x + widths[ci]), y + rh)
            if is_head:
                sl.d.rectangle(box, fill=C["navy"] if not on_dark else C["yellow"])
            sl.d.rectangle(box, outline=grid)
            colname = ("white" if not on_dark else "black") if is_head else "text"
            numeric = bool(re.fullmatch(r"[-+$€£]?[\d.,]+[%kKmMx]?", cell.strip()))
            if numeric and not is_head:
                sl.text((box[2] - pad, y + rh // 2), cell, f, colname, anchor="rm")
            else:
                sl.text((box[0] + pad, y + rh // 2), cell, fb if is_head else f, colname, anchor="lm")
            x += widths[ci]
        y += rh
    sl.footer()


def layout_image(sl, spec, deck_dir):
    sl.draw_title(spec.get("title", ""))
    x0, y0, x1, y1 = sl.content
    cap = spec.get("caption")
    if cap:
        y1 -= sl.px(30)
    src = Image.open(deck_dir / spec["image"]).convert("RGB")
    src.thumbnail((x1 - x0, y1 - y0), Image.LANCZOS)
    pal = Image.new("P", (1, 1))
    pal.putpalette(PALETTE)
    q = src.quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG)
    px, py = (x0 + x1 - q.width) // 2, (y0 + y1 - q.height) // 2
    sl.img.paste(q, (px, py))
    sl.d.rectangle((px - 1, py - 1, px + q.width, py + q.height), outline=C["black"])
    if cap:
        f = Font.get("sans", sl.px(16), italic=True)
        sl.text(((x0 + x1) // 2, y1 + sl.px(10)), cap, f, "sub", anchor="ma")
    sl.footer()


LAYOUTS = {
    "title": layout_title, "section": layout_section, "bullets": layout_bullets,
    "two-column": layout_two_column, "statement": layout_statement, "chart": layout_chart,
    "table": layout_table, "image": layout_image,
}


def bmp4(img):
    """Encode a 16-colour P image as a 4-bit BMP (half the size of Pillow's 8-bit output)."""
    w, h = img.size
    a = np.asarray(img, dtype=np.uint8)
    if w % 2:
        a = np.pad(a, ((0, 0), (0, 1)))
    packed = (a[:, 0::2] << 4) | a[:, 1::2]
    stride = (packed.shape[1] + 3) & ~3
    rows = np.zeros((h, stride), np.uint8)
    rows[:, : packed.shape[1]] = packed
    pixels = rows[::-1].tobytes()  # bottom-up
    pal = b"".join(bytes((b, g, r, 0)) for _, (r, g, b) in VGA)
    off = 14 + 40 + len(pal)
    return (b"BM" + struct.pack("<IHHI", off + len(pixels), 0, 0, off)
            + struct.pack("<IiiHHIIiiII", 40, w, h, 1, 4, 0, len(pixels), 2835, 2835, 16, 16) + pal + pixels)


def volume_id(title):
    v = re.sub(r"[^A-Z0-9_]", "_", title.upper())[:16].strip("_")  # Joliet: 16 UCS-2 chars
    return v or "SLIDES"


def build(deck_path, out_root):
    deck_path = Path(deck_path)
    deck = json.loads(deck_path.read_text())
    name = deck.get("name") or deck_path.stem
    out = Path(out_root) / name
    (out / "preview").mkdir(parents=True, exist_ok=True)
    for old in (out / "preview").glob("*.png"):
        old.unlink()

    theme = THEMES[deck.get("theme", "teal")]
    w, h = deck.get("resolution", [640, 480])
    slides = deck["slides"]
    if not 0 < len(slides) <= 999:
        sys.exit("a deck needs 1-999 slides")

    if not SHOW_EXE.exists():
        sys.exit(f"missing {SHOW_EXE}; run viewer/build.sh first")

    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=1, joliet=3, vol_ident=volume_id(deck.get("title", name)))

    def add(fname, data):
        iso.add_fp(io.BytesIO(data), len(data), f"/{fname};1", joliet_path=f"/{fname}")

    add("SHOW.EXE", SHOW_EXE.read_bytes())
    add("AUTORUN.INF", b"[autorun]\r\nopen=SHOW.EXE\r\n")

    ini = [f"[deck]", f"title={deck.get('title', name)}", f"slides={len(slides)}",
           f"transition={deck.get('transition', 'none')}", "", "[transitions]"]
    meta = []
    previews = []
    for i, spec in enumerate(slides):
        layout = spec.get("layout", "bullets")
        if layout not in LAYOUTS:
            sys.exit(f"slide {i + 1}: unknown layout '{layout}' (use one of {', '.join(LAYOUTS)})")
        sl = Slide(w, h, theme, deck, i + 1, len(slides))
        if layout == "image":
            layout_image(sl, spec, deck_path.parent)
        else:
            LAYOUTS[layout](sl, spec)
        add(f"SLIDE{i + 1:03d}.BMP", bmp4(sl.img))
        if spec.get("transition"):
            ini.append(f"{i + 1}={spec['transition']}")
        sl.img.convert("RGB").save(out / "preview" / f"slide{i + 1:03d}.png")
        previews.append(sl.img)
        meta.append({"title": spec.get("title") or spec.get("text", "")[:60], "notes": spec.get("notes", "")})
    add("DECK.INI", ("\r\n".join(ini) + "\r\n").encode("latin-1", "replace"))

    buf = io.BytesIO()
    iso.write_fp(buf)
    iso.close()
    (out / "deck.iso").write_bytes(buf.getvalue())
    (out / "deck.json").write_text(json.dumps({
        "name": name, "title": deck.get("title", name), "theme": deck.get("theme", "teal"),
        "resolution": [w, h], "iso": "deck.iso", "isoSize": len(buf.getvalue()), "slides": meta,
    }, indent=2, ensure_ascii=False))

    # contact sheet for quick review
    cols = 4
    tw, th = w // 2, h // 2
    rows = (len(previews) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 8) + 8), (64, 64, 64))
    for i, im in enumerate(previews):
        sheet.paste(im.convert("RGB").resize((tw, th), Image.NEAREST), (8 + i % cols * (tw + 8), 8 + i // cols * (th + 8)))
    sheet.save(out / "preview" / "contact-sheet.png")
    print(f"{out}/deck.iso: {len(slides)} slides, {len(buf.getvalue()) // 1024} KB, theme {deck.get('theme', 'teal')}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("deck", nargs="+")
    ap.add_argument("--out", default=str(ROOT / "public" / "decks"))
    args = ap.parse_args()
    for d in args.deck:
        build(d, args.out)
    # deck list for the player's deck picker
    index = []
    for meta in sorted(Path(args.out).glob("*/deck.json")):
        m = json.loads(meta.read_text())
        index.append({"name": m["name"], "title": m["title"], "slides": len(m["slides"]), "theme": m["theme"]})
    (Path(args.out) / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))
