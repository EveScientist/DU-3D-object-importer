import base64, json, lz4.block, xxhash

MASK64 = 0xFFFFFFFFFFFFFFFF
SEED = 0xa1b2c3d4e5f6e7d8

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size)

print(f"SEED = 0x{SEED:016x}")
print()

for n in (1496, 1502, 1504, 1506, 1508, 1517):
    with open(f"/home/du/exports/{n}_export.blueprint") as f:
        bp = json.load(f)
    for entry in bp["VoxelData"]:
        if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
            vhash = int(entry["records"]["voxel"]["hash"]["$numberLong"]) & MASK64
            mhash = int(entry["records"]["meta"]["hash"]["$numberLong"]) & MASK64
            vdec = decode_blob(entry["records"]["voxel"]["data"]["$binary"])
            mdec = decode_blob(entry["records"]["meta"]["data"]["$binary"])
            vcalc = xxhash.xxh64(vdec, seed=SEED).intdigest()
            mcalc = xxhash.xxh64(mdec, seed=SEED).intdigest()
            print(f"n={n} (2,2,2): voxel match={vcalc==vhash}  (calc={vcalc:016x} target={vhash:016x})")
            print(f"             meta  match={mcalc==mhash}  (calc={mcalc:016x} target={mhash:016x})")

print()
print("=== 1517 placeholder cells ===")
with open("/home/du/exports/1517_export.blueprint") as f:
    bp = json.load(f)
for entry in bp["VoxelData"]:
    if entry["h"] == 3:
        x,y,z = entry["x"]["$numberLong"], entry["y"]["$numberLong"], entry["z"]["$numberLong"]
        if (x,y,z) == (2,2,2):
            continue
        vhash = int(entry["records"]["voxel"]["hash"]["$numberLong"]) & MASK64
        mhash = int(entry["records"]["meta"]["hash"]["$numberLong"]) & MASK64
        vdec = decode_blob(entry["records"]["voxel"]["data"]["$binary"])
        mdec = decode_blob(entry["records"]["meta"]["data"]["$binary"])
        vcalc = xxhash.xxh64(vdec, seed=SEED).intdigest()
        mcalc = xxhash.xxh64(mdec, seed=SEED).intdigest()
        print(f"1517 ({x},{y},{z}): voxel match={vcalc==vhash}  meta match={mcalc==mhash}")
