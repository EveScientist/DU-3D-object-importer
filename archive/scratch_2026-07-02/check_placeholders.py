import base64
import json
import lz4.block

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size)

with open("/home/du/exports/1517_export.blueprint") as f:
    bp = json.load(f)

for entry in bp["VoxelData"]:
    if entry["h"] == 3:
        x,y,z = entry["x"]["$numberLong"], entry["y"]["$numberLong"], entry["z"]["$numberLong"]
        vhash = int(entry["records"]["voxel"]["hash"]["$numberLong"]) & 0xFFFFFFFFFFFFFFFF
        mhash = int(entry["records"]["meta"]["hash"]["$numberLong"]) & 0xFFFFFFFFFFFFFFFF
        mdec = decode_blob(entry["records"]["meta"]["data"]["$binary"])
        vdec = decode_blob(entry["records"]["voxel"]["data"]["$binary"])
        m1018 = int.from_bytes(mdec[10:18],'little')
        print(f"h3 ({x},{y},{z}): voxel.hash=0x{vhash:016x} meta.hash=0x{mhash:016x} meta_len={len(mdec)} meta[10:18]=0x{m1018:016x} vdec_len={len(vdec)}")
        print(f"  meta[0:20].hex() = {mdec[0:20].hex()}")
