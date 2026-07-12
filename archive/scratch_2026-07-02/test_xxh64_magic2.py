import base64, json, lz4.block, xxhash

MASK64 = 0xFFFFFFFFFFFFFFFF
SEED = 0xa1b2c3d4e5f6e7d8

def get_blobs(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    dec = lz4.block.decompress(raw[12:], uncompressed_size=size)
    return raw, dec

def variants(raw, dec):
    yield "dec", dec
    yield "raw", raw
    yield "raw[4:]", raw[4:]
    yield "raw[8:]", raw[8:]
    yield "raw[12:]", raw[12:]
    yield "raw[4:8]+raw[12:]", raw[4:8] + raw[12:]
    yield "len32+dec", len(dec).to_bytes(4,'little') + dec
    yield "len64+dec", len(dec).to_bytes(8,'little') + dec
    yield "dec+len32", dec + len(dec).to_bytes(4,'little')

samples = []
for n in (1496, 1502, 1504, 1506, 1508, 1517):
    with open(f"/home/du/exports/{n}_export.blueprint") as f:
        bp = json.load(f)
    for entry in bp["VoxelData"]:
        if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
            vhash = int(entry["records"]["voxel"]["hash"]["$numberLong"]) & MASK64
            mhash = int(entry["records"]["meta"]["hash"]["$numberLong"]) & MASK64
            vraw, vdec = get_blobs(entry["records"]["voxel"]["data"]["$binary"])
            mraw, mdec = get_blobs(entry["records"]["meta"]["data"]["$binary"])
            samples.append(dict(n=n, vhash=vhash, mhash=mhash, vraw=vraw, vdec=vdec, mraw=mraw, mdec=mdec))

vnames = [v[0] for v in variants(samples[0]['vraw'], samples[0]['vdec'])]
print(f"Testing seed=0x{SEED:016x} across variants: {vnames}")
print()

for vname in vnames:
    voxel_ok = True
    meta_ok = True
    for s in samples:
        vdata = dict(variants(s['vraw'], s['vdec']))[vname]
        mdata = dict(variants(s['mraw'], s['mdec']))[vname]
        vcalc = xxhash.xxh64(vdata, seed=SEED).intdigest()
        mcalc = xxhash.xxh64(mdata, seed=SEED).intdigest()
        if vcalc != s['vhash']:
            voxel_ok = False
        if mcalc != s['mhash']:
            meta_ok = False
    print(f"{vname:20s} voxel_all_match={voxel_ok}  meta_all_match={meta_ok}")

# also try seed=0 for these variants, just in case
print()
print("Now with seed=0:")
for vname in vnames:
    voxel_ok = True
    for s in samples:
        vdata = dict(variants(s['vraw'], s['vdec']))[vname]
        vcalc = xxhash.xxh64(vdata, seed=0).intdigest()
        if vcalc != s['vhash']:
            voxel_ok = False
    print(f"{vname:20s} voxel_all_match={voxel_ok}")
