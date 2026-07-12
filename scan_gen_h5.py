"""
scan_gen_h5.py — h=5 blob generator.

CONFIRMED FORMULA (verified against 188_export server-corrected h5(0,0,0)):
  h5 scan = independently generated scan based on h4 scan parameters.
  Key relationships (h4 and h5 scans are same length):
    - h4_decl_pair = first non-background pair in h4 scan (e.g. 162 for lx=14)
    - n1_sub1_h5 = h4_decl_pair // 2 + 2  (e.g. 162//2+2 = 83)
    - h5_ftr_val = h4_ftr_val - 48
    - h5_marker = h5_ftr_val - 512
    - h5_G1_opener = h4_G1_opener + 48
    - FG groups at h4_FG_pair_positions - N1S_REF (N1S_REF = (h4_decl_pair-4)//2)
    - Pre-FG marker at EVEN byte of same pair as h4 pre-FG marker; value = h5_marker
    - Declaration at pair n1_sub1_h5: even=00, odd=h5_marker, then (01,02), (00,00)

  h5 header chunk_pos = (h4_coord // 2) * 32 = (cx3 // 4) * 32
  h5 mat = h4 mat but with ftr_val replaced by h5_ftr_val

SCOPE: verified for simple constructs (one h3 per h4 region, h5=single chunk).
"""
import struct
import lz4.block

BLOB_MAGIC = bytes([0xF9, 0xB6, 0x14, 0xFB])

# h5 FG group constants (0x9e=high, 0x5f=low)
_H5_G2_FULL = bytes([0x20, 0x01, 0x01, 0x9e, 0x5f, 0x9e, 0x00, 0x9e, 0x5f, 0x5f, 0x00, 0x00])
_H5_G3_FULL = bytes([0xa3, 0x01, 0x01, 0x5f, 0x9e, 0x9e, 0x00, 0x5f, 0x9e, 0x5f, 0x00, 0x00])
_H5_G4_FULL = bytes([0x20, 0x01, 0x01, 0x5f, 0x5f, 0x9e, 0x00, 0x5f, 0x5f, 0x5f, 0x00, 0x00])
_H5_G1_TAIL = bytes([0x01, 0x01, 0x9e, 0x9e, 0x9e, 0x00, 0x9e, 0x9e, 0x5f, 0x00, 0x00])
_H5_CONST_GROUPS = [_H5_G2_FULL, _H5_G3_FULL, _H5_G4_FULL]

_H5_FTR_DELTA = 48    # h5_ftr_val = h4_ftr_val - 48
_H5_OPENER_DELTA = 48  # h5_G1_opener = h4_G1_opener + 48


