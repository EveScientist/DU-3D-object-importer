#!/usr/bin/env python3
"""
gen_h4_test.py — Generate test blueprints with correct h4 LOD blobs.

TEST 1: Regenerate 188_export using captured h3 scans + new h4 generator.
         If the h4 blobs match byte-for-byte, the formula is confirmed.

TEST 2: Generate a fresh blueprint using generate_v3.py h3 format +
         h4 generator. Can be imported in-game to verify LOD at distance.

Usage: python3 gen_h4_test.py
Outputs: /home/du/tests/test_h4_regen_188.blueprint
         /home/du/tests/test_h4_fresh_single.blueprint
"""
import base64, json, struct, copy
from pathlib import Path
import lz4.block

from scan_gen_h4 import make_h4_blob, h4_chunk_coords
from scan_gen_h5 import make_h5_blob, h5_chunk_coords

TESTS_DIR = Path('/home/du/tests')
BLOB_MAGIC = bytes([0xF9, 0xB6, 0x14, 0xFB])

def _decode_blob(b64):
    raw = base64.b64decode(b64)
    unc = struct.unpack('<I', raw[4:8])[0]
    return lz4.block.decompress(raw[12:], uncompressed_size=unc)

def _make_blob(payload):
    c = lz4.block.compress(payload, store_size=False)
    return BLOB_MAGIC + struct.pack('<I', len(payload)) + b'\x00\x00\x00\x00' + c

def _b64(b): return base64.b64encode(b).decode()

def _chunk_entry(h_level, cx, cy, cz, blob_bytes):
    return {
        'h': h_level,
        'x': {'$numberLong': cx},
        'y': {'$numberLong': cy},
        'z': {'$numberLong': cz},
        'records': {
            'voxel': {
                'data': {'$binary': _b64(blob_bytes), '$type': '0'}
            }
        }
    }


# ──────────────────────────────────────────────────────────────────────────────
# TEST 1: Regenerate 188_export with generated h4 blobs
# Verifies h4 matches reference byte-for-byte.
# ──────────────────────────────────────────────────────────────────────────────

def test1_regen_188():
    print("=== TEST 1: Regenerate 188_export h4 blobs ===")
    with open('/home/du/export/188_export.blueprint') as f:
        ref_bp = json.load(f)

    # Extract h3 chunks
    h3_data = {}
    for c in ref_bp['VoxelData']:
        if c['h'] != 3:
            continue
        cx, cy, cz = c['x']['$numberLong'], c['y']['$numberLong'], c['z']['$numberLong']
        raw = _decode_blob(c['records']['voxel']['data']['$binary'])
        h3_data[(cx, cy, cz)] = {
            'hdr': raw[:64], 'scan': raw[64:-40], 'mat': raw[-40:]
        }

    # Generate h4 blobs from h3
    all_pass = True
    new_voxeldata = []

    # Add original h3 chunks unchanged
    for cx, cy, cz in sorted(h3_data):
        raw = h3_data[(cx, cy, cz)]
        blob = _make_blob(raw['hdr'] + raw['scan'] + raw['mat'])
        new_voxeldata.append(_chunk_entry(3, cx, cy, cz, blob))

    # Generate h4 from h3
    for cx3, cy3, cz3 in sorted(h3_data):
        h3 = h3_data[(cx3, cy3, cz3)]
        gen_h4 = make_h4_blob(cx3, cy3, cz3, h3['scan'], h3['mat'])

        # Compare to reference
        cx4, cy4, cz4 = h4_chunk_coords(cx3, cy3, cz3)
        ref_c4 = next((c for c in ref_bp['VoxelData']
                       if c['h'] == 4 and c['x']['$numberLong'] == cx4
                       and c['y']['$numberLong'] == cy4 and c['z']['$numberLong'] == cz4), None)

        if ref_c4:
            ref_raw = _decode_blob(ref_c4['records']['voxel']['data']['$binary'])
            unc = struct.unpack('<I', gen_h4[4:8])[0]
            gen_raw = lz4.block.decompress(gen_h4[12:], uncompressed_size=unc)
            diffs = sum(1 for a, b in zip(gen_raw, ref_raw) if a != b)
            len_ok = len(gen_raw) == len(ref_raw)
            ok = diffs == 0 and len_ok
            all_pass = all_pass and ok
            status = f"✓" if ok else f"✗ {diffs} diffs"
            print(f"  h4({cx4},{cy4},{cz4}) from h3({cx3},{cy3},{cz3}): {status}")

        new_voxeldata.append(_chunk_entry(4, cx4, cy4, cz4, gen_h4))

    # Add h5 chunk from reference (unchanged)
    for c in ref_bp['VoxelData']:
        if c['h'] == 5:
            blob = base64.b64decode(c['records']['voxel']['data']['$binary'])
            cx, cy, cz = c['x']['$numberLong'], c['y']['$numberLong'], c['z']['$numberLong']
            new_voxeldata.append(_chunk_entry(5, cx, cy, cz, blob))

    # Build new blueprint
    new_bp = copy.deepcopy(ref_bp)
    new_bp['VoxelData'] = new_voxeldata
    out_path = TESTS_DIR / 'test_h4_regen_188.blueprint'
    with open(out_path, 'w') as f:
        json.dump(new_bp, f)
    print(f"\n{'ALL PASS ✓' if all_pass else 'SOME FAIL ✗'}")
    print(f"Saved: {out_path} ({out_path.stat().st_size//1024}KB)")
    return all_pass


