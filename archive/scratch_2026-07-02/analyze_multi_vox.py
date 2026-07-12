#!/usr/bin/env python3
"""
Comprehensive analysis of multi-voxel blueprint scan encoding.
Analyzes F through M blueprints.
"""
import json, base64, lz4.block, struct
from pathlib import Path

def decomp(b64):
    raw = base64.b64decode(b64)
    sz = struct.unpack('<I', raw[4:8])[0]
    return lz4.block.decompress(raw[12:], uncompressed_size=sz)

def load_bp(name):
    path = f'/home/du/export/{name}'
    with open(path) as f:
        return json.load(f)

def get_A(cz):
    return [0x01, 0x21, 0x20, 0x00][cz % 4]

def find_decl_pattern(pairs):
    """Find all declaration patterns: (00,X),(01,02),(Y,00) where Y != ff, X != ff, X != 00"""
    decls = []
    for i in range(len(pairs)-2):
        a0,a1 = pairs[i]
        b0,b1 = pairs[i+1]
        c0,c1 = pairs[i+2]
        if (a0 == 0x00 and a1 not in (0x00, 0xff) and
            b0 == 0x01 and b1 == 0x02 and
            c1 == 0x00 and c0 not in (0xff,)):
            decls.append((i, a1, c0))  # (pair_index, CV, decl_end_byte)
    return decls

def find_fg_pattern(pairs, A):
    """Find face group starts: (FX,01),(A,7e),(7e,7e),(A,00)"""
    fgs = []
    i = 0
    while i < len(pairs)-3:
        a0,a1 = pairs[i]
        b0,b1 = pairs[i+1]
        c0,c1 = pairs[i+2]
        d0,d1 = pairs[i+3]
        if a1 == 0x01 and b0 == A and b1 == 0x7e and c0 == 0x7e and c1 == 0x7e and d0 == A and d1 == 0x00:
            fgs.append((i, a0))
            i += 4  # skip past this FG to avoid double-counting
        else:
            i += 1
    return fgs

def find_leading_run(pairs):
    """Find length of leading (00,ff) run"""
    for i, (a, b) in enumerate(pairs):
        if a != 0x00 or b != 0xff:
            return i
    return len(pairs)

def find_trailing_run(pairs):
    """Find where trailing (ff,00) run starts"""
    for i in range(len(pairs)-1, -1, -1):
        if pairs[i] != (0xff, 0x00):
            return i+1
    return 0

