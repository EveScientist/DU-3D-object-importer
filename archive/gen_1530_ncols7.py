import base64
import json
from du_hash import decode_blob, encode_blob, compute_hash, to_signed64
from h3_lowrow_generator import generate_lowrow_blob

with open("/home/du/exports/1508_export.blueprint") as f:
    bp = json.load(f)

found = False
for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        # --- voxel record: GENERATED Ncols=7 content (extrapolated formula) ---
        # mat_counter formula (Ncols>=2): 55*Ncols + 410, validated 5/5 on Ncols=2..6
        header, scan, mat = generate_lowrow_blob(7, 55 * 7 + 410)
        new_vdec = header + scan + mat

        new_vraw = encode_blob(new_vdec)
        new_vhash = compute_hash(new_vraw)
        entry["records"]["voxel"]["data"]["$binary"] = base64.b64encode(new_vraw).decode()
        entry["records"]["voxel"]["hash"]["$numberLong"] = str(to_signed64(new_vhash))

        # --- meta record: 1508's Ncols=5 meta, minimally patched for Ncols=7 ---
        # (per TEST 1528: the other unidentified byte ranges don't matter)
        meta_b64 = entry["records"]["meta"]["data"]["$binary"]
        mdec, _ = decode_blob(meta_b64)
        mdec = bytearray(mdec)
        mdec[81] = 7                                   # Ncols
        mdec[116:118] = (4 * 7 * 29).to_bytes(2, 'little')  # 812
        mdec[10:18] = new_vhash.to_bytes(8, 'little')  # voxel.hash echo
        mdec = bytes(mdec)

        new_mraw = encode_blob(mdec)
        new_mhash = compute_hash(new_mraw)
        entry["records"]["meta"]["data"]["$binary"] = base64.b64encode(new_mraw).decode()
        entry["records"]["meta"]["hash"]["$numberLong"] = str(to_signed64(new_mhash))

        print(f"scan_len={len(scan)} mat_counter={55*7+410}")
        print(f"new voxel.hash = {to_signed64(new_vhash)} (0x{new_vhash:016x})")
        print(f"new meta.hash  = {to_signed64(new_mhash)} (0x{new_mhash:016x})")
        found = True

assert found

bp["Model"]["Id"] = 1530
bp["Model"]["Name"] = "GEN Ncols=7 (extrapolated, never-before-seen)"

with open("/home/du/tests/1530_ncols7.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote /home/du/tests/1530_ncols7.blueprint")
