#!/usr/bin/env python3
"""
compare_export.py
Decode an in-game-exported blueprint and compare vs our generator output.

Usage:
    python3 compare_export.py <export.blueprint> --voxel gx,gy,gz [--mat hcSodium]

Where gx,gy,gz are in-game coordinates (e.g. -0.5,-0.5,-0.5 or 0.5,0.5,0.5).
All valid in-game coords end in .5 and are within -31.5 to +30.5.

The script finds the h=3 chunk that contains the voxel, decodes its scan,
prints annotated hex, and generates our expected scan for side-by-side diff.
"""

import argparse, base64, json, struct, sys
import lz4.block

CHUNK_SIZE = 32
BLOB_MAGIC = bytes([0xF9, 0xB6, 0x14, 0xFB])

MATERIALS_INFO = {
    'hcSodium': (bytes.fromhex('69670374'), b'hcSodium', 249, 1),
    'hcCarbon': (bytes.fromhex('a502b0cb'), b'hcCarbon', 179, 9),
    'hcAlLiPa': (bytes.fromhex('c60fb674'), b'hcAlLiPa',  12, 12),
}


def game_to_voxel(gx, gy, gz):
    """Convert in-game float coords to absolute voxel indices."""
    ax = round(gx + 63.5)
    ay = round(gy + 63.5)
    az = round(gz + 63.5)
    return ax, ay, az


def voxel_to_chunk_local(ax, ay, az):
    cx, lx = divmod(ax, CHUNK_SIZE)
    cy, ly = divmod(ay, CHUNK_SIZE)
    cz, lz = divmod(az, CHUNK_SIZE)
    return (cx, cy, cz), (lx, ly, lz)


def decompress_blob(b64_data):
    raw = base64.b64decode(b64_data)
    assert raw[:4] == BLOB_MAGIC, f"Bad magic: {raw[:4].hex()}"
    unc_size = struct.unpack('<I', raw[4:8])[0]
    data = lz4.block.decompress(raw[12:], uncompressed_size=unc_size)
    return data


def split_scan_mat(body):
    """body = everything after 64B header. Returns (scan_bytes, mat_bytes)."""
    mat = body[-40:]
    scan = body[:-40]
    return scan, mat


def parse_scan_pairs(scan):
    """Return list of (hi, lo) byte pairs."""
    pairs = []
    for i in range(0, len(scan), 2):
        pairs.append((scan[i], scan[i+1]))
    return pairs


def _n1_first(lx, ly, lz):
    lz_eff = 32 if (lz == 0 and (lx > 0 or ly > 0)) else lz
    return 4 + (153 * lx + 4 * ly + lz_eff) // 31


def _get_n(lx, ly, lz):
    Wx = 1 if lx == 0 else 0
    Wy = 1 if ly == 0 else 0
    Wz = 1 if lz == 0 else 0
    return (4 - Wx - 3 * Wy - Wz) % 8


def predict_scan_params(lx, ly, lz, base_corner):
    n = _get_n(lx, ly, lz)
    CV = (32 * n + base_corner) % 256
    n1_first = _n1_first(lx, ly, lz)
    gap = 162 if n in (4, 7) else 163
    if n1_first == 4 and (CV + 19) % 256 != 0xff:
        n1_first = 9
    FG_START = n1_first + 3 + gap
    marker_val = (120 - CV) % 256
    marker_pair = gap + 7
    G1_OPENER = (CV + 19) % 256
    if G1_OPENER == 0xff:
        G1_OPENER = marker_val
    ftr_marker = G1_OPENER if marker_pair >= FG_START else marker_val
    ftr_val = 512 + ftr_marker
    trailing = (166 if n in (4, 7) else 167) - n1_first
    return dict(n=n, CV=CV, n1_first=n1_first, gap=gap, FG_START=FG_START,
                marker_val=marker_val, marker_pair=marker_pair, G1_OPENER=G1_OPENER,
                ftr_marker=ftr_marker, ftr_val=ftr_val, trailing=trailing)


