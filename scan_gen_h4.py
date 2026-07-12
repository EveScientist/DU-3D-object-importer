"""
scan_gen_h4.py — h=4 blob generator.

CONFIRMED FORMULA (verified against all 8 chunks of 188_export):
  h4_scan = h3_scan with each 8-byte FG group expanded to 12 bytes:
    Group 1: [h3_opener][01 01 93 93 93 00 93 93 69 00 00]
    Group 2: [20 01 01 93 69 93 00 93 69 69 00 00]  (constant)
    Group 3: [a3 01 01 69 93 93 00 69 93 69 00 00]  (constant)
    Group 4: [20 01 01 69 69 93 00 69 69 69 00 00]  (constant)
  h4 JSON coord = h3 JSON coord // 2; header chunk_pos = (h3//2)*32
  h4 mat section = h3 mat section (identical)

SCOPE: works for simple constructs where each h4 chunk has exactly 4 FG groups
(i.e., the corresponding h3 scan has exactly 4 FG groups — single-voxel or
simple nx=1,ny=1 blocks). For complex constructs (hollow cubes, large blocks)
the FG group pattern would differ.
"""
import struct
import lz4.block

BLOB_MAGIC = bytes([0xF9, 0xB6, 0x14, 0xFB])

# h4 FG group tail constants (bytes after opener for each group)
_H4_G1_TAIL = bytes([0x01, 0x01, 0x93, 0x93, 0x93, 0x00, 0x93, 0x93, 0x69, 0x00, 0x00])
_H4_G2_FULL = bytes([0x20, 0x01, 0x01, 0x93, 0x69, 0x93, 0x00, 0x93, 0x69, 0x69, 0x00, 0x00])
_H4_G3_FULL = bytes([0xa3, 0x01, 0x01, 0x69, 0x93, 0x93, 0x00, 0x69, 0x93, 0x69, 0x00, 0x00])
_H4_G4_FULL = bytes([0x20, 0x01, 0x01, 0x69, 0x69, 0x93, 0x00, 0x69, 0x69, 0x69, 0x00, 0x00])
_H4_CONST_GROUPS = [_H4_G2_FULL, _H4_G3_FULL, _H4_G4_FULL]


