import base64
import json
import lz4.block

from h3_lowrow_generator import generate_lowrow_blob, HEADER_222

def encode_blob(header64, scan, mat40):
    data = bytes(header64) + bytes(scan) + bytes(mat40)
    compressed = lz4.block.compress(data, store_size=False)
    return b'\xf9\xb6\x14\xfb' + len(data).to_bytes(4, 'little') + b'\x00\x00\x00\x00' + compressed

Ncols = 29
mat_counter = 686

header, scan, mat = generate_lowrow_blob(Ncols, mat_counter)
print(f"Ncols={Ncols}: scan_len={len(scan)} (predicted 11490)")
blob = encode_blob(header, scan, mat)
b64 = base64.b64encode(blob).decode()
print("new blob b64 len:", len(b64))

with open("/home/du/exports/1508_export.blueprint") as f:
    bp = json.load(f)

found = False
for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        entry["records"]["voxel"]["data"]["$binary"] = b64
        found = True
        print("replaced main (2,2,2) h3 voxel data")
assert found

bp["Model"]["Id"] = 1510
bp["Model"]["Name"] = "GEN fullface 29x29 z=14"

with open("/home/du/tests/1510_gen_fullface.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote /home/du/tests/1510_gen_fullface.blueprint")