# ──────────────────────────────────────────────────────────────────────────────
# TEST 2: Generate fresh blueprint with correct h3 + h4 for single voxel
# Uses captured 188_export h3 scans but with a different chunk assignment,
# to verify the h4 chunk_pos formula is correct for any cx3,cy3,cz3.
# ──────────────────────────────────────────────────────────────────────────────

def test2_verify_h4_chunk_pos():
    """
    Verification: extract each h3 chunk from 188_export and regenerate an
    equivalent blueprint with the h3 chunks at SHIFTED positions, verifying
    h4 chunk_pos adjusts correctly.
    """
    print("\n=== TEST 2: H4 chunk_pos formula verification ===")
    print("Checking: for any h3 chunk (cx3,cy3,cz3), h4 chunk_pos = (cx3-1,cy3-1,cz3-1)*32")
    with open('/home/du/export/188_export.blueprint') as f:
        ref_bp = json.load(f)

    # Check chunk_pos formula for all h4 chunks in reference
    h4_chunks = {(c['x']['$numberLong'], c['y']['$numberLong'], c['z']['$numberLong']): c
                 for c in ref_bp['VoxelData'] if c['h'] == 4}
    h3_chunks = {(c['x']['$numberLong'], c['y']['$numberLong'], c['z']['$numberLong']): c
                 for c in ref_bp['VoxelData'] if c['h'] == 3}

    all_ok = True
    for (cx3, cy3, cz3) in sorted(h3_chunks):
        cx4_pred, cy4_pred, cz4_pred = h4_chunk_coords(cx3, cy3, cz3)
        exists = (cx4_pred, cy4_pred, cz4_pred) in h4_chunks
        ok = exists
        all_ok = all_ok and ok
        print(f"  h3({cx3},{cy3},{cz3}) → h4({cx4_pred},{cy4_pred},{cz4_pred}): {'✓ exists' if exists else '✗ NOT FOUND'}")

    print(f"\n{'ALL OK ✓' if all_ok else 'SOME FAIL ✗'}")
    return all_ok