def h4_scan_to_h5_scan(h4_scan: bytes, h4_ftr_val: int) -> bytes:
    """
    Generate h5 scan from h4 scan parameters.

    h4_scan: the h4 scan bytes.
    h4_ftr_val: the h4 footer value (= h3 ftr_val = 512 + marker).
    Returns: h5 scan bytes (same length as h4 scan).
    """
    total = len(h4_scan)
    n_pairs = total // 2

    # Find h4 FG groups (same detection as h3_scan_to_h4_scan)
    pairs = [(h4_scan[i*2], h4_scan[i*2+1]) for i in range(n_pairs)]
    h4_fg_pairs = [i for i, (b0, b1) in enumerate(pairs)
                   if b0 not in (0x00, 0xff) and b1 == 0x01]

    if not h4_fg_pairs:
        return h4_scan  # no FG groups found, return as-is

    h4_G1_opener = h4_scan[h4_fg_pairs[0] * 2]
    h5_ftr_val = h4_ftr_val - _H5_FTR_DELTA
    h5_marker = h5_ftr_val - 512
    h5_G1_opener = (h4_G1_opener + _H5_OPENER_DELTA) & 0xFF

    # h4_decl_pair: first non-background pair in h4 scan (declaration position).
    # This is the post-bump value (e.g. 9 for the n1_first=4→9 bump case).
    h4_decl_pair = next((i for i, (b0, b1) in enumerate(pairs)
                         if (b0, b1) not in ((0x00, 0xff), (0xff, 0x00))), 0)
    # CV=0xff h3 scan omits the (00,ff) declaration pair, so h4/h5 start with (01,02)
    # at pair 0. Treat as virtual declaration at pair 4 to preserve N1S_REF=0.
    h4_decl_pair = max(h4_decl_pair, 4)

    # N1S_REF uses the actual (post-bump) h4_decl_pair. FG groups shift left by N1S_REF.
    N1S_REF = (h4_decl_pair - 4) // 2   # e.g. (162-4)//2=79 for 188_export; 2 for bumped n=7

    # h5 FG pairs = h4 FG pairs shifted back by N1S_REF
    h5_fg_pairs = [p - N1S_REF for p in h4_fg_pairs]
    h5_fg_start = h5_fg_pairs[0]

    # Declaration position: h4_decl_pair // 2 + 2 (confirmed formula for all cases).
    n1_sub1_h5 = h4_decl_pair // 2 + 2

    # h5 gap and marker derived from h5 FG and declaration positions.
    h5_gap = h5_fg_start - n1_sub1_h5 - 3
    marker_pair = h5_gap + 7

    # When marker and FG share the same pair (N1S_REF=0, no-bump case), G1_opener
    # must equal h5_marker so the ftr formula (h5_ftr = h4_ftr - 48) remains consistent.
    if marker_pair >= h5_fg_start:
        h5_G1_opener = h5_marker

    # Build h5 scan
    scan = bytearray(total)

    # Phase 1: 00ff background for pairs 0..n1_sub1_h5-1
    for i in range(n1_sub1_h5):
        scan[i*2] = 0x00
        scan[i*2+1] = 0xff

    # Phase 2: declaration at pair n1_sub1_h5
    # Odd byte = h5_marker; followed by (01,02), (00,00)
    decl_start = n1_sub1_h5 * 2 + 1  # odd byte of pair n1_sub1_h5
    decl_bytes = bytes([h5_marker & 0xFF, 0x01, 0x02, 0x00, 0x00])
    for j, b in enumerate(decl_bytes):
        if decl_start + j < total:
            scan[decl_start + j] = b

    # Phase 3: ff00 background from pair n1_sub1_h5+3 onwards
    for i in range(n1_sub1_h5 + 3, n_pairs):
        scan[i*2] = 0xff
        scan[i*2+1] = 0x00

    # Phase 4: pre-FG marker. Write explicitly when marker_pair < h5_fg_start
    # (when they share the same pair, G1 == h5_marker by the 0xff-fallback path, so implicit is fine)
    if marker_pair < h5_fg_start and 0 <= marker_pair < n_pairs:
        scan[marker_pair * 2] = h5_marker & 0xFF

    # Phase 5: FG groups
    for fg_idx, h5_pair in enumerate(h5_fg_pairs):
        if fg_idx >= 4 or h5_pair * 2 + 12 > total:
            continue
        byte_pos = h5_pair * 2
        if fg_idx == 0:
            scan[byte_pos:byte_pos+12] = bytes([h5_G1_opener]) + _H5_G1_TAIL
        else:
            scan[byte_pos:byte_pos+12] = _H5_CONST_GROUPS[min(fg_idx-1, 2)]

    return bytes(scan)


