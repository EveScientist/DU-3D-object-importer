import base64
import json
import lz4.block
import xxhash
import mmh3

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
            vhash = int(entry["records"]["voxel"]["hash"]["$numberLong"]) & 0xFFFFFFFFFFFFFFFF
            voxel_b64 = entry["records"]["voxel"]["data"]["$binary"]
            dec, raw = decode_blob(voxel_b64)
            samples.append(dict(n=n, vhash=vhash, dec=dec, raw=raw))

MASK64 = 0xFFFFFFFFFFFFFFFF

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
    yield "scan_no_matbyte", scan  # placeholder, same as scan

# --- algo implementations ---
def crc64(data, poly, init, refin, refout, xorout, width=64):
    if refin:
        # process bit-reversed bytes, reflected poly approach (table-free, slow but ok for small data)
        reg = init
        for byte in data:
            b = byte
            reg ^= b
            for _ in range(8):
                if reg & 1:
                    reg = (reg >> 1) ^ poly
                else:
                    reg >>= 1
        out = reg
    else:
        reg = init
        topbit = 1 << (width - 1)
        for byte in data:
            reg ^= (byte << (width - 8))
            for _ in range(8):
                if reg & topbit:
                    reg = ((reg << 1) ^ poly) & MASK64
                else:
                    reg = (reg << 1) & MASK64
        out = reg
    if refout != refin:
        # reverse bits
        v = out
        r = 0
        for _ in range(width):
            r = (r << 1) | (v & 1)
            v >>= 1
        out = r
    return (out ^ xorout) & MASK64

CRC64_VARIANTS = {
    "CRC64-XZ": dict(poly=0x42F0E1EBA9EA3693, init=MASK64, refin=True, refout=True, xorout=MASK64),
    "CRC64-ECMA": dict(poly=0x42F0E1EBA9EA3693, init=0, refin=False, refout=False, xorout=0),
    "CRC64-ISO": dict(poly=0x000000000000001B, init=MASK64, refin=True, refout=True, xorout=MASK64),
    "CRC64-JONES": dict(poly=0xAD93D23594C935A9, init=MASK64, refin=True, refout=True, xorout=0),
    "CRC64-NVME": dict(poly=0xAD93D23594C935A9, init=MASK64, refin=True, refout=True, xorout=MASK64),
}

def wyhash64(data, seed=0):
    # simplified wyhash (v3-ish), for search purposes
    P0=0xa0761d6478bd642f; P1=0xe7037ed1a0b428db; P2=0x8ebc6af09c88c6e3; P3=0x589965cc75374cc3
    def mum(a,b):
        r = (a*b)
        return (r & MASK64) ^ (r >> 64)
    seed ^= P0
    i = 0
    n = len(data)
    a = seed
    while i + 8 <= n:
        a = mum(a ^ int.from_bytes(data[i:i+8],'little'), P1)
        i += 8
    if i < n:
        rem = data[i:]
        v = int.from_bytes(rem + b'\x00'*(8-len(rem)), 'little')
        a = mum(a ^ v, P2)
    return mum(a, n ^ P3)

algos = {}
for seed in (0, 1, 2, 0x9E3779B97F4A7C15 & MASK64, 0xCBF29CE484222325, 1337, 12345, 0x1234567812345678):
    algos[f"xxh64_s{seed:x}"] = (lambda b, s=seed: xxhash.xxh64(b, seed=s).intdigest())
    algos[f"xxh3_64_s{seed:x}"] = (lambda b, s=seed: xxhash.xxh3_64(b, seed=s).intdigest())
    algos[f"wyhash_s{seed:x}"] = (lambda b, s=seed: wyhash64(b, s))

for name, params in CRC64_VARIANTS.items():
    algos[name] = (lambda b, p=params: crc64(b, **p))

def mmh3_x64_128_lo(b):
    a, c = mmh3.hash64(b, signed=False)
    return a
def mmh3_x64_128_hi(b):
    a, c = mmh3.hash64(b, signed=False)
    return c
algos["mmh3_x64_128_lo"] = mmh3_x64_128_lo
algos["mmh3_x64_128_hi"] = mmh3_x64_128_hi

print(f"Testing {len(algos)} algos x variants on {len(samples)} samples...")

# collect variant names
vnames = [v[0] for v in variants(samples[0])]

found = []
for name, fn in algos.items():
    for vname in vnames:
        ok = True
        for s in samples:
            data = dict(variants(s))[vname]
            try:
                h = fn(data) & MASK64
            except Exception as e:
                ok = False
                break
            if h != s['vhash']:
                ok = False
                break
        if ok:
            found.append((name, vname))

if found:
    for f in found:
        print("MATCH:", f)
else:
    print("No exact match found.")
    # print a sample of values for offline inspection
    s = samples[-1]
    print(f"\nSample n={s['n']} target vhash=0x{s['vhash']:016x}")
    for vname in vnames[:6]:
        data = dict(variants(s))[vname]
        print(f"  variant={vname} len={len(data)}")
        for name in ["xxh64_s0","xxh3_64_s0","wyhash_s0","CRC64-XZ","mmh3_x64_128_lo"]:
            h = algos[name](data) & MASK64
            print(f"    {name} = 0x{h:016x}")
