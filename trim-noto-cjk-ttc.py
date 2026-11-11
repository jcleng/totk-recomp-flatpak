#!/usr/bin/env python3
"""Trim noto-cjk's NotoSansCJK.ttc down to the faces this package actually uses.

Why this exists
---------------
Upstream's Linux game build looks the CJK font up **by file name** at fixed paths
(`runtime/platform/linux.c`, `plat_font_path`), the first candidate being
`/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc`. The file we ship therefore has to be a
TrueType collection called exactly `NotoSansCJK-Regular.ttc`. The release archive
`00_NotoSansCJK.ttc.zip` from notofonts does provide that name, but its `NotoSansCJK.ttc` holds
45 faces (5 languages x 7 weights, plus the mono faces) and is 112 MB. Only the five Regular faces
are ever useful here.

Which faces are kept
--------------------
The five `Noto Sans CJK <lang> Regular` faces: JP, KR, SC, TC, HK. They share one CFF table (a
pan-CJK outline set -- the faces differ only in which variant glyph their `cmap` maps a shared
codepoint to), so keeping all five costs one `cmap` table each, about 16 MB in total instead of
112 MB, and still covers every CJK text the package can show: `zh-Hans` picks the SC face,
`zh-Hant` the TC face, `ko` the KR face, `ja` the JP face, and fontconfig exposes each as its own
family, which is what the `60-totk-cjk.conf` aliases prefer `Noto Sans CJK SC` from.

Bold is dropped on purpose: it is another ~16 MB of CFF for one face, and Tk synthesises a bold
face from Regular when it cannot find one, so the four bold labels of the installer window (the
title, the run header, the running step and the finish title) still stand out.

Why this does not use fontTools
-------------------------------
The Flatpak SDK's python3 is whatever the runtime ships and is not guaranteed to carry fontTools,
and this module runs inside the build sandbox. A TTC is a simple container -- a header, one offset
per face, then an sfnt table directory per face whose records point into the file -- so copying the
table payloads of the faces we keep and re-pointing the records is a few dozen lines of `struct`
work with no dependencies.

Usage
-----
    python3 trim-noto-cjk-ttc.py NotoSansCJK.ttc NotoSansCJK-Regular.ttc

Exits non-zero if a face this package needs is missing, or if the kept faces cannot map a character
from every CJK language the release has text in: a silent fallback to tofu is exactly the bug this
file exists to prevent, so it must fail the build rather than the user.

Layout reference: OpenType spec, "Font Collections" (TTC) and "Organization of an OpenType Font".
"""
import struct
import sys

# The faces to keep, as (family, subfamily) of the English name records.
KEEP = [
    ('Noto Sans CJK JP', 'Regular'),
    ('Noto Sans CJK KR', 'Regular'),
    ('Noto Sans CJK SC', 'Regular'),
    ('Noto Sans CJK TC', 'Regular'),
    ('Noto Sans CJK HK', 'Regular'),
]

# One character per script the release has text in, plus the CJK punctuation the Chinese strings use.
# zh-Hans: 设置 (installer/text/zh-Hans.json), zh-Hant: 設定, ja: 日本語, ko: 한국어.
# The status glyphs (U+25CB, U+25B6, U+2714, U+2716...) are deliberately *not* checked here: those
# come from DejaVu, which the release already bundles, and noto-cjk has no U+2716 at all.
REQUIRED = '设置設定日本語한국어　「」，。…'

TTC_TAG = b'ttcf'
# sfnt versions a font file head may declare: TrueType outlines, CFF outlines, and the two Apple ones.
SFNT_VERSIONS = (b'\x00\x01\x00\x00', b'OTTO', b'true', b'typ1')


def read_u16(b, o):
    return struct.unpack_from('>H', b, o)[0]


def read_u32(b, o):
    return struct.unpack_from('>I', b, o)[0]


