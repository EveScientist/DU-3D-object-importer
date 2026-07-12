import base64
import json
from du_hash import decode_blob, encode_blob, compute_hash, to_signed64
from h3_lowrow_generator import generate_lowrow_blob

# Use 1528_export as template: its (2,2,2) h3 cell already has real Ncols=7
# meta (all fields correct); we only need to update meta[10:18] with our
# generated voxel's hash (our LZ4 encoding differs from game's, so hash differs).
with open("exports/1528_export.blueprint") as f:
    bp = json.load(f)

found = False
for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        # mat_counter = 512 + (410 + 55*7) % 256 = 539 (confirmed against real)
        mat_counter = 512 + (410 + 55 * 7) % 256
        header, scan, mat = generate_lowrow_blob(7, mat_counter)
        new_vdec = header + scan + mat

        new_vraw = encode_blob(new_vdec)
        new_vhash = compute_hash(new_vraw)
        entry["records"]["voxel"]["data"]["$binary"] = base64.b64encode(new_vraw).decode()
        entry["records"]["voxel"]["hash"]["$numberLong"] = str(to_signed64(new_vhash))

        # Meta: patch only meta[10:18] (voxel.hash echo); all other Ncols=7
        # fields (meta[81]=7, meta[116:118]=812) already correct in 1528_export.
        meta_b64 = entry["records"]["meta"]["data"]["$binary"]
        mdec, _ = decode_blob(meta_b64)
        mdec = bytearray(mdec)
        assert mdec[81] == 7, f"expected Ncols=7 in template meta, got {mdec[81]}"
        assert int.from_bytes(mdec[116:118], 'little') == 812
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

bp["Model"]["Id"] = 1534
bp["Model"]["Name"] = "GEN Ncols=7 (fixed gap formula, byte-exact scan)"

with open("tests/1534_ncols7_fixed.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote tests/1534_ncols7_fixed.blueprint")
