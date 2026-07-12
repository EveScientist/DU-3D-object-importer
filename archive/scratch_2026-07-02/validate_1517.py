import base64
import json
import lz4.block
from h3_lowrow_generator import generate_lowrow_blob, generate_lowrow_scan, HEADER_222

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size)

with open("/home/du/exports/1517_export.blueprint") as f:
    bp1517 = json.load(f)
with open("/home/du/exports/1508_export.blueprint") as f:
    bp1508 = json.load(f)

def get_222(bp):
    for entry in bp["VoxelData"]:
        if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
            return entry
    raise Exception("not found")

e1517 = get_222(bp1517)
e1508 = get_222(bp1508)

vdec1517 = decode_blob(e1517["records"]["voxel"]["data"]["$binary"])
mdec1517 = decode_blob(e1517["records"]["meta"]["data"]["$binary"])
mdec1508 = decode_blob(e1508["records"]["meta"]["data"]["$binary"])

idx = vdec1517.find(b'Debug1')
mat_start = idx - 13
real_header = vdec1517[:64]
real_scan = vdec1517[64:mat_start]
real_mat = vdec1517[mat_start:]
mat_counter = int.from_bytes(real_mat[:4], 'little')

print(f"real scan_len={len(real_scan)} mat_counter={mat_counter}")

gen_header, gen_scan, gen_mat = generate_lowrow_blob(6, mat_counter)
print(f"gen  scan_len={len(gen_scan)}")
print(f"header match: {gen_header == real_header}")
print(f"mat match: {gen_mat == real_mat}")
print(f"scan match: {gen_scan == real_scan}")

if gen_scan != real_scan:
    if len(gen_scan) != len(real_scan):
        print(f"LEN MISMATCH: real={len(real_scan)} gen={len(gen_scan)}")
    n = min(len(gen_scan), len(real_scan))
    diffs = [(i, real_scan[i], gen_scan[i]) for i in range(n) if real_scan[i] != gen_scan[i]]
    print(f"num diffs in overlap: {len(diffs)}")
    for i, r, g in diffs[:40]:
        print(f"  diff at {i}: real={r:02x} gen={g:02x}")

print()
print("=== META DIFF: 1508 (Ncols=5) vs 1517 (Ncols=6) ===")
print(f"len 1508={len(mdec1508)} len 1517={len(mdec1517)}")
n = min(len(mdec1508), len(mdec1517))
diffs = [(i, mdec1508[i], mdec1517[i]) for i in range(n) if mdec1508[i] != mdec1517[i]]
print(f"num diff bytes: {len(diffs)}")
# group into contiguous ranges
ranges = []
for i, a, b in diffs:
    if ranges and ranges[-1][1] == i-1:
        ranges[-1] = (ranges[-1][0], i)
    else:
        ranges.append((i, i))
for start, end in ranges:
    print(f"  bytes [{start}:{end+1}]  1508={mdec1508[start:end+1].hex()}  1517={mdec1517[start:end+1].hex()}")