class Face:
    """One face of a collection: its table directory plus the absolute file offset of each table."""

    def __init__(self, data, edge, index):
        self.index = index
        self.sfnt_version = data[edge:edge + 4]
        if self.sfnt_version not in SFNT_VERSIONS:
            raise ValueError(f'face {index}: not an sfnt at offset {edge} (version {self.sfnt_version!r})')
        self.num_tables = read_u16(data, edge + 4)
        self.tables = []      # (tag, checksum, absolute offset, length)
        for i in range(self.num_tables):
            rec = edge + 12 + 16 * i
            tag = data[rec:rec + 4]
            checksum = read_u32(data, rec + 4)
            offset = read_u32(data, rec + 8)
            length = read_u32(data, rec + 12)
            self.tables.append((tag, checksum, offset, length))

    def table(self, tag):
        for t in self.tables:
            if t[0] == tag:
                return t
        return None

    def name(self, data, name_id):
        """The first Windows/Unicode English name record with `name_id`, or ''."""
        t = self.table(b'name')
        if not t:
            return ''
        _, _, base, length = t
        count = read_u16(data, base + 2)
        strings = base + read_u16(data, base + 4)
        found = ''
        for i in range(count):
            rec = base + 6 + 12 * i
            platform, encoding, language, this_id = struct.unpack_from('>HHHH', data, rec)
            size, offset = struct.unpack_from('>HH', data, rec + 8)
            if this_id != name_id or platform != 3 or encoding != 1:
                continue
            raw = data[strings + offset:strings + offset + size]
            text = raw.decode('utf-16-be', 'replace')
            # 0x409 is en-US; anything else is a hint that an English name exists further on.
            if language == 0x409:
                return text
            found = found or text
        return found

    def codepoints(self, data):
        """The characters of the best Unicode cmap subtable, as a set of codepoints."""
        t = self.table(b'cmap')
        if not t:
            return set()
        _, _, base, _ = t
        count = read_u16(data, base + 2)
        best = None
        for i in range(count):
            rec = base + 4 + 8 * i
            platform, encoding = struct.unpack_from('>HH', data, rec)
            offset = base + read_u32(data, rec + 4)
            fmt = read_u16(data, offset)
            # Prefer a full-repertoire Unicode subtable: 3/10 (UCS-4) and 0/4, then 3/1 and 0/3.
            rank = {(3, 10): 4, (0, 4): 4, (3, 1): 3, (0, 3): 3, (0, 6): 3}.get((platform, encoding), 0)
            if rank and fmt in (4, 12) and (best is None or rank > best[0]):
                best = (rank, fmt, offset)
        if best is None:
            return set()
        _, fmt, offset = best
        chars = set()
        if fmt == 4:
            seg_x2 = read_u16(data, offset + 6)
            segs = seg_x2 // 2
            ends = offset + 14
            starts = ends + seg_x2 + 2
            for s in range(segs):
                start, end = read_u16(data, starts + 2 * s), read_u16(data, ends + 2 * s)
                if start <= end:
                    chars.update(range(start, end + 1))
        else:   # fmt == 12
            groups = read_u32(data, offset + 12)
            for g in range(groups):
                rec = offset + 16 + 12 * g
                start, end = read_u32(data, rec), read_u32(data, rec + 4)
                if end >= start:
                    chars.update(range(start, end + 1))
        return chars


def parse_collection(data):
    if data[:4] != TTC_TAG:
        raise ValueError(f'not a font collection (tag {data[:4]!r}); pass the NotoSansCJK.ttc inside the zip')
    num_fonts = read_u32(data, 8)
    offsets = struct.unpack_from(f'>{num_fonts}I', data, 12)
    return [Face(data, offsets[i], i) for i in range(num_fonts)]


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    src, dst = argv[1], argv[2]

    with open(src, 'rb') as f:
        data = f.read()
    faces = parse_collection(data)
    print(f'{src}: {len(faces)} faces, {len(data)} bytes')

    by_name = {}
    for face in faces:
        key = (face.name(data, 1), face.name(data, 2))     # family, subfamily
        by_name.setdefault(key, face)

    missing = [f'{fam} {sub}' for fam, sub in KEEP if (fam, sub) not in by_name]
    if missing:
        sys.exit(f'{src}: missing faces: {missing}')

    kept = [by_name[(fam, sub)] for fam, sub in KEEP]
    for face in kept:
        chars = face.codepoints(data)
        absent = [c for c in REQUIRED if ord(c) not in chars]
        if absent:
            sys.exit(f'{face.name(data, 1)} {face.name(data, 2)}: no glyph for {absent!r}')
        print(f'  keep {face.name(data, 1)} {face.name(data, 2)}: {len(chars)} chars')

    out = bytearray()
    # Header: tag, version 1.0, numFonts, then one offset per face. The table directories come
    # straight after, so the offsets are filled in once their sizes are known.
    out += TTC_TAG + struct.pack('>II', 0x00010000, len(kept))
    header_len = 12 + 4 * len(kept)
    dir_len = sum(12 + 16 * face.num_tables for face in kept)
    payload_start = header_len + dir_len
    # Payloads are shared by content: the five faces point at one CFF table, and copying it once keeps
    # the result near 16 MB instead of 35 MB. Keyed by (offset, length) in the source, which is the
    # identity the collection itself uses for sharing.
    payload = bytearray()
    placed = {}
    dirs = []
    for face in kept:
        records = []
        for tag, checksum, offset, length in face.tables:
            key = (offset, length)
            if key not in placed:
                placed[key] = payload_start + len(payload)
                chunk = data[offset:offset + length]
                payload += chunk
                # Table records must be 4-byte aligned; pad between tables, not inside one.
                payload += b'\0' * (-len(payload) % 4)
            records.append((tag, checksum, placed[key], length))
        # Table directories must be sorted by tag (they already are in the source, but do not rely on it).
        records.sort(key=lambda r: r[0])
        dirs.append((face.sfnt_version, records))

    out += b''.join(struct.pack('>I', header_len + sum(12 + 16 * f.num_tables for f in kept[:i]))
                    for i in range(len(kept)))
    assert len(out) == header_len, (len(out), header_len)
    for sfnt_version, records in dirs:
        out += sfnt_version + struct.pack('>HHHH', len(records), 0, 0, 0)
        for tag, checksum, offset, length in records:
            out += tag + struct.pack('>III', checksum, offset, length)
    assert len(out) == payload_start, (len(out), payload_start)
    out += payload

    with open(dst, 'wb') as f:
        f.write(out)
    print(f'{dst}: {len(kept)} faces, {len(out)} bytes')


if __name__ == '__main__':
    main(sys.argv)
