import base64
import json
import lz4.block
import xxhash
import mmh3
import struct

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size), raw

samples = []
for n in (1496, 1502, 1504, 1506, 1508):
    with open(f"/home/du/exports/{n}_export.blueprint") as f:
        bp = json.load(f)
    for entry in bp["VoxelData"]:
        if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
            vhash = int(entry["records"]["voxel"]["hash"]["$numberLong"])
            mhash = int(entry["records"]["meta"]["hash"]["$numberLong"])
            voxel_b64 = entry["records"]["voxel"]["data"]["$binary"]
            meta_b64 = entry["records"]["meta"]["data"]["$binary"]
            dec, raw = decode_blob(voxel_b64)
            mdec, mraw = decode_blob(meta_b64)
            samples.append(dict(n=n, vhash=vhash, mhash=mhash, dec=dec, raw=raw, mdec=mdec, mraw=mraw))

for s in samples:
    vh = s['vhash']
    vh_u = vh & 0xFFFFFFFFFFFFFFFF
    print(f"n={s['n']} vhash(signed)={vh} vhash(unsigned)=0x{vh_u:016x} dec_len={len(s['dec'])} raw_len={len(s['raw'])}")
    print(f"  meta[10:18] = {s['mdec'][10:18].hex()}  (LE u64={int.from_bytes(s['mdec'][10:18],'little')})")

print()
print("=== brute force ===")

def variants(s):
    dec = s['dec']
    raw = s['raw']
    idx = dec.find(b'Debug1')
    mat_start = idx - 13
    header = dec[:64]
    scan = dec[64:mat_start]
    mat = dec[mat_start:]
    yield "dec", dec
    yield "raw_full", raw
    yield "raw_payload(no_magic)", raw[4:]
    yield "raw_compressed_payload", raw[12:]
    yield "scan", scan
    yield "header+scan", header+scan
    yield "scan+mat", scan+mat
    yield "mat", mat

algos = {}
algos["xxh64_seed0"] = lambda b: xxhash.xxh64(b, seed=0).intdigest()
algos["xxh64_seed1"] = lambda b: xxhash.xxh64(b, seed=1).intdigest()
algos["xxh3_64_seed0"] = lambda b: xxhash.xxh3_64(b, seed=0).intdigest()
algos["xxh3_64_default"] = lambda b: xxhash.xxh3_64(b).intdigest()
algos["xxh32_seed0"] = lambda b: xxhash.xxh32(b, seed=0).intdigest()

def fnv1_64(b):
    h = 0xcbf29ce484222325
    for byte in b:
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
        h ^= byte
    return h

def fnv1a_64(b):
    h = 0xcbf29ce484222325
    for byte in b:
        h ^= byte
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h

algos["fnv1_64"] = fnv1_64
algos["fnv1a_64"] = fnv1a_64

found = False
for name, fn in algos.items():
    for vname, _ in variants(samples[0]):
        ok = True
        for s in samples:
            for vn2, data in variants(s):
                if vn2 != vname:
                    continue
                h = fn(data)
                vh_u = s['vhash'] & 0xFFFFFFFFFFFFFFFF
                if h != vh_u:
                    ok = False
                break
        if ok:
            print(f"MATCH: {name} on {vname}")
            found = True

if not found:
    print("no match found among tried algos/variants")
    # print first sample's candidate hashes for inspection
    s = samples[0]
    for vname, data in variants(s):
        for name, fn in algos.items():
            h = fn(data)
            print(f"  {name}({vname}) = 0x{h:016x}")
        print(f"  target vhash_u = 0x{s['vhash']&0xFFFFFFFFFFFFFFFF:016x}")
        break