def make_h5_header(cx3: int, cy3: int, cz3: int) -> bytes:
    """
    Build 64-byte h5 chunk header.
    h5 JSON coord = h3 coord // 4; header chunk_pos = (cx3//4)*32.
    """
    CHUNK = 32
    chunk_x = (cx3 // 4) * CHUNK
    chunk_y = (cy3 // 4) * CHUNK
    chunk_z = (cz3 // 4) * CHUNK
    h = bytearray(64)
    vals = [666411027, 6, 3900781470, 9,
            (chunk_x - 1) & 0xFFFFFFFF,
            (chunk_y - 1) & 0xFFFFFFFF,
            (chunk_z - 1) & 0xFFFFFFFF,
            CHUNK + 3, CHUNK + 3, CHUNK + 3,
            chunk_x, chunk_y, chunk_z,
            CHUNK, CHUNK, CHUNK]
    for i, v in enumerate(vals):
        struct.pack_into('<I', h, i * 4, v)
    return bytes(h)


def h5_mat_from_h4(h4_mat: bytes, h4_ftr_val: int) -> bytes:
    """Build h5 mat section from h4 mat: replace ftr_val with h5_ftr_val."""
    h5_ftr_val = h4_ftr_val - _H5_FTR_DELTA
    mat = bytearray(h4_mat)
    struct.pack_into('<I', mat, 0, h5_ftr_val)
    return bytes(mat)


def make_h5_blob(cx3: int, cy3: int, cz3: int,
                 h4_scan: bytes, h4_mat: bytes) -> bytes:
    """
    Generate h5 blob from h4 scan and mat section.

    cx3/cy3/cz3: one of the h3 chunk coordinates in this h5 region.
    h4_scan: scan from the corresponding h4 blob.
    h4_mat: mat from the corresponding h4 blob (= h3 mat).
    """
    h4_ftr_val = struct.unpack('<I', h4_mat[:4])[0]
    hdr = make_h5_header(cx3, cy3, cz3)
    h5_scan = h4_scan_to_h5_scan(h4_scan, h4_ftr_val)
    h5_mat = h5_mat_from_h4(h4_mat, h4_ftr_val)
    payload = hdr + h5_scan + h5_mat
    compressed = lz4.block.compress(payload, store_size=False)
    return BLOB_MAGIC + struct.pack('<I', len(payload)) + b'\x00\x00\x00\x00' + compressed


def h5_chunk_coords(cx3: int, cy3: int, cz3: int):
    """Return h5 chunk JSON coords from h3 chunk coords. Formula: h5 = h3 // 4."""
    return cx3 // 4, cy3 // 4, cz3 // 4


if __name__ == '__main__':
    import base64, json

    print("=== Verifying h5 generator against 188_export ===")

    with open('/home/du/export/188_export.blueprint') as f:
        bp = json.load(f)

    def decode_blob(b64):
        raw = base64.b64decode(b64)
        unc = struct.unpack('<I', raw[4:8])[0]
        return lz4.block.decompress(raw[12:], uncompressed_size=unc)

    # Use server-corrected blobs (h4 and h5 from migration)
    H4_00_B64 = "+bYU+zYDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAA/wEARCMAAAAEAAgCABcgBAAvAP8CAP8xRYwBAgBHARXsCgAPAgD/IPYHnwEBk5OTAJOTaQAAIAEBk2mTAJNpaVwBg6MBAWmTkwBpIABYaWmTAGkgAIDsAgAAAMdoaQoD4ABEZWJ1ZzEAAAHGD7Z0AAOgaGNBbExpUGECAQ=="
    H5_SRV_B64 = "+bYU+zYDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAA/wEARCMAAAAEAAgCABcgBAAvAP8CAJJPvAECAKkAkj//ALyoAIr2B88BAZ6engCenl8AACABAZ5fngCeX19cAYOjAQFfnp4AXyAAWF9fngBfIAAPAgCLgLwCAAAAx2hpCgPgAERlYnVnMQAAAcYPtnQAA6BoY0FsTGlQYQIB"

    h4_raw = decode_blob(H4_00_B64)
    h4_scan = h4_raw[64:-40]
    h4_mat = h4_raw[-40:]

    gen_h5 = make_h5_blob(1, 1, 1, h4_scan, h4_mat)
    gen_unc = struct.unpack('<I', gen_h5[4:8])[0]
    gen_raw = lz4.block.decompress(gen_h5[12:], uncompressed_size=gen_unc)

    srv_h5_raw = decode_blob(H5_SRV_B64)

    diffs = [(i, gen_raw[i], srv_h5_raw[i]) for i in range(min(len(gen_raw), len(srv_h5_raw)))
             if gen_raw[i] != srv_h5_raw[i]]
    len_ok = len(gen_raw) == len(srv_h5_raw)
    ok = not diffs and len_ok

    print(f"h5(0,0,0) from h4(0,0,0): {'✓' if ok else f'✗ {len(diffs)} diffs (gen={len(gen_raw)} srv={len(srv_h5_raw)})'}")
    if diffs:
        for i, g, s in diffs[:10]:
            region = "header" if i<64 else ("mat" if i>=len(gen_raw)-40 else "scan")
            pi = (i - 64) // 2 if i >= 64 else 0
            print(f"  byte {i} (scan pair {pi}, {region}): gen=0x{g:02x} srv=0x{s:02x}")