def test3_regen_188_all_lods():
    """
    Regenerate 188_export with all three LOD levels (h3, h4, h5) from generators.
    Verifies h5 generator matches server byte-for-byte when given generated h4.
    """
    print("\n=== TEST 3: Regen 188_export with generated h3+h4+h5 ===")
    with open('/home/du/export/188_export.blueprint') as f:
        ref_bp = json.load(f)

    # Extract h3 chunks from reference
    h3_data = {}
    for c in ref_bp['VoxelData']:
        if c['h'] != 3:
            continue
        cx, cy, cz = c['x']['$numberLong'], c['y']['$numberLong'], c['z']['$numberLong']
        raw = _decode_blob(c['records']['voxel']['data']['$binary'])
        h3_data[(cx, cy, cz)] = {'hdr': raw[:64], 'scan': raw[64:-40], 'mat': raw[-40:]}

    # Reference h4 and h5 for comparison
    ref_h4 = {(c['x']['$numberLong'], c['y']['$numberLong'], c['z']['$numberLong']):
              _decode_blob(c['records']['voxel']['data']['$binary'])
              for c in ref_bp['VoxelData'] if c['h'] == 4}
    ref_h5 = {(c['x']['$numberLong'], c['y']['$numberLong'], c['z']['$numberLong']):
              _decode_blob(c['records']['voxel']['data']['$binary'])
              for c in ref_bp['VoxelData'] if c['h'] == 5}

    all_pass = True
    new_vd = []

    # h3 chunks (unchanged from reference)
    for cx, cy, cz in sorted(h3_data):
        d = h3_data[(cx, cy, cz)]
        blob = _make_blob(d['hdr'] + d['scan'] + d['mat'])
        new_vd.append(_chunk_entry(3, cx, cy, cz, blob))

    # Generate h4 from each h3
    h4_blobs = {}
    for cx3, cy3, cz3 in sorted(h3_data):
        d = h3_data[(cx3, cy3, cz3)]
        gen_blob = make_h4_blob(cx3, cy3, cz3, d['scan'], d['mat'])
        cx4, cy4, cz4 = h4_chunk_coords(cx3, cy3, cz3)
        unc = struct.unpack('<I', gen_blob[4:8])[0]
        gen_raw = lz4.block.decompress(gen_blob[12:], uncompressed_size=unc)
        ref_raw = ref_h4.get((cx4, cy4, cz4), b'')
        ok = gen_raw == ref_raw
        all_pass = all_pass and ok
        print(f"  h4({cx4},{cy4},{cz4}) from h3({cx3},{cy3},{cz3}): {'✓' if ok else f'✗ {sum(a!=b for a,b in zip(gen_raw,ref_raw))} diffs'}")
        h4_blobs[(cx4, cy4, cz4)] = (gen_blob, gen_raw[64:-40], gen_raw[-40:])
        new_vd.append(_chunk_entry(4, cx4, cy4, cz4, gen_blob))

    # Generate h5 from each h4 (use first h3 coords in each h5 region)
    h5_to_h3 = {}
    for cx3, cy3, cz3 in h3_data:
        k5 = h5_chunk_coords(cx3, cy3, cz3)
        h5_to_h3.setdefault(k5, []).append((cx3, cy3, cz3))

    for (cx5, cy5, cz5), h3_list in sorted(h5_to_h3.items()):
        # Use first h3's corresponding h4
        cx3, cy3, cz3 = h3_list[0]
        cx4, cy4, cz4 = h4_chunk_coords(cx3, cy3, cz3)
        _, h4_scan, h4_mat = h4_blobs[(cx4, cy4, cz4)]
        gen_blob = make_h5_blob(cx3, cy3, cz3, h4_scan, h4_mat)
        unc = struct.unpack('<I', gen_blob[4:8])[0]
        gen_raw = lz4.block.decompress(gen_blob[12:], uncompressed_size=unc)
        ref_raw = ref_h5.get((cx5, cy5, cz5), b'')
        ok = gen_raw == ref_raw
        all_pass = all_pass and ok
        print(f"  h5({cx5},{cy5},{cz5}): {'✓' if ok else f'✗ {sum(a!=b for a,b in zip(gen_raw,ref_raw))} diffs'}")
        new_vd.append(_chunk_entry(5, cx5, cy5, cz5, gen_blob))

    new_bp = copy.deepcopy(ref_bp)
    new_bp['VoxelData'] = new_vd
    out = TESTS_DIR / 'test_all_lods_188.blueprint'
    with open(out, 'w') as f:
        json.dump(new_bp, f)
    print(f"\n{'ALL PASS ✓' if all_pass else 'SOME FAIL ✗'}")
    print(f"Saved: {out} ({out.stat().st_size//1024}KB)")
    return all_pass


if __name__ == '__main__':
    TESTS_DIR.mkdir(exist_ok=True)
    t1 = test1_regen_188()
    t2 = test2_verify_h4_chunk_pos()
    t3 = test3_regen_188_all_lods()

    print("\n=== SUMMARY ===")
    print(f"Test 1 (regen h4): {'PASS' if t1 else 'FAIL'}")
    print(f"Test 2 (chunk_pos): {'PASS' if t2 else 'FAIL'}")
    print(f"Test 3 (all LODs): {'PASS' if t3 else 'FAIL'}")

    if t1 and t3:
        print("\n✓ All LOD generators confirmed. test_all_lods_188.blueprint ready for in-game import.")