def analyze_chunk(vdata, cx, cy, cz, chunk_label=""):
    A = get_A(cz)
    header = vdata[:64]
    scan_bytes_data = vdata[64:-40]
    mat = vdata[-40:]

    n_pairs = len(scan_bytes_data) // 2
    pairs = [(scan_bytes_data[i*2], scan_bytes_data[i*2+1]) for i in range(n_pairs)]

    print(f"\n{'='*80}")
    print(f"CHUNK {chunk_label} at ({cx},{cy},{cz}), A=0x{A:02x}")
    print(f"Total scan pairs: {n_pairs}")
    print(f"Header (hex): {header.hex()}")

    leading = find_leading_run(pairs)
    trailing_start = find_trailing_run(pairs)
    decls = find_decl_pattern(pairs)
    fgs = find_fg_pattern(pairs, A)

    print(f"Leading (00,ff) run: {leading} pairs (0..{leading-1})")
    print(f"Trailing (ff,00) run: starts at pair {trailing_start} ({n_pairs-trailing_start} pairs)")
    print(f"Middle section: pairs {leading}..{trailing_start-1} ({trailing_start-leading} pairs)")

    print(f"\nDeclaration patterns found ({len(decls)}):")
    for idx, cv, de in decls:
        print(f"  [{idx:4d}] (00,{cv:02x}),(01,02),({de:02x},00) — CV=0x{cv:02x} decl_end=0x{de:02x}")

    print(f"\nFace group patterns found ({len(fgs)}):")
    for i, (idx, fx) in enumerate(fgs):
        fg_pairs = pairs[idx:idx+8]
        fg_str = ' '.join(f'({p[0]:02x},{p[1]:02x})' for p in fg_pairs)
        print(f"  FG{i+1} at pair {idx}: FX=0x{fx:02x} → {fg_str}")

    # Group FGs into groups of 2 (each voxel has 2 blocks of 4 pairs × 2 face groups)
    # Actually each "FG block" is 8 pairs (2 face groups × 4 pairs)
    # But we need to figure out the grouping from the data
    # Let's look at FG spacing
    if len(fgs) >= 2:
        print(f"\nFG spacing: ", end="")
        for i in range(1, len(fgs)):
            print(f"{fgs[i][0]-fgs[i-1][0]}", end="  ")
        print()

    # Relationship between first decl (n1) and FG1
    if decls and fgs:
        n1_first = decls[0][0]
        fg1 = fgs[0][0]
        print(f"\nFirst decl (n1_first) = {n1_first}")
        print(f"FG1 position = {fg1}")
        print(f"FG1 - n1_first = {fg1 - n1_first}")
        print(f"leading = {leading}")
        print(f"FG1 - leading = {fg1 - leading}")

    # Check region between decls and FG1 for non-trivial pairs
    if decls and fgs:
        last_decl_pair_idx = decls[-1][0] + 2  # index of (Y,00) pair
        first_fg_idx = fgs[0][0]
        mid_start = last_decl_pair_idx + 1
        print(f"\nRegion from after last decl (pair {mid_start}) to FG1 (pair {first_fg_idx}):")
        for j in range(mid_start, first_fg_idx):
            p = pairs[j]
            if p != (0xff, 0x00):
                print(f"  [{j:4d}] ({p[0]:02x},{p[1]:02x}) *** NON-FF00 ***")

    # Annotated full scan - print ALL pairs with labels
    print(f"\n--- Full annotated scan ---")

    # Build annotation map
    ann = {}
    for j in range(n_pairs):
        if j < leading:
            ann[j] = "lead"
        elif j >= trailing_start:
            ann[j] = "trail"

    for di, cv, de in decls:
        ann[di]   = f"DECL_A  CV={cv:02x}"
        ann[di+1] = f"DECL_B"
        ann[di+2] = f"DECL_C  de={de:02x}"

    for fg_i, (idx, fx) in enumerate(fgs):
        for k in range(4):
            if idx+k < n_pairs:
                ann[idx+k] = f"FG{fg_i+1}.{k}"

    # Now print — compress long runs of same annotation
    last_ann = None
    run_start = 0
    run_count = 0
    run_val = None

    def flush_run():
        nonlocal last_ann, run_start, run_count, run_val
        if run_count > 0:
            if run_count <= 3:
                for jj in range(run_start, run_start+run_count):
                    p = pairs[jj]
                    a = ann.get(jj, "")
                    print(f"  [{jj:4d}] ({p[0]:02x},{p[1]:02x})  {a}")
            else:
                # print first, ellipsis, last
                jj = run_start
                p = pairs[jj]
                a = ann.get(jj, "")
                print(f"  [{jj:4d}] ({p[0]:02x},{p[1]:02x})  {a}")
                if run_count > 2:
                    print(f"         ... {run_count-2} more ...")
                jj = run_start + run_count - 1
                p = pairs[jj]
                a = ann.get(jj, "")
                print(f"  [{jj:4d}] ({p[0]:02x},{p[1]:02x})  {a}")
        run_count = 0

    prev_compressed_ann = None
    i = 0
    while i < n_pairs:
        p = pairs[i]
        a = ann.get(i, "")
        cur_ann = a if a else f"({p[0]:02x},{p[1]:02x})"

        # Always print DECL and FG pairs uncompressed
        is_special = any(tag in a for tag in ['DECL', 'FG', 'NON', 'NOTABLE'])
        if is_special:
            if run_count > 0:
                flush_run()
                run_count = 0
                prev_compressed_ann = None
            print(f"  [{i:4d}] ({p[0]:02x},{p[1]:02x})  {a}")
        elif cur_ann == prev_compressed_ann:
            run_count += 1
        else:
            if run_count > 0:
                flush_run()
            run_start = i
            run_count = 1
            run_val = p
            prev_compressed_ann = cur_ann

        i += 1

    if run_count > 0:
        flush_run()

    return {
        'n_pairs': n_pairs,
        'leading': leading,
        'trailing_start': trailing_start,
        'decls': decls,
        'fgs': fgs,
        'A': A,
    }

