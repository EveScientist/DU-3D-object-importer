import base64
import json
from du_hash import decode_blob, encode_blob, compute_hash, to_signed64

with open("/home/du/exports/1508_export.blueprint") as f:
    bp = json.load(f)

found = False
for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        # --- voxel record: NO content change, just re-encode + re-hash ---
        voxel_b64 = entry["records"]["voxel"]["data"]["$binary"]
        vdec, vraw_old = decode_blob(voxel_b64)

        new_vraw = encode_blob(vdec)
        new_vhash = compute_hash(new_vraw)
        entry["records"]["voxel"]["data"]["$binary"] = base64.b64encode(new_vraw).decode()
        entry["records"]["voxel"]["hash"]["$numberLong"] = str(to_signed64(new_vhash))

        # --- meta record: patch meta[10:18] = new voxel hash, recompute meta.hash ---
        meta_b64 = entry["records"]["meta"]["data"]["$binary"]
        mdec, mraw_old = decode_blob(meta_b64)
        mdec = bytearray(mdec)
        mdec[10:18] = new_vhash.to_bytes(8, 'little')
        mdec = bytes(mdec)

        new_mraw = encode_blob(mdec)
        new_mhash = compute_hash(new_mraw)
        entry["records"]["meta"]["data"]["$binary"] = base64.b64encode(new_mraw).decode()
        entry["records"]["meta"]["hash"]["$numberLong"] = str(to_signed64(new_mhash))

        print(f"voxel: old raw len={len(vraw_old)} new raw len={len(new_vraw)}")
        print(f"old voxel.hash unsigned=0x{int.from_bytes(base64.b64decode(voxel_b64)[12:16],'little'):08x}... (full: see below)")
        print(f"new voxel.hash = {to_signed64(new_vhash)} (0x{new_vhash:016x})")
        print(f"meta:  old raw len={len(mraw_old)} new raw len={len(new_mraw)}")
        print(f"new meta.hash  = {to_signed64(new_mhash)} (0x{new_mhash:016x})")
        found = True

assert found

bp["Model"]["Id"] = 1526
bp["Model"]["Name"] = "GEN null-edit (re-encode only)"

with open("/home/du/tests/1526_nulledit.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote /home/du/tests/1526_nulledit.blueprint")
