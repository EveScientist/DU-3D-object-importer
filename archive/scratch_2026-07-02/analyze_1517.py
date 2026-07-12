import base64
import json
import lz4.block

def decode_blob(b64):
    raw = base64.b64decode(b64)
    magic = raw[:4]
    size = int.from_bytes(raw[4:8], 'little')
    next4 = raw[8:12]
    dec = lz4.block.decompress(raw[12:], uncompressed_size=size)
    return dec, magic, size, next4, raw

with open("/home/du/exports/1517_export.blueprint") as f:
    bp = json.load(f)

for entry in bp["VoxelData"]:
    if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
        voxel_b64 = entry["records"]["voxel"]["data"]["$binary"]
        meta_b64 = entry["records"]["meta"]["data"]["$binary"]
        vhash = int(entry["records"]["voxel"]["hash"]["$numberLong"])
        mhash = int(entry["records"]["meta"]["hash"]["$numberLong"])

        vdec, vmagic, vsize, vnext4, vraw = decode_blob(voxel_b64)
        mdec, mmagic, msize, mnext4, mraw = decode_blob(meta_b64)

        print("=== VOXEL (2,2,2) ===")
        print(f"vhash (signed)={vhash}  unsigned=0x{vhash & 0xFFFFFFFFFFFFFFFF:016x}")
        print(f"raw_len={len(vraw)} dec_len={len(vdec)} magic={vmagic.hex()} size={vsize} next4={vnext4.hex()}")

        idx = vdec.find(b'Debug1')
        mat_start = idx - 13
        header = vdec[:64]
        scan = vdec[64:mat_start]
        mat = vdec[mat_start:]
        mat_counter = int.from_bytes(mat[:4], 'little')
        print(f"header={header.hex()}")
        print(f"scan_len={len(scan)}")
        print(f"mat_counter={mat_counter} mat={mat.hex()}")
        print()

        print("=== META (2,2,2) ===")
        print(f"mhash (signed)={mhash}  unsigned=0x{mhash & 0xFFFFFFFFFFFFFFFF:016x}")
        print(f"raw_len={len(mraw)} dec_len={len(mdec)} magic={mmagic.hex()} size={msize} next4={mnext4.hex()}")
        print(f"mdec hex = {mdec.hex()}")
        print(f"meta[10:18] = {mdec[10:18].hex()}  LE u64=0x{int.from_bytes(mdec[10:18],'little'):016x}")
        print(f"meta[81] = {mdec[81] if len(mdec)>81 else 'N/A'}")
        if len(mdec) > 118:
            print(f"meta[116:118] = {mdec[116:118].hex()} LE u16={int.from_bytes(mdec[116:118],'little')}")

        vhash_u = vhash & 0xFFFFFFFFFFFFFFFF
        meta1018 = int.from_bytes(mdec[10:18],'little')
        print()
        print(f"meta[10:18] == voxel.hash (unsigned)? {meta1018 == vhash_u}")