def annotate_scan(pairs, p, label="ACTUAL"):
    """Print annotated scan pairs with structural markers."""
    n1 = p['n1_first']
    decl_end = n1 + 5  # 5 pairs for single-voxel decl (3 decl + 2 compact)
    gap_start = n1 + 3  # after 3 decl pairs
    fg_start = p['FG_START']
    marker_pair = p['marker_pair']
    fg_end = fg_start + 20  # Z1(8p) + gap(4p) + Z0(8p) for N=1 → 20 pairs

    print(f"\n{'='*60}")
    print(f"{label} SCAN — {len(pairs)} pairs")
    print(f"  n={p['n']} CV=0x{p['CV']:02x}={p['CV']} n1_first={n1}")
    print(f"  gap={p['gap']} FG_START={fg_start}")
    print(f"  marker_val=0x{p['marker_val']:02x} at pair {marker_pair}")
    print(f"  G1_OPENER=0x{p['G1_OPENER']:02x}")
    print(f"  ftr_marker=0x{p['ftr_marker']:02x} ftr_val={p['ftr_val']}")
    print(f"  trailing={p['trailing']}")
    print(f"{'='*60}")

    def zone(i):
        if i < n1:
            return "PRE  "
        elif i < n1 + 3:
            return "DECL "
        elif i < n1 + 5:
            return "DCMP "
        elif i < fg_start:
            z = "GAP  "
            if i == marker_pair:
                z = "MARK "
            return z
        elif i < fg_end:
            offset = i - fg_start
            if offset < 8:
                return "FGZ1 "
            elif offset < 12:
                return "FGGAP"
            else:
                return "FGZ0 "
        else:
            return "TAIL "

    prev_zone = None
    for i, (hi, lo) in enumerate(pairs):
        z = zone(i)
        if z != prev_zone:
            print(f"  --- {z.strip()} (pair {i}) ---")
            prev_zone = z
        marker = ""
        if i == n1:
            marker = f" ← n1_first (expected 00 {p['CV']:02x})"
        elif i == marker_pair and z.strip() == "MARK":
            marker = f" ← marker (expected {p['marker_val']:02x} 00)"
        elif i == fg_start:
            marker = f" ← FG_START G1 (expected {p['G1_OPENER']:02x} 01)"
        print(f"  [{i:4d}] {hi:02x} {lo:02x}{marker}")


def diff_scan(pairs_actual, pairs_expected, p_act, p_exp):
    """Show byte-level differences between actual and expected scans."""
    print(f"\n{'='*60}")
    print("DIFF — actual vs expected (only differing pairs)")
    print(f"{'='*60}")

    max_len = max(len(pairs_actual), len(pairs_expected))
    diffs = 0
    for i in range(max_len):
        a = pairs_actual[i] if i < len(pairs_actual) else None
        e = pairs_expected[i] if i < len(pairs_expected) else None
        if a != e:
            a_str = f"{a[0]:02x}{a[1]:02x}" if a else "----"
            e_str = f"{e[0]:02x}{e[1]:02x}" if e else "----"
            print(f"  pair {i:4d}: actual={a_str}  expected={e_str}")
            diffs += 1

    if diffs == 0:
        print("  PERFECT MATCH — no differences!")
    else:
        print(f"\n  Total differing pairs: {diffs} / {max_len}")


