import base64
import json
import lz4.block

def encode_blob(data):
    compressed = lz4.block.compress(data, store_size=False)
    return b'\xf9\xb6\x14\xfb' + len(data).to_bytes(4, 'little') + b'\x00\x00\x00\x00' + compressed

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size)

with open("/home/du/exports/1508_export.blueprint") as f:
    bp = json.load(f)

found = False
for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        voxel_b64 = entry["records"]["voxel"]["data"]["$binary"]
        dec = decode_blob(voxel_b64)

        idx = dec.find(b'Debug1')
        mat_start = idx - 13
        header = dec[:64]
        scan = dec[64:mat_start]
        mat = dec[mat_start:]

        old_counter = int.from_bytes(mat[:4], 'little')
        new_counter = old_counter + 256  # same as 1518/1520
        new_mat = new_counter.to_bytes(4, 'little') + mat[4:]
        new_voxel_data = header + scan + new_mat
        assert len(new_voxel_data) == len(dec)

        new_b64 = base64.b64encode(encode_blob(new_voxel_data)).decode()
        entry["records"]["voxel"]["data"]["$binary"] = new_b64
        # meta left COMPLETELY UNCHANGED (stale, same as 1518)
        # voxel.hash also left UNCHANGED (same as 1518, NOT zeroed this time)

        entry["metadata"]["uptodate"] = False
        found = True
assert found

bp["Model"]["Id"] = 1522
bp["Model"]["Name"] = "GEN matcounter + uptodate=false"

with open("/home/du/tests/1522_uptodate_false.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote /home/du/tests/1522_uptodate_false.blueprint")
