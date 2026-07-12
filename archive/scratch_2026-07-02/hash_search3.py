import base64
import json
import lz4.block

MASK64 = 0xFFFFFFFFFFFFFFFF

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size), raw

samples = []
for n in (1496, 1502, 1504, 1506, 1508, 1517):
    with open(f"/home/du/exports/{n}_export.blueprint") as f:
        bp = json.load(f)
    for entry in bp["VoxelData"]:
        if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
            vhash = int(entry["records"]["voxel"]["hash"]["$numberLong"]) & MASK64
            voxel_b64 = entry["records"]["voxel"]["data"]["$binary"]
            dec, raw = decode_blob(voxel_b64)
            samples.append(dict(n=n, vhash=vhash, dec=dec, raw=raw))

def variants(s):
    dec = s['dec']
    raw = s['raw']
    idx = dec.find(b'Debug1')
    mat_start = idx - 13
    header = dec[:64]
    scan = dec[64:mat_start]
    mat = dec[mat_start:]
    yield "dec", dec
    yield "dec_no_counter", header + scan + mat[4:]
    yield "raw_full", raw
    yield "raw_no_magic", raw[4:]
    yield "raw_compressed", raw[12:]
    yield "scan", scan
    yield "header+scan", header + scan
    yield "scan+mattail", scan + mat[4:]
    yield "mat", mat
    yield "mattail", mat[4:]
    yield "header", header

def shift_mix(v):
    return (v ^ (v >> 47)) & MASK64

def gcc_hash_bytes(data, seed=0xc70f6907):
    mul = 0xc6a4a7935bd1e995
    length = len(data)
    len_aligned = length & ~0x7
    h = (seed ^ (length * mul)) & MASK64
    for i in range(0, len_aligned, 8):
        chunk = int.from_bytes(data[i:i+8], 'little')
        d = (shift_mix((chunk * mul) & MASK64) * mul) & MASK64
        h ^= d
        h = (h * mul) & MASK64
    rem = length & 0x7
    if rem:
        tail = int.from_bytes(data[len_aligned:], 'little')
        h ^= tail
        h = (h * mul) & MASK64
    h = (shift_mix(h) * mul) & MASK64
    h = shift_mix(h)
    return h

def murmur64a(data, seed=0):
    m = 0xc6a4a7935bd1e995
    r = 47
    length = len(data)
    h = (seed ^ ((length * m) & MASK64)) & MASK64
    n8 = length // 8
    for i in range(n8):
        k = int.from_bytes(data[i*8:i*8+8], 'little')
        k = (k * m) & MASK64
        k ^= (k >> r)
        k = (k * m) & MASK64
        h ^= k
        h = (h * m) & MASK64
    tail = data[n8*8:]
    for i in range(len(tail)-1, -1, -1):
        h ^= (tail[i] << (8*i))
    if tail:
        h = (h * m) & MASK64
    h ^= (h >> r)
    h = (h * m) & MASK64
    h ^= (h >> r)
    return h & MASK64

algos = {}
for seed in (0, 0xc70f6907, 1, 0x9747b28c, 0xffffffff):
    algos[f"gcc_hash_bytes_s{seed:x}"] = (lambda b, s=seed: gcc_hash_bytes(b, s))
    algos[f"murmur64a_s{seed:x}"] = (lambda b, s=seed: murmur64a(b, s))

vnames = [v[0] for v in variants(samples[0])]
print(f"Testing {len(algos)} algos x {len(vnames)} variants on {len(samples)} samples")

found = []
for name, fn in algos.items():
    for vname in vnames:
        ok = True
        for s in samples:
            data = dict(variants(s))[vname]
            h = fn(data) & MASK64
            if h != s['vhash']:
                ok = False
                break
        if ok:
            found.append((name, vname))

if found:
    for f in found:
        print("MATCH:", f)
else:
    print("No exact match.")
    # Show closeness: for the last sample, print candidate hashes
    s = samples[-1]
    print(f"\nn={s['n']} target=0x{s['vhash']:016x}")
    for vname in vnames:
        data = dict(variants(s))[vname]
        for name in ["gcc_hash_bytes_s0", "gcc_hash_bytes_sc70f6907", "murmur64a_s0", "murmur64a_sc70f6907"]:
            h = algos[name](data) & MASK64
            print(f"  {vname:20s} {name:25s} = 0x{h:016x}")