def h3_scan_to_h4_scan(h3_scan: bytes) -> bytes:
    """
    Convert an h3 scan to an h4 scan by expanding each 8-byte FG group to 12 bytes.
    FG groups are identified by: even byte != 0x00/0xff AND odd byte == 0x01.
    Group 1 opener is preserved from the h3 scan; groups 2-4 use fixed constants.
    """
    pairs = [(h3_scan[i*2], h3_scan[i*2+1]) for i in range(len(h3_scan)//2)]
    fg_pair_indices = [i for i, (b0, b1) in enumerate(pairs)
                       if b0 not in (0x00, 0xff) and b1 == 0x01]

    h4 = bytearray()
    byte_i = 0
    fg_idx = 0

    while byte_i < len(h3_scan):
        if fg_idx < len(fg_pair_indices) and byte_i == fg_pair_indices[fg_idx] * 2:
            opener = h3_scan[byte_i]
            if fg_idx == 0:
                h4.extend(bytes([opener]) + _H4_G1_TAIL)
            else:
                h4.extend(_H4_CONST_GROUPS[min(fg_idx - 1, 2)])
            byte_i += 8  # skip 8 h3 bytes (4 pairs)
            fg_idx += 1
        else:
            h4.append(h3_scan[byte_i])
            byte_i += 1

    return bytes(h4)


def make_h4_header(cx3: int, cy3: int, cz3: int) -> bytes:
    """
    Build 64-byte h4 chunk header.
    h4 JSON coord = h3 coord // 2; h4 header chunk_pos = (cx3//2)*32.
    Verified: 188_export h3 ∈{1,2} → h3//2 = h3-1 (both give 0 or 1).
              122_export h3 ∈{0..3} → h3//2 ∈{0,1} matches observed h4 range.
    """
    CHUNK = 32
    chunk_x = (cx3 // 2) * CHUNK
    chunk_y = (cy3 // 2) * CHUNK
    chunk_z = (cz3 // 2) * CHUNK
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


def make_h4_blob(cx3: int, cy3: int, cz3: int,
                 h3_scan: bytes, h3_mat: bytes) -> bytes:
    """
    Generate h4 blob from h3 scan and mat section.

    cx3/cy3/cz3: h3 chunk coordinates (not h4).
    h3_scan: the raw h3 scan bytes (from the corresponding h3 blob).
    h3_mat: the 40-byte h3 material section (copied verbatim to h4).

    Returns: complete h4 blob bytes (ready to base64-encode for blueprint JSON).
    """
    hdr = make_h4_header(cx3, cy3, cz3)
    h4_scan = h3_scan_to_h4_scan(h3_scan)
    mat = h3_mat
    payload = hdr + h4_scan + mat
    compressed = lz4.block.compress(payload, store_size=False)
    return BLOB_MAGIC + struct.pack('<I', len(payload)) + b'\x00\x00\x00\x00' + compressed


def h4_chunk_coords(cx3: int, cy3: int, cz3: int):
    """Return h4 chunk JSON coords from h3 chunk coords. Formula: h4 = h3 // 2."""
    return cx3 // 2, cy3 // 2, cz3 // 2


if __name__ == '__main__':
    import base64, json

    print("=== Verifying h4 generator against 188_export ===")

    with open('/home/du/export/188_export.blueprint') as f:
        bp = json.load(f)

    def decode_blob(b64):
        import lz4.block, struct
        raw = base64.b64decode(b64)
        unc = struct.unpack('<I', raw[4:8])[0]
        return lz4.block.decompress(raw[12:], uncompressed_size=unc)

    # Build h4-to-h3 mapping
    h3_chunks = {}
    for c in bp['VoxelData']:
        if c['h'] == 3:
            cx, cy, cz = c['x']['$numberLong'], c['y']['$numberLong'], c['z']['$numberLong']
            h3_chunks[(cx, cy, cz)] = c

    all_pass = True
    for c4 in bp['VoxelData']:
        if c4['h'] != 4:
            continue
        cx4, cy4, cz4 = c4['x']['$numberLong'], c4['y']['$numberLong'], c4['z']['$numberLong']

        # Find corresponding h3 chunk
        cx3, cy3, cz3 = None, None, None
        for (x3, y3, z3) in h3_chunks:
            if (2*cx4 <= x3 <= 2*cx4+1 and
                2*cy4 <= y3 <= 2*cy4+1 and
                2*cz4 <= z3 <= 2*cz4+1):
                cx3, cy3, cz3 = x3, y3, z3
                break

        if cx3 is None:
            print(f"  h4({cx4},{cy4},{cz4}): no h3 found")
            continue

        h3_raw = decode_blob(h3_chunks[(cx3,cy3,cz3)]['records']['voxel']['data']['$binary'])
        h3_scan = h3_raw[64:-40]
        h3_mat = h3_raw[-40:]

        gen_blob = make_h4_blob(cx3, cy3, cz3, h3_scan, h3_mat)
        ref_raw = decode_blob(c4['records']['voxel']['data']['$binary'])
        gen_raw = lz4.block.decompress(gen_blob[12:],
                                       uncompressed_size=struct.unpack('<I', gen_blob[4:8])[0])

        diffs = [(i, gen_raw[i], ref_raw[i]) for i in range(min(len(gen_raw), len(ref_raw)))
                 if gen_raw[i] != ref_raw[i]]
        len_ok = len(gen_raw) == len(ref_raw)
        ok = not diffs and len_ok
        all_pass = all_pass and ok
        status = f"✓ ({len(gen_raw)}B)" if ok else f"✗ {len(diffs)} diffs ({len(gen_raw)} vs {len(ref_raw)})"
        print(f"  h4({cx4},{cy4},{cz4}) from h3({cx3},{cy3},{cz3}): {status}")

    print(f"\n{'ALL PASS ✓' if all_pass else 'SOME FAIL ✗'}")