def process_all():
    targets = [
        'F_2vox_diff_n1.blueprint',
        'G_4vox_diff_n1.blueprint',
        'H_2vox_same_n1.blueprint',
        'I_4vox_same_n1.blueprint',
        'J_8vox.blueprint',
        'K_16vox.blueprint',
        'L_64vox.blueprint',
        'M_layer.blueprint',
    ]

    all_results = {}

    for fname in targets:
        print(f"\n\n{'#'*80}")
        print(f"### FILE: {fname}")
        bp = load_bp(fname)

        voxel_entries = bp.get('VoxelData', [])
        print(f"Found {len(voxel_entries)} VoxelData entries")

        file_results = []
        for entry in voxel_entries:
            h = entry.get('h', -1)
            x = entry.get('x', {}).get('$numberLong', entry.get('x', 0))
            y = entry.get('y', {}).get('$numberLong', entry.get('y', 0))
            z = entry.get('z', {}).get('$numberLong', entry.get('z', 0))

            # cx,cy,cz are the chunk coords
            cx = int(x) if not isinstance(x, dict) else int(x.get('$numberLong', 0))
            cy = int(y) if not isinstance(y, dict) else int(y.get('$numberLong', 0))
            cz = int(z) if not isinstance(z, dict) else int(z.get('$numberLong', 0))

            if h != 3:
                print(f"  Skipping h={h} chunk at ({cx},{cy},{cz})")
                continue

            voxel_record = entry.get('records', {}).get('voxel', {})
            data_obj = voxel_record.get('data', {})
            b64 = data_obj.get('$binary', '')
            if not b64:
                print(f"  No binary data for chunk ({cx},{cy},{cz})")
                continue

            try:
                vdata = decomp(b64)
            except Exception as e:
                print(f"  Decomp error for chunk ({cx},{cy},{cz}): {e}")
                continue

            label = f"{fname.replace('.blueprint','')} ({cx},{cy},{cz})"
            result = analyze_chunk(vdata, cx, cy, cz, label)
            file_results.append((cx, cy, cz, result))

        all_results[fname] = file_results

    return all_results

if __name__ == '__main__':
    results = process_all()

    print(f"\n\n{'#'*80}")
    print("### SUMMARY TABLE")
    print(f"{'File':<30} {'Chunk':<15} {'n_pairs':>8} {'leading':>8} {'#decls':>7} {'#FGs':>5} {'FG1':>6} {'FG1-n1':>7}")
    print("-"*90)
    for fname, chunks in results.items():
        short = fname.replace('.blueprint','')
        for cx, cy, cz, r in chunks:
            n1 = r['decls'][0][0] if r['decls'] else '?'
            fg1 = r['fgs'][0][0] if r['fgs'] else '?'
            fg1_minus_n1 = (fg1 - n1) if isinstance(n1, int) and isinstance(fg1, int) else '?'
            print(f"{short:<30} ({cx},{cy},{cz}):{'':>5} {r['n_pairs']:>8} {r['leading']:>8} {len(r['decls']):>7} {len(r['fgs']):>5} {str(fg1):>6} {str(fg1_minus_n1):>7}")
