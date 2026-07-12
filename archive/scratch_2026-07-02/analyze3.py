#!/usr/bin/env python3
"""
Byte-level analysis of multi-voxel blueprints F-M.
The scan is indexed by BYTES, not pairs.
Key structures (in bytes):
  - Leading: 00 ff 00 ff ... (2-byte pairs)
  - Decl: 00 CV 01 02 00 00  (starting at byte 2*n1)
  - XX00 marker: some value at byte offset 169*2 = 338
  - FG block (8 bytes each): FX 01 7e 7e 7e 01 00 A  repeated (2 FGs per face group block)
  - The face group pattern we see: FX 01 7e 7e 7e 01 00 A
"""
import json, base64, lz4.block, struct

def decomp(b64):
    raw = base64.b64decode(b64)
    sz = struct.unpack('<I', raw[4:8])[0]
    return lz4.block.decompress(raw[12:], uncompressed_size=sz)

def load_bp(name):
    with open(f'/home/du/export/{name}') as f:
        return json.load(f)

def get_chunk_data(bp, h_filter=3):
    chunks = []
    for entry in bp.get('VoxelData', []):
        h = entry.get('h', -1)
        if h != h_filter: continue
        x = entry.get('x', {}); y = entry.get('y', {}); z = entry.get('z', {})
        cx = int(x.get('$numberLong', x)) if isinstance(x, dict) else int(x)
        cy = int(y.get('$numberLong', y)) if isinstance(y, dict) else int(y)
        cz = int(z.get('$numberLong', z)) if isinstance(z, dict) else int(z)
        b64 = entry.get('records', {}).get('voxel', {}).get('data', {}).get('$binary', '')
        if not b64: continue
        try:
            vdata = decomp(b64)
            chunks.append((cx, cy, cz, vdata))
        except: pass
    return sorted(chunks)

def get_A(cz):
    return [0x01, 0x21, 0x20, 0x00][cz % 4]

def find_decls_bytes(scan):
    """Find declaration sequences: 00 CV 01 02 00 00 (CV not in 00,ff)"""
    decls = []
    for i in range(len(scan)-5):
        if (scan[i] == 0x00 and scan[i+1] not in (0x00, 0xff) and
            scan[i+2] == 0x01 and scan[i+3] == 0x02 and
            scan[i+4] == 0x00 and scan[i+5] == 0x00):
            decls.append((i, scan[i+1]))  # (byte_offset, CV)
    return decls

def find_fg_blocks_bytes(scan, A):
    """
    Face group pattern (8 bytes): FX 01 7e 7e 7e 01 00 A
    Where A = [0x01, 0x21, 0x20, 0x00][cz%4]
    For z_side=0 terminator: FX 01 00 7e 7e 00 00 00
    """
    fgs = []
    i = 0
    while i < len(scan)-7:
        # FX 01 7e 7e 7e 01 00 A  (A = cz-dependent)
        if (scan[i+1] == 0x01 and scan[i+2] == 0x7e and scan[i+3] == 0x7e and
            scan[i+4] == 0x7e and scan[i+5] == 0x01 and scan[i+6] == 0x00):
            fgs.append((i, scan[i], scan[i+7], 'FG'))
            i += 8
        else:
            i += 1
    return fgs

def find_xx00_bytes(scan):
    """Find XX 00 marker: byte that doesn't fit leading/trailing patterns."""
    # Typically at a fixed position (byte 338 = pair 169)
    markers = []
    for i in range(0, len(scan)-1, 2):
        a, b = scan[i], scan[i+1]
        if b == 0x00 and a not in (0x00, 0xff) and a != 0x01:
            # Could be xx00 marker
            markers.append((i, a))
    return markers

