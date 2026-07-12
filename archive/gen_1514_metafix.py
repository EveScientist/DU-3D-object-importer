import base64
import json
import lz4.block

from h3_lowrow_generator import generate_lowrow_blob

def encode_blob(data):
    compressed = lz4.block.compress(data, store_size=False)
    return b'\xf9\xb6\x14\xfb' + len(data).to_bytes(4, 'little') + b'\x00\x00\x00\x00' + compressed

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size)

Ncols = 6
mat_counter = 700

header, scan, mat = generate_lowrow_blob(Ncols, mat_counter)
voxel_data = header + scan + mat
voxel_b64 = base64.b64encode(encode_blob(voxel_data)).decode()
print(f"Ncols={Ncols}: scan_len={len(scan)}")

with open("/home/du/exports/1508_export.blueprint") as f:
    bp = json.load(f)

found = False
for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        meta_b64 = entry["records"]["meta"]["data"]["$binary"]
        meta = bytearray(decode_blob(meta_b64))
        print("meta len:", len(meta), "meta[81] before:", meta[81])
        assert meta[81] == 5
        meta[81] = Ncols
        new_meta_b64 = base64.b64encode(encode_blob(bytes(meta))).decode()

        entry["records"]["meta"]["data"]["$binary"] = new_meta_b64
        entry["records"]["voxel"]["data"]["$binary"] = voxel_b64
        found = True
assert found

bp["Model"]["Id"] = 1514
bp["Model"]["Name"] = "GEN Ncols6 metafix b81"

with open("/home/du/tests/1514_gen_ncols6_metafix.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote /home/du/tests/1514_gen_ncols6_metafix.blueprint")
