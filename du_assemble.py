"""DU blueprint assembler: rebuild a blueprint's h=3 voxel blobs from generated
scans, recomputing per-record hashes. Clones the template envelope verbatim and
substitutes only the voxel data (per import-test guidance)."""
import json, base64, struct, copy, lz4.block
import du_hash

# constant 36-byte material tail after the 4-byte mc (hcCarbon single-material chunk)
MAT_TAIL = bytes.fromhex(
    "00c768690900000000446562756731000001a502b0cb000000006863436172626f6e0201")


def voxel_header(cx, cy, cz):
    h = bytearray(64)
    for off, val in [(0, 0x27B8A013), (4, 6), (8, 0xE881339E), (12, 9),
                     (16, (cx*32-1) & 0xffffffff), (20, (cy*32-1) & 0xffffffff),
                     (24, (cz*32-1) & 0xffffffff), (28, 35), (32, 35), (36, 35),
                     (40, cx*32), (44, cy*32), (48, cz*32), (52, 32), (56, 32), (60, 32)]:
        struct.pack_into('<I', h, off, val)
    return bytes(h)


def _scan_b2(scan):
    """Plateau byte-2 of the scan's first marker (offset lead+2; lead = where the
    leading 00/ff background alternation breaks). The material tail's penultimate
    byte must MATCH it or the mesher rejects the body ('Deserializing invalid
    vertex' -- OCC3 3325 lesson, re-hit by Deployment 11 multi-chunk ramp)."""
    i = 0
    while i < len(scan) and scan[i] == (0 if i % 2 == 0 else 0xff):
        i += 1
    if i + 4 < len(scan) and scan[i + 1] == 1:
        return scan[i + 2]
    return 2


def encode_voxel_b64(cx, cy, cz, scan, mc):
    tail = MAT_TAIL[:-2] + bytes([_scan_b2(scan)]) + MAT_TAIL[-1:]
    blob = voxel_header(cx, cy, cz) + scan + struct.pack('<I', mc) + tail
    comp = lz4.block.compress(blob, store_size=False)
    raw = b'\xf9\xb6\x14\xfb' + struct.pack('<I', len(blob)) + b'\x00\x00\x00\x00' + comp
    return base64.b64encode(raw).decode(), du_hash.to_signed64(du_hash.compute_hash(raw))


def rebuild_h3(template_path, out_path, scan_for):
    """scan_for(cx,cy,cz) -> (scan_bytes, mc) for each h=3 chunk; others cloned."""
    bp = json.load(open(template_path))
    out = copy.deepcopy(bp)
    n = 0
    for entry in out['VoxelData']:
        if entry['h'] != 3:
            continue
        cx, cy, cz = (entry['x']['$numberLong'], entry['y']['$numberLong'],
                      entry['z']['$numberLong'])
        res = scan_for(cx, cy, cz)
        if res is None:
            continue
        scan, mc = res
        b64, h = encode_voxel_b64(cx, cy, cz, scan, mc & 0xff | (mc & ~0xff))
        entry['records']['voxel']['data']['$binary'] = b64
        entry['records']['voxel']['hash']['$numberLong'] = h
        n += 1
    json.dump(out, open(out_path, 'w'))
    return n


def generate_box_blueprint(template_path, out_path,
                           nx_neg=1, nx_pos=1, ny_neg=1, ny_pos=1, nz_neg=1, nz_pos=1):
    """Filled axis-aligned box straddling the origin, given per-axis voxel extents
    (neg/pos voxels from the x=0/y=0/z=0 planes). Reuses the 8-octant corner
    generator: each chunk picks its own side's extent. Clones the template envelope
    (must have the 8 (cx,cy,cz) in {1,2} h3 chunks); DU regenerates LOD/mesh/meta.

    Validated range: each chunk may have AT MOST ONE saturated neg side (so e.g.
    nx_neg=2 with ny_neg=nz_neg=1 is fine; symmetric >=2 neg on multiple axes hits
    the not-yet-derived combined neg-saturation)."""
    import h3_generator as _g

    def scan_for(cx, cy, cz):
        return _g.generate_corner_crossing_scan(
            (cx, cy, cz), neg_cols=nx_neg, pos_cols=nx_pos,
            neg_y=ny_neg, pos_y=ny_pos, neg_z=nz_neg, pos_z=nz_pos)
    return rebuild_h3(template_path, out_path, scan_for)
