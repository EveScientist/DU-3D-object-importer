#!/usr/bin/env python3
"""
Focused analysis - dump all non-trivial pairs from h=3 chunks with full context.
"""
import json, base64, lz4.block, struct

def decomp(b64):
    raw = base64.b64decode(b64)
    sz = struct.unpack('<I', raw[4:8])[0]
    return lz4.block.decompress(raw[12:], uncompressed_size=sz)

def load_bp(name):
    with open(f'/home/du/export/{name}') as f:
        return json.load(f)

def get_A(cz):
    return [0x01, 0x21, 0x20, 0x00][cz % 4]

def get_chunk_data(bp):
    """Extract all h=3 chunks as list of (x,y,z, vdata)"""
    chunks = []
    for entry in bp.get('VoxelData', []):
        h = entry.get('h', -1)
        if h != 3:
            continue
        x = entry.get('x', {})
        y = entry.get('y', {})
        z = entry.get('z', {})
        cx = int(x.get('$numberLong', x)) if isinstance(x, dict) else int(x)
        cy = int(y.get('$numberLong', y)) if isinstance(y, dict) else int(y)
        cz = int(z.get('$numberLong', z)) if isinstance(z, dict) else int(z)
        b64 = entry.get('records', {}).get('voxel', {}).get('data', {}).get('$binary', '')
        if not b64:
            continue
        try:
            vdata = decomp(b64)
        except Exception as e:
            print(f"  Decomp error ({cx},{cy},{cz}): {e}")
            continue
        chunks.append((cx, cy, cz, vdata))
    return sorted(chunks)

def dump_all_pairs(vdata, cx, cy, cz, label):
    """Dump complete scan with all non-(00,ff) and non-(ff,00) pairs highlighted."""
    A = get_A(cz)
    scan = vdata[64:-40]
    n = len(scan) // 2
    pairs = [(scan[i*2], scan[i*2+1]) for i in range(n)]

    print(f"\n{'='*70}")
    print(f"CHUNK {label} at ({cx},{cy},{cz}), cz%4={cz%4}, A=0x{A:02x}")
    print(f"Total pairs: {n}")
    print(f"Header: {vdata[:64].hex()}")
    print(f"Material: {vdata[-40:].hex()}")

    # Find leading run of (00,ff)
    lead_end = 0
    while lead_end < n and pairs[lead_end] == (0x00, 0xff):
        lead_end += 1

    # Find trailing run of (ff,00)
    trail_start = n
    while trail_start > 0 and pairs[trail_start-1] == (0xff, 0x00):
        trail_start -= 1

    print(f"Leading (00,ff): 0..{lead_end-1} ({lead_end} pairs)")
    print(f"Trailing (ff,00): {trail_start}..{n-1} ({n-trail_start} pairs)")
    print(f"Middle: {lead_end}..{trail_start-1} ({trail_start-lead_end} pairs)")

    # Print ALL pairs in middle section
    print(f"\nAll pairs (middle section, pairs {lead_end} to {trail_start-1}):")
    for i in range(lead_end, trail_start):
        p = pairs[i]
        tag = ""
        # Classify
        if p == (0x00, 0xff):
            tag = "(00,ff) embedded"
        elif p == (0xff, 0x00):
            tag = "(ff,00)"
        print(f"  [{i:4d}] {p[0]:02x} {p[1]:02x}  {tag}")

    return pairs, lead_end, trail_start, A, n

def analyze_fg_region(pairs, start, end, A):
    """Try to find face group patterns in a region, being flexible about pattern."""
    print(f"\n  Scanning for FG patterns (A=0x{A:02x}) in [{start}..{end}]:")
    i = start
    while i < end - 3:
        a,b = pairs[i], pairs[i+1]
        c,d = pairs[i+2], pairs[i+3]
        # Look for 7e 7e in middle
        if b[1] == 0x7e and c[0] == 0x7e:
            print(f"  Potential FG at [{i}]: ({pairs[i][0]:02x},{pairs[i][1]:02x}) ({pairs[i+1][0]:02x},{pairs[i+1][1]:02x}) ({pairs[i+2][0]:02x},{pairs[i+2][1]:02x}) ({pairs[i+3][0]:02x},{pairs[i+3][1]:02x})")
        if c[1] == 0x7e and d[0] == 0x7e:
            print(f"  Potential FG at [{i+1}]: ({pairs[i][0]:02x},{pairs[i][1]:02x}) ({pairs[i+1][0]:02x},{pairs[i+1][1]:02x}) ({pairs[i+2][0]:02x},{pairs[i+2][1]:02x}) ({pairs[i+3][0]:02x},{pairs[i+3][1]:02x})")
        i += 1

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

# First, just show F and H in full detail
for fname, tag in [('F_2vox_diff_n1.blueprint', 'F'), ('H_2vox_same_n1.blueprint', 'H')]:
    print(f"\n{'#'*70}")
    print(f"### {tag}: {fname}")
    bp = load_bp(fname)
    chunks = get_chunk_data(bp)
    print(f"h=3 chunks: {[(cx,cy,cz) for cx,cy,cz,_ in chunks]}")

    for cx, cy, cz, vdata in chunks:
        label = f"{tag}({cx},{cy},{cz})"
        pairs, lead_end, trail_start, A, n = dump_all_pairs(vdata, cx, cy, cz, label)
        analyze_fg_region(pairs, lead_end, trail_start, A)