def build_expected_scan(lx, ly, lz, base_corner):
    """Build our generator's expected scan bytes for a single-voxel chunk."""
    n = _get_n(lx, ly, lz)
    CV = (32 * n + base_corner) % 256
    n1_first = _n1_first(lx, ly, lz)
    gap = 162 if n in (4, 7) else 163
    if n1_first == 4 and (CV + 19) % 256 != 0xff:
        n1_first = 9
    FG_START = n1_first + 3 + gap
    marker_val = (120 - CV) % 256
    marker_pair = gap + 7
    G1_OPENER = (CV + 19) % 256
    if G1_OPENER == 0xff:
        G1_OPENER = marker_val

    FG_Z1 = bytes([G1_OPENER, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00,
                   0x20, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00])
    FG_Z0 = bytes([0xa3, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00,
                   0x20, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00])
    fg_bytes = FG_Z1 + bytes([0xff, 0x00] * 4) + FG_Z0
    fg_pairs = len(fg_bytes) // 2  # 20 pairs

    trailing = (166 if n in (4, 7) else 167) - n1_first
    total_pairs = FG_START + fg_pairs + trailing
    scan = bytearray(total_pairs * 2)

    for i in range(n1_first):
        scan[i*2] = 0x00; scan[i*2+1] = 0xff

    decl = bytes([0x00, CV, 0x01, 2, 0x00, 0x00])
    dstart = n1_first * 2
    scan[dstart:dstart+6] = decl

    for i in range(n1_first + 3, FG_START):
        scan[i*2] = 0xff; scan[i*2+1] = 0x00

    if marker_pair < FG_START and marker_val != 0xFF:
        scan[marker_pair*2] = marker_val
        scan[marker_pair*2+1] = 0x00

    fg_start_byte = FG_START * 2
    scan[fg_start_byte:fg_start_byte+len(fg_bytes)] = fg_bytes

    for i in range(FG_START + fg_pairs, total_pairs):
        scan[i*2] = 0xff; scan[i*2+1] = 0x00

    return bytes(scan)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('blueprint', help='Exported .blueprint or .json file')
    ap.add_argument('--voxel', required=True,
                    help='In-game coords as gx,gy,gz e.g. -0.5,-0.5,-0.5')
    ap.add_argument('--mat', default='hcSodium',
                    choices=list(MATERIALS_INFO.keys()))
    ap.add_argument('--dump-all-chunks', action='store_true',
                    help='Print summary of all h=3 chunks in the blueprint')
    args = ap.parse_args()

    gx, gy, gz = [float(x) for x in args.voxel.split(',')]
    ax, ay, az = game_to_voxel(gx, gy, gz)
    (cx, cy, cz), (lx, ly, lz) = voxel_to_chunk_local(ax, ay, az)
    base_corner = MATERIALS_INFO[args.mat][2]

    print(f"In-game: ({gx}, {gy}, {gz})")
    print(f"Voxel abs: ({ax}, {ay}, {az})")
    print(f"Chunk: ({cx}, {cy}, {cz}), local: ({lx}, {ly}, {lz})")
    print(f"Material: {args.mat} (base_corner={base_corner})")

    with open(args.blueprint) as f:
        bp = json.load(f)

    voxel_data = bp.get('VoxelData', [])

    if args.dump_all_chunks:
        print(f"\nAll VoxelData entries ({len(voxel_data)} total):")
        for vd in voxel_data:
            h = vd.get('h', '?')
            xc = vd.get('x', {}).get('$numberLong', '?')
            yc = vd.get('y', {}).get('$numberLong', '?')
            zc = vd.get('z', {}).get('$numberLong', '?')
            print(f"  h={h} chunk=({xc},{yc},{zc})")

    # Find matching h=3 entry
    match = None
    for vd in voxel_data:
        if vd.get('h') != 3:
            continue
        xc = vd.get('x', {}).get('$numberLong')
        yc = vd.get('y', {}).get('$numberLong')
        zc = vd.get('z', {}).get('$numberLong')
        if (xc, yc, zc) == (cx, cy, cz):
            match = vd
            break

    if match is None:
        print(f"\nERROR: No h=3 entry found at chunk ({cx},{cy},{cz})")
        print("Available h=3 chunks:")
        for vd in voxel_data:
            if vd.get('h') == 3:
                xc = vd.get('x', {}).get('$numberLong')
                yc = vd.get('y', {}).get('$numberLong')
                zc = vd.get('z', {}).get('$numberLong')
                print(f"  ({xc},{yc},{zc})")
        sys.exit(1)

    print(f"\nFound h=3 chunk at ({cx},{cy},{cz})")

    # Decode voxel blob
    voxel_b64 = match['records']['voxel']['data']['$binary']
    body = decompress_blob(voxel_b64)
    print(f"Decompressed body: {len(body)} bytes  (header=64, scan={len(body)-104}B, mat=40)")

    header = body[:64]
    scan_bytes, mat_bytes = split_scan_mat(body[64:])
    pairs_actual = parse_scan_pairs(scan_bytes)

    # Material section layout (40B):
    # [0]    ftr_marker byte (= ftr_val - 512)
    # [1:5]  count (uint32LE, always 2)
    # [5:22] Record 1 (Debug1): hash4 + pad4 + name8 + local_id1
    # [22:39] Record 2 (material): hash4 + pad4 + name8 + local_id1
    # [39]   trailing 0x01
    ftr_val_actual = struct.unpack('<I', mat_bytes[0:4])[0]
    mat2_hash = mat_bytes[22:26]
    mat2_name = mat_bytes[30:38].rstrip(b'\x00').decode('ascii', errors='replace')
    print(f"\nMaterial section:")
    print(f"  ftr_val (actual):   {ftr_val_actual}  (= 512 + {ftr_val_actual - 512} = 512 + 0x{ftr_val_actual-512:02x})")
    print(f"  mat2 hash (actual): {mat2_hash.hex()}")
    print(f"  mat2 name (actual): {mat2_name}")
    known_hash = MATERIALS_INFO[args.mat][0]
    if mat2_hash == known_hash:
        print(f"  Hash MATCHES our {args.mat} definition ✓")
    else:
        print(f"  Hash MISMATCH — our {args.mat} has {known_hash.hex()}, game has {mat2_hash.hex()}")

    # Predicted params
    p = predict_scan_params(lx, ly, lz, base_corner)
    print(f"\nPredicted params:")
    for k, v in p.items():
        if isinstance(v, int) and v < 256:
            print(f"  {k:15s} = {v}  (0x{v:02x})")
        else:
            print(f"  {k:15s} = {v}")

    # ftr_val comparison
    if ftr_val_actual == p['ftr_val']:
        print(f"\nftr_val: MATCH ({ftr_val_actual}) ✓")
    else:
        print(f"\nftr_val MISMATCH: actual={ftr_val_actual} predicted={p['ftr_val']}")

    # Build expected scan
    expected_scan = build_expected_scan(lx, ly, lz, base_corner)
    pairs_expected = parse_scan_pairs(expected_scan)

    # Annotate actual scan (using predicted structural params)
    annotate_scan(pairs_actual, p, "ACTUAL (from game export)")

    # Build predicted params for expected annotation
    annotate_scan(pairs_expected, p, "EXPECTED (our generator)")

    # Diff
    diff_scan(pairs_actual, pairs_expected, p, p)

    # Raw hex of actual mat section for future reference
    print(f"\nActual mat section (40B hex):")
    print(f"  {mat_bytes.hex()}")

    # First declaration pair in actual scan
    n1 = p['n1_first']
    if n1 < len(pairs_actual):
        hi, lo = pairs_actual[n1]
        print(f"\nActual declaration byte at pair {n1}: 0x{hi:02x} 0x{lo:02x}")
        if hi == 0x00:
            cv_found = lo
            expected_cv = p['CV']
            if cv_found == expected_cv:
                print(f"  CV byte: 0x{cv_found:02x} = {cv_found} — MATCHES predicted ✓")
            else:
                cv_n = (cv_found - base_corner) % 256
                print(f"  CV byte: 0x{cv_found:02x} = {cv_found} — MISMATCH (predicted 0x{expected_cv:02x})")
                print(f"  Actual CV implies: (cv - base_corner)%256 = {cv_n} mod 8 = {cv_n % 32}")
        else:
            print(f"  Not a declaration pair (expected 00 xx) — n1_first prediction wrong?")
            print(f"  Scanning for first 00-XX pair (non-00ff):")
            for i, (h2, l2) in enumerate(pairs_actual):
                if h2 == 0x00 and l2 != 0xff:
                    print(f"    First non-00ff: pair {i} = 00 {l2:02x}  (n1_first guess was {n1})")
                    break


if __name__ == '__main__':
    main()
