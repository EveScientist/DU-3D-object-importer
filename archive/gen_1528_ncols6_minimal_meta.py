import base64
import json
from du_hash import decode_blob, encode_blob, compute_hash, to_signed64
from h3_lowrow_generator import generate_lowrow_blob

with open("/home/du/exports/1508_export.blueprint") as f:
    bp = json.load(f)

found = False
for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        # --- voxel record: GENERATED Ncols=6 content (byte-exact to 1517) ---
        header, scan, mat = generate_lowrow_blob(6, 740)
        new_vdec = header + scan + mat

        new_vraw = encode_blob(new_vdec)
        new_vhash = compute_hash(new_vraw)
        entry["records"]["voxel"]["data"]["$binary"] = base64.b64encode(new_vraw).decode()
        entry["records"]["voxel"]["hash"]["$numberLong"] = str(to_signed64(new_vhash))

        # --- meta record: 1508's Ncols=5 meta, MINIMALLY patched for Ncols=6 ---
        meta_b64 = entry["records"]["meta"]["data"]["$binary"]
        mdec, _ = decode_blob(meta_b64)
        mdec = bytearray(mdec)
        mdec[81] = 6                                   # Ncols
        mdec[116:118] = (4 * 6 * 29).to_bytes(2, 'little')  # 696
        mdec[10:18] = new_vhash.to_bytes(8, 'little')  # voxel.hash echo
        mdec = bytes(mdec)

        new_mraw = encode_blob(mdec)
        new_mhash = compute_hash(new_mraw)
        entry["records"]["meta"]["data"]["$binary"] = base64.b64encode(new_mraw).decode()
        entry["records"]["meta"]["hash"]["$numberLong"] = str(to_signed64(new_mhash))

        print(f"new voxel.hash = {to_signed64(new_vhash)} (0x{new_vhash:016x})")
        print(f"new meta.hash  = {to_signed64(new_mhash)} (0x{new_mhash:016x})")
        found = True

assert found

bp["Model"]["Id"] = 1528
bp["Model"]["Name"] = "GEN Ncols=6 + minimal-patch Ncols=5 meta"

with open("/home/du/tests/1528_ncols6_minimalmeta.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote /home/du/tests/1528_ncols6_minimalmeta.blueprint")
