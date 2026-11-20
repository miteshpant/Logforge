"""
TrueType fonts for the PDF writer in reports.py, without a PDF library.

Only what embedding needs is read from the font: the character map
(cmap formats 4 and 12), advance widths (hmtx) and the metrics for the font
descriptor (head, hhea, OS/2). Text is written as 2-byte glyph IDs with the
Identity-H encoding, and a ToUnicode map lets viewers copy and search it.

The fonts are DejaVu Sans, Sans Bold and Sans Mono (assets/fonts, Bitstream
Vera licence): Latin, Greek, Cyrillic and more, but not CJK. A character the
font lacks is drawn as '?'.
"""

from __future__ import annotations

import os
import struct
import zlib
from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")


class TrueTypeFont:
    def __init__(self, name: str, data: bytes):
        self.name, self.data = name, data
        tables = {}
        num = struct.unpack(">H", data[4:6])[0]
        for i in range(num):
            tag, _, offset, length = struct.unpack(">4sIII", data[12 + 16 * i: 28 + 16 * i])
            tables[tag.decode("latin-1")] = (offset, length)
        self._tables = tables
        head = self._table("head")
        self.units_per_em = struct.unpack(">H", head[18:20])[0]
        self.bbox = struct.unpack(">hhhh", head[36:44])
        hhea = self._table("hhea")
        self.ascent, self.descent = struct.unpack(">hh", hhea[4:8])
        n_metrics = struct.unpack(">H", hhea[34:36])[0]
        hmtx = self._table("hmtx")
        self._advances = [struct.unpack(">H", hmtx[4 * i: 4 * i + 2])[0] for i in range(n_metrics)]
        self._cmap = self._read_cmap()

    @classmethod
    @lru_cache(maxsize=None)
    def load(cls, filename: str) -> "TrueTypeFont":
        with open(os.path.join(FONT_DIR, filename), "rb") as f:
            return cls(os.path.splitext(filename)[0].replace("-", ""), f.read())

    def _table(self, tag: str) -> bytes:
        offset, length = self._tables[tag]
        return self.data[offset: offset + length]

    def _read_cmap(self) -> Dict[int, int]:
        cmap = self._table("cmap")
        count = struct.unpack(">H", cmap[2:4])[0]
        subtables = {}
        for i in range(count):
            platform, encoding, offset = struct.unpack(">HHI", cmap[4 + 8 * i: 12 + 8 * i])
            subtables[(platform, encoding)] = offset
        for key in ((3, 10), (0, 4), (3, 1), (0, 3)):
            if key in subtables:
                offset = subtables[key]
                fmt = struct.unpack(">H", cmap[offset: offset + 2])[0]
                if fmt == 12:
                    return self._format12(cmap, offset)
                if fmt == 4:
                    return self._format4(cmap, offset)
        raise ValueError(f"{self.name}: no Unicode cmap")

    @staticmethod
    def _format4(cmap: bytes, offset: int) -> Dict[int, int]:
        seg_x2 = struct.unpack(">H", cmap[offset + 6: offset + 8])[0]
        n = seg_x2 // 2
        ends = struct.unpack(f">{n}H", cmap[offset + 14: offset + 14 + seg_x2])
        starts_at = offset + 16 + seg_x2
        starts = struct.unpack(f">{n}H", cmap[starts_at: starts_at + seg_x2])
        deltas = struct.unpack(f">{n}h", cmap[starts_at + seg_x2: starts_at + 2 * seg_x2])
        ranges_at = starts_at + 2 * seg_x2
        ranges = struct.unpack(f">{n}H", cmap[ranges_at: ranges_at + seg_x2])
        out = {}
        for i in range(n):
            for code in range(starts[i], ends[i] + 1):
                if code == 0xFFFF:
                    continue
                if ranges[i] == 0:
                    gid = (code + deltas[i]) & 0xFFFF
                else:
                    at = ranges_at + 2 * i + ranges[i] + 2 * (code - starts[i])
                    gid = struct.unpack(">H", cmap[at: at + 2])[0]
                    if gid:
                        gid = (gid + deltas[i]) & 0xFFFF
                if gid:
                    out[code] = gid
        return out

    @staticmethod
    def _format12(cmap: bytes, offset: int) -> Dict[int, int]:
        groups = struct.unpack(">I", cmap[offset + 12: offset + 16])[0]
        out = {}
        for g in range(groups):
            start, end, gid = struct.unpack(">III", cmap[offset + 16 + 12 * g: offset + 28 + 12 * g])
            for code in range(start, end + 1):
                out[code] = gid + code - start
        return out

    def glyph(self, char: str) -> int:
        """The glyph ID for a character; 0 (.notdef) if the font lacks it."""
        return self._cmap.get(ord(char), 0)

    def width_1000(self, gid: int) -> int:
        advance = self._advances[min(gid, len(self._advances) - 1)]
        return round(advance * 1000 / self.units_per_em)

    def encode(self, text: str) -> Tuple[str, List[Tuple[int, str]]]:
        """Hex glyph string for a PDF text operator, and the (glyph, char) pairs used."""
        question = self.glyph("?")
        used, out = [], []
        for char in text:
            gid = self.glyph(char) or question
            used.append((gid, char if self.glyph(char) else "?"))
            out.append(f"{gid:04X}")
        return "<" + "".join(out) + ">", used

    # -- PDF objects ----------------------------------------------------------------------

    def pdf_objects(self, add, used: Iterable[Tuple[int, str]]) -> int:
        """Add the font's objects (via add(bytes) -> object number); return the Type0 font's number."""
        glyphs = dict(sorted(set(used)))
        compressed = zlib.compress(self.data)
        file_obj = add(b"<< /Length %d /Length1 %d /Filter /FlateDecode >>\r\nstream\r\n"
                       % (len(compressed), len(self.data)) + compressed + b"\r\nendstream")
        scale = 1000 / self.units_per_em
        x0, y0, x1, y1 = (round(v * scale) for v in self.bbox)
        descriptor = add((f"<< /Type /FontDescriptor /FontName /{self.name} /Flags 32 "
                          f"/FontBBox [{x0} {y0} {x1} {y1}] /ItalicAngle 0 /Ascent {round(self.ascent * scale)} "
                          f"/Descent {round(self.descent * scale)} /CapHeight {round(self.ascent * scale)} "
                          f"/StemV 80 /FontFile2 {file_obj} 0 R >>").encode())
        widths = " ".join(f"{gid} [{self.width_1000(gid)}]" for gid in glyphs)
        cid = add((f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{self.name} "
                   f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
                   f"/FontDescriptor {descriptor} 0 R /CIDToGIDMap /Identity /DW 600 /W [{widths}] >>").encode())
        tounicode = _to_unicode(glyphs)
        to_obj = add(b"<< /Length %d >>\r\nstream\r\n" % len(tounicode) + tounicode + b"\r\nendstream")
        return add((f"<< /Type /Font /Subtype /Type0 /BaseFont /{self.name} /Encoding /Identity-H "
                    f"/DescendantFonts [{cid} 0 R] /ToUnicode {to_obj} 0 R >>").encode())


def _utf16_hex(char: str) -> str:
    return char.encode("utf-16-be").hex().upper()


def _to_unicode(glyphs: Dict[int, str]) -> bytes:
    lines = ["/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
             "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
             "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def",
             "1 begincodespacerange", "<0000> <FFFF>", "endcodespacerange"]
    items = list(glyphs.items())
    for i in range(0, len(items), 100):  # at most 100 entries per block
        chunk = items[i: i + 100]
        lines.append(f"{len(chunk)} beginbfchar")
        lines += [f"<{gid:04X}> <{_utf16_hex(char)}>" for gid, char in chunk]
        lines.append("endbfchar")
    lines += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(lines).encode()


def available() -> bool:
    return all(os.path.exists(os.path.join(FONT_DIR, f)) for f in FONTS.values())


# report style font -> file
FONTS = {"F1": "DejaVuSans.ttf", "F2": "DejaVuSans-Bold.ttf", "F3": "DejaVuSansMono.ttf"}