def analyze_scan_bytes(scan, cz, label):
    A = get_A(cz)
    n_bytes = len(scan)
    n_pairs = n_bytes // 2

    # Find leading 00 ff run (by BYTES)
    lead_bytes = 0
    while lead_bytes < n_bytes-1 and scan[lead_bytes] == 0x00 and scan[lead_bytes+1] == 0xff:
        lead_bytes += 2
    lead_pairs = lead_bytes // 2

    # Find trailing ff 00 run
    trail_bytes = n_bytes
    while trail_bytes >= 2 and scan[trail_bytes-2] == 0xff and scan[trail_bytes-1] == 0x00:
        trail_bytes -= 2
    trail_pairs = trail_bytes // 2

    decls = find_decls_bytes(scan)
    fgs = find_fg_blocks_bytes(scan, A)

    print(f"\n{'='*70}")
    print(f"CHUNK {label}, cz={cz}, A=0x{A:02x}")
    print(f"Total bytes={n_bytes}, pairs={n_pairs}")
    print(f"Leading: {lead_pairs} pairs ({lead_bytes} bytes, 0..{lead_bytes-1})")
    print(f"Trailing: {n_pairs-trail_pairs} pairs, starts at byte {trail_bytes}")

    print(f"\nDeclarations ({len(decls)}):")
    for off, cv in decls:
        n1 = off // 2  # pair index = byte_offset / 2
        print(f"  byte {off:4d} (pair {n1:3d}): 00 {cv:02x} 01 02 00 00  CV=0x{cv:02x}")

    print(f"\nFace groups ({len(fgs)}):")
    for i, (off, fx, a_val, typ) in enumerate(fgs):
        print(f"  FG{i+1} at byte {off:4d} (pair {off//2:3d}): {fx:02x} 01 7e 7e 7e 01 00 {a_val:02x}  FX=0x{fx:02x} A_val=0x{a_val:02x}")

    if decls and fgs:
        n1_first = decls[0][0] // 2
        fg1_pair = fgs[0][0] // 2
        print(f"\nRelationships:")
        print(f"  n1_first = {n1_first}")
        print(f"  FG1_pair = {fg1_pair}")
        print(f"  FG1 - n1_first = {fg1_pair - n1_first}")
        print(f"  FG1 - lead = {fg1_pair - lead_pairs}")
        if len(decls) > 1:
            n1_second = decls[1][0] // 2
            print(f"  n1_second = {n1_second}")
            print(f"  Decl spacing = {n1_second - n1_first}")
            print(f"  FG1 - n1_second = {fg1_pair - n1_second}")
        if len(fgs) >= 2:
            fg2_pair = fgs[1][0] // 2
            print(f"  FG2_pair = {fg2_pair}")
            print(f"  FG2 - FG1 = {fg2_pair - fg1_pair}")
        if len(fgs) >= 4:
            print(f"  FG3_pair = {fgs[2][0]//2}, FG4_pair = {fgs[3][0]//2}")
            print(f"  FG3-FG1 = {fgs[2][0]//2 - fgs[0][0]//2}, FG4-FG3 = {fgs[3][0]//2 - fgs[2][0]//2}")

    # Highlight all non-trivial bytes
    print(f"\nNon-trivial bytes (not 00ff or ff00):")
    i = 0
    while i < n_bytes - 1:
        a, b = scan[i], scan[i+1]
        if not ((a == 0x00 and b == 0xff) or (a == 0xff and b == 0x00)):
            print(f"  byte {i:4d} (pair {i//2:3d}): {a:02x} {b:02x}")
        i += 2

    return {
        'lead_pairs': lead_pairs,
        'trail_pairs': n_pairs - trail_pairs,
        'n_pairs': n_pairs,
        'decls': decls,
        'fgs': fgs,
        'A': A,
    }

def process_all():
    targets = [
        ('F_2vox_diff_n1.blueprint', 'F'),
        ('G_4vox_diff_n1.blueprint', 'G'),
        ('H_2vox_same_n1.blueprint', 'H'),
        ('I_4vox_same_n1.blueprint', 'I'),
        ('J_8vox.blueprint', 'J'),
        ('K_16vox.blueprint', 'K'),
        ('L_64vox.blueprint', 'L'),
        ('M_layer.blueprint', 'M'),
    ]

    all_results = {}

    for fname, tag in targets:
        print(f"\n\n{'#'*70}")
        print(f"### {tag}: {fname}")
        bp = load_bp(fname)
        chunks = get_chunk_data(bp)
        print(f"h=3 chunks: {[(c[0],c[1],c[2]) for c in chunks]}")

        file_results = []
        for cx,cy,cz,vdata in chunks:
            scan = vdata[64:-40]
            label = f"{tag}({cx},{cy},{cz})"
            r = analyze_scan_bytes(scan, cz, label)
            file_results.append((cx,cy,cz,r))

        all_results[fname] = file_results

    # Summary
    print(f"\n\n{'#'*70}")
    print("### SUMMARY")
    print(f"{'File/Chunk':<35} {'pairs':>6} {'lead':>5} {'#decl':>6} {'#FG':>5} {'FG1':>5} {'FG1-n1':>7}")
    print("-"*70)
    for fname, tag in targets:
        if fname not in all_results: continue
        for cx,cy,cz,r in all_results[fname]:
            label = f"{tag}({cx},{cy},{cz})"
            n1 = r['decls'][0][0]//2 if r['decls'] else '?'
            fg1 = r['fgs'][0][0]//2 if r['fgs'] else '?'
            d = (fg1-n1) if isinstance(n1,int) and isinstance(fg1,int) else '?'
            print(f"  {label:<33} {r['n_pairs']:>6} {r['lead_pairs']:>5} {len(r['decls']):>6} {len(r['fgs']):>5} {str(fg1):>5} {str(d):>7}")

if __name__ == '__main__':
    process_all()
