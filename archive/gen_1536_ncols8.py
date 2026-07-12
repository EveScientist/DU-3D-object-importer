import base64
import json
from du_hash import decode_blob, encode_blob, compute_hash, to_signed64
from h3_lowrow_generator import generate_lowrow_blob

# mat_counter formula for Ncols>=2: 512 + (410 + 55*Ncols) % 256
# W (wraps in [3..Ncols]) = 1 for Ncols=7..11 (no new wrap at Ncols=8)
# gap1=250, gap2=230 (both use W=1 correction from the Ncols=7 wrap)

with open("exports/1528_export.blueprint") as f:
    bp = json.load(f)

found = False
for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        mat_counter = 512 + (410 + 55 * 8) % 256  # 594
        header, scan, mat = generate_lowrow_blob(8, mat_counter)
        new_vdec = header + scan + mat

        new_vraw = encode_blob(new_vdec)
        new_vhash = compute_hash(new_vraw)
        entry["records"]["voxel"]["data"]["$binary"] = base64.b64encode(new_vraw).decode()
        entry["records"]["voxel"]["hash"]["$numberLong"] = str(to_signed64(new_vhash))

        meta_b64 = entry["records"]["meta"]["data"]["$binary"]
        mdec, _ = decode_blob(meta_b64)
        mdec = bytearray(mdec)
        mdec[81] = 8
        mdec[116:118] = (4 * 8 * 29).to_bytes(2, 'little')  # 928
        mdec[10:18] = new_vhash.to_bytes(8, 'little')
        mdec = bytes(mdec)

        new_mraw = encode_blob(mdec)
        new_mhash = compute_hash(new_mraw)
        entry["records"]["meta"]["data"]["$binary"] = base64.b64encode(new_mraw).decode()
        entry["records"]["meta"]["hash"]["$numberLong"] = str(to_signed64(new_mhash))

        print(f"mat_counter={mat_counter} scan_len={len(scan)}")
        print(f"new voxel.hash = {to_signed64(new_vhash)} (0x{new_vhash:016x})")
        print(f"new meta.hash  = {to_signed64(new_mhash)} (0x{new_mhash:016x})")
        found = True

assert found

bp["Model"]["Id"] = 1536
bp["Model"]["Name"] = "GEN Ncols=8 (W=1 wrap correction)"

with open("tests/1536_ncols8.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote tests/1536_ncols8.blueprint")
