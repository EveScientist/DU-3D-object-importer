import base64
import json
import lz4.block
import zlib
import xxhash

MASK64 = 0xFFFFFFFFFFFFFFFF

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size)

samples = []
for n in (1496, 1502, 1504, 1506, 1508, 1517):
    with open(f"/home/du/exports/{n}_export.blueprint") as f:
        bp = json.load(f)
    for entry in bp["VoxelData"]:
        if entry["h"] == 3 and entry["x"]["$numberLong"] == 2 and entry["y"]["$numberLong"] == 2 and entry["z"]["$numberLong"] == 2:
            mdec = decode_blob(entry["records"]["meta"]["data"]["$binary"])
            h1018 = int.from_bytes(mdec[10:18], 'little')
            samples.append(dict(n=n, mdec=mdec, h1018=h1018))

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

def variants(mdec):
    zeroed = bytearray(mdec)
    zeroed[10:18] = b'\x00'*8
    yield "meta[18:]", mdec[18:]
    yield "meta_zeroed_full", bytes(zeroed)
    yield "meta[0:10]+meta[18:]", mdec[0:10] + mdec[18:]
    yield "meta[18:]_no_pad", mdec[18:].rstrip(b'\x00')
    yield "meta_zeroed_no_pad", bytes(zeroed).rstrip(b'\x00')

algos = {}
algos["crc32"] = lambda b: zlib.crc32(b) & 0xFFFFFFFF
algos["adler32"] = lambda b: zlib.adler32(b) & 0xFFFFFFFF
for seed in (0, 0xc70f6907):
    algos[f"xxh64_s{seed:x}"] = (lambda b, s=seed: xxhash.xxh64(b, seed=s).intdigest())
    algos[f"gcc_hash_bytes_s{seed:x}"] = (lambda b, s=seed: gcc_hash_bytes(b, s))

vnames = [v[0] for v in variants(samples[0]['mdec'])]
print(f"{len(samples)} samples, testing variants: {vnames}")

found = []
for name, fn in algos.items():
    for vname in vnames:
        ok = True
        for s in samples:
            data = dict(variants(s['mdec']))[vname]
            h = fn(data)
            target = s['h1018']
            if (h & MASK64) != target and (h & 0xFFFFFFFF) != (target & 0xFFFFFFFF):
                ok = False
                break
        if ok:
            found.append((name, vname))

if found:
    for f in found:
        print("POSSIBLE MATCH:", f)
else:
    print("No match.")

# Print details for last sample
s = samples[-1]
print(f"\nn={s['n']} target meta[10:18]=0x{s['h1018']:016x}  (low32=0x{s['h1018']&0xFFFFFFFF:08x})")
for vname in vnames:
    data = dict(variants(s['mdec']))[vname]
    print(f"  variant={vname} len={len(data)}")
    for name, fn in algos.items():
        h = fn(data)
        print(f"    {name} = 0x{h:0{16 if h>0xFFFFFFFF else 8}x}")
