#!/usr/bin/env python3
"""
Single, reusable decoder for the true 3-axis-corner h3 chunks.
Replaces all the ad-hoc one-off scripts used during the corner-case
investigation with one carefully-checked implementation, so every claim
made in h3_lowrow_scanners.md about (1,1,1)/(1,1,2)/(1,2,1)/(1,2,2)/
(2,1,1)/(2,1,2)/(2,2,1)/(2,2,2) can be re-verified in one consistent pass.
"""
import json
import base64
import lz4.block


def decode_chunk(path, h, cx, cy, cz):
    with open(path) as f:
        bp = json.load(f)
    for entry in bp['VoxelData']:
        if (entry['h'] == h and entry['x']['$numberLong'] == cx
                and entry['y']['$numberLong'] == cy and entry['z']['$numberLong'] == cz):
            vraw = base64.b64decode(entry['records']['voxel']['data']['$binary'])
            dec = lz4.block.decompress(vraw[12:], uncompressed_size=int.from_bytes(vraw[4:8], 'little'))
            idx = dec.find(b'Debug1')
            return dec[64:idx - 13], int.from_bytes(dec[idx - 13:idx - 9], 'little')
    return None, None


def find_pos1(scan):
    n = len(scan)
    for i in range(n):
        if scan[i] != (0x00 if i % 2 == 0 else 0xff):
            return i
    return None


def find_gs(scan, lme_true):
    n = len(scan)
    for i in range(lme_true, n):
        if scan[i] != (0x00 if i % 2 == 0 else 0xff):
            return i
    return None


def is_valid_hb(scan, i):
    n = len(scan)
    return (i + 8 <= n and scan[i + 1] == 1 and scan[i + 3] == 0x7e and scan[i + 4] == 0x7e
            and scan[i + 5] == 0x7e and scan[i + 2] == scan[i + 6] and scan[i + 7] == 0)


def find_first_real_hb(scan, gs):
    """Proper forward search -- never skip this, it's the step that was
    previously skipped by mistake and produced a false-positive 'extra HB'."""
    n = len(scan)
    is_type_a = scan[gs + 1] == 1
    start = gs if is_type_a else gs + 2
    i = start
    while i + 8 <= n:
        if is_valid_hb(scan, i):
            return i, is_type_a, i - start
        i += 1
    return None, is_type_a, None


def split_sections(scan, first_hb_pos):
    """Split the groups region into sections separated by 8-byte
    [255,0,255,0,255,0,255,0] background runs. Trailing all-zero-length
    entries (pure background) are dropped from the returned list."""
    n = len(scan)
    sep = bytes([255, 0, 255, 0, 255, 0, 255, 0])
    sections = []
    cur_start = first_hb_pos
    j = first_hb_pos
    while j < n:
        if bytes(scan[j:j + 8]) == sep:
            sections.append((cur_start, j - cur_start, list(scan[cur_start:j])))
            j += 8
            cur_start = j
        else:
            j += 1
    if cur_start < n:
        sections.append((cur_start, n - cur_start, list(scan[cur_start:n])))
    # drop trailing zero-length / pure-background sections
    while sections and (sections[-1][1] == 0 or all(
            b == (255 if k % 2 == 0 else 0) for k, b in enumerate(sections[-1][2]))):
        sections.pop()
    return sections


def get_own_marker(scan):
    """First marker's value byte (the chunk's own anchor before the groups
    section), found by scanning the whole chunk for the 5-byte
    [val,01,02,N-1,00] pattern."""
    n = len(scan)
    i = 0
    while i + 5 <= n:
        if scan[i + 1] == 0x01 and scan[i + 2] == 0x02 and scan[i + 4] == 0x00:
            return scan[i]
        i += 1
    return None


def analyze(path, cx, cy, cz, ye):
    scan, mc = decode_chunk(path, 3, cx, cy, cz)
    if scan is None:
        return None
    pos1 = find_pos1(scan)
    lme_true = pos1 + 10 * (ye + 1) + 8
    gs = find_gs(scan, lme_true)
    first_hb_pos, is_type_a, gap = find_first_real_hb(scan, gs)
    sections = split_sections(scan, first_hb_pos)
    section_lens = [s[1] for s in sections]
    own_marker = get_own_marker(scan)
    return dict(
        chunk=(cx, cy, cz), ye=ye, mc=mc, mc_mod256=mc % 256, pos1=pos1,
        gs=gs, type_a=is_type_a, gap=gap, first_hb_pos=first_hb_pos,
        own_marker=own_marker, section_lens=section_lens,
        section_opener_vals=[s[2][0] for s in sections],
    )


CHUNKS = [(2, 1, 2), (2, 2, 2), (1, 2, 2), (1, 1, 2), (2, 1, 1), (2, 2, 1), (1, 2, 1), (1, 1, 1)]
TESTS = [
    ('exports/archive/1679_export.blueprint', 1),
    ('exports/1770_export.blueprint', 2),
    ('exports/1772_export.blueprint', 3),
    ('exports/1774_export.blueprint', 4),
]

if __name__ == '__main__':
    import sys
    for path, ye in TESTS:
        print(f'=== {path} (Ye={ye}) ===')
        for c in CHUNKS:
            r = analyze(path, *c, ye)
            print(f'  {c}: pos1={r["pos1"]:>3} type={"A" if r["type_a"] else "B"} '
                  f'gap={r["gap"]:>3} own_marker={r["own_marker"]:>3} '
                  f'sections={r["section_lens"]} openers={r["section_opener_vals"]}')
        print()
