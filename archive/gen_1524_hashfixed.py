import base64
import json
from du_hash import decode_blob, encode_blob, compute_hash, to_signed64

with open("/home/du/exports/1508_export.blueprint") as f:
    bp = json.load(f)

found = False
for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        # --- voxel record: same mat_counter edit as 1518 (685 -> 941) ---
        voxel_b64 = entry["records"]["voxel"]["data"]["$binary"]
        vdec, _ = decode_blob(voxel_b64)

        idx = vdec.find(b'Debug1')
        mat_start = idx - 13
        header = vdec[:64]
        scan = vdec[64:mat_start]
        mat = vdec[mat_start:]

        old_counter = int.from_bytes(mat[:4], 'little')
        new_counter = old_counter + 256
        new_mat = new_counter.to_bytes(4, 'little') + mat[4:]
        new_vdec = header + scan + new_mat
        assert len(new_vdec) == len(vdec)

        new_vraw = encode_blob(new_vdec)
        new_vhash = compute_hash(new_vraw)
        entry["records"]["voxel"]["data"]["$binary"] = base64.b64encode(new_vraw).decode()
        entry["records"]["voxel"]["hash"]["$numberLong"] = str(to_signed64(new_vhash))

        # --- meta record: patch meta[10:18] = new voxel hash, recompute meta.hash ---
        meta_b64 = entry["records"]["meta"]["data"]["$binary"]
        mdec, _ = decode_blob(meta_b64)
        mdec = bytearray(mdec)
        mdec[10:18] = new_vhash.to_bytes(8, 'little')
        mdec = bytes(mdec)

        new_mraw = encode_blob(mdec)
        new_mhash = compute_hash(new_mraw)
        entry["records"]["meta"]["data"]["$binary"] = base64.b64encode(new_mraw).decode()
        entry["records"]["meta"]["hash"]["$numberLong"] = str(to_signed64(new_mhash))

        print(f"old mat_counter={old_counter} new={new_counter}")
        print(f"old voxel.hash unsigned=0x{int(entry['records']['voxel']['hash']['$numberLong']) & 0xFFFFFFFFFFFFFFFF:016x}")
        print(f"new voxel.hash = {to_signed64(new_vhash)} (0x{new_vhash:016x})")
        print(f"new meta.hash  = {to_signed64(new_mhash)} (0x{new_mhash:016x})")
        found = True

assert found

bp["Model"]["Id"] = 1524
bp["Model"]["Name"] = "GEN matcounter + CORRECT hashes"

with open("/home/du/tests/1524_hashfixed.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote /home/du/tests/1524_hashfixed.blueprint")
