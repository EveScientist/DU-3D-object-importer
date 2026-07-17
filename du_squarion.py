"""du_squarion.py -- SEMANTIC model of the DU voxel cell format (2026-07-17).

Derived from https://github.com/Skygallant/du-blueprint (src/squarion.rs), then
VERIFIED: every record (all LOD levels h3-h7) of every checked donor ROUND-TRIPS
byte-exactly through parse_cell/serialize_cell.

Format (after LZ4 header strip):
  [cell magic 0x27b8a013][ver 6][grid magic 0xe881339e][ver 9]
  [range: origin 3xi32, size 3xi32]      <- 35^3 at inner-1 (1 below, 2 above)
  [inner_range: origin, size]            <- the 32^3 chunk
  MATERIALS: RLE over the DENSE 35^3 grid, z-fastest ((x*35+y)*35+z):
     absent run  = [00, count-1];  present run = [01, mat_idx, count-1]
  VERTICES: RLE runs [flags, count-1]; flags&1 -> inner RLE quads
     [px, py, pz, count-1] (positions u8 around 126, 84 steps/voxel)
  [mapping: u32 n + n x (u64 id, 8-char name, u8 idx)]  (Debug1=1 + material=2)
  [is_diff u8]
Materials sit at voxel+(1,1,1); vertices on voxel corners.

This EXPLAINS the entire empirical h3 grammar in du_general/du_validate:
  bg 00/ff alternation = absent-run pairs (256 cells each); markers [v,1,m,h-1,0]
  = material column runs; group tokens [v,1,r,...] = vertex runs (v = tail count
  byte of the preceding gap, 1 = flags, r = run count); plain token = single-quad
  RLE (count aliases run); "mc" at dec[-40:-36] = last gap count byte + 512
  (mapping-count bytes). All val/pad/lead/gap "laws" = RLE distance arithmetic.
"""
import sys, struct, json, base64, lz4.block, os
sys.path.insert(0, '/home/du')

def load_records(name):
    for d in ('exports', 'exports/archive', 'tests'):
        p = f'/home/du/{d}/{name}_export.blueprint'
        if os.path.exists(p): break
    bp = json.load(open(p)); out = []
    for e in bp['VoxelData']:
        raw = base64.b64decode(e['records']['voxel']['data']['$binary'])
        size = int.from_bytes(raw[4:12], 'little')
        dec = bytes(lz4.block.decompress(raw[12:], uncompressed_size=size))
        key = (e['h'], *(int(e[k]['$numberLong']) for k in ('x','y','z')))
        out.append((key, dec))
    return out

def parse_cell(D):
    off = 0
    def u32():
        nonlocal off; v = struct.unpack_from('<I', D, off)[0]; off += 4; return v
    def i32x3():
        nonlocal off; v = struct.unpack_from('<3i', D, off); off += 12; return v
    assert u32() == 0x27b8a013, 'cell magic'
    assert u32() == 6, 'cell version'
    assert u32() == 0xe881339e, 'grid magic'
    assert u32() == 9, 'grid version'
    rng_o, rng_s = i32x3(), i32x3()
    inn_o, inn_s = i32x3(), i32x3()
    length = rng_s[0]*rng_s[1]*rng_s[2]
    # materials: RLE of Option<u8>
    mats = []   # list of (mat|None, count)
    i = 0
    while i < length:
        present = D[off]; off += 1
        mat = None
        if present:
            mat = D[off]; off += 1
        more = D[off] + 1; off += 1
        mats.append((mat, more)); i += more
    assert i == length, f'materials overrun {i}/{length}'
    # vertices: RLE of flags runs, flags&1 -> inner RLE of ([x,y,z], count)
    verts = []  # list of (flags, count, [( (x,y,z), count ), ...])
    i = 0
    while i < length:
        flags = D[off]; off += 1
        more = D[off] + 1; off += 1
        quads = None
        if flags & 1:
            quads = []
            j = 0
            while j < more:
                pos = tuple(D[off:off+3]); off += 3
                yet = D[off] + 1; off += 1
                quads.append((pos, yet)); j += yet
            assert j == more, 'vertex inner overrun'
        verts.append((flags, more, quads)); i += more
    assert i == length, f'vertices overrun {i}/{length}'
    # mapping: u32 count + (u64 id + 8-char name + u8 index)*
    nmap = u32()
    mapping = []
    for _ in range(nmap):
        mid = struct.unpack_from('<Q', D, off)[0]; off += 8
        name = D[off:off+8].decode('utf8', 'replace'); off += 8
        idx = D[off]; off += 1
        mapping.append((mid, name, idx))
    is_diff = D[off]; off += 1
    assert off == len(D), f'tail mismatch: off {off} != len {len(D)}'
    return dict(range=(rng_o, rng_s), inner=(inn_o, inn_s), mats=mats, verts=verts,
                mapping=mapping, is_diff=is_diff)

def ser_rle_none(count, out):
    while count:
        out.append(0); count -= 1
        more = min(count, 255); out.append(more); count -= more

def serialize_cell(P):
    out = bytearray()
    out += struct.pack('<I', 0x27b8a013) + struct.pack('<I', 6)
    out += struct.pack('<I', 0xe881339e) + struct.pack('<I', 9)
    for tri in (*P['range'], *P['inner']):
        out += struct.pack('<3i', *tri)
    for mat, more in P['mats']:
        if mat is None:
            out.append(0)
        else:
            out.append(1); out.append(mat)
        out.append(more - 1)
    for flags, more, quads in P['verts']:
        out.append(flags); out.append(more - 1)
        if flags & 1:
            for pos, yet in quads:
                out += bytes(pos); out.append(yet - 1)
    out += struct.pack('<I', len(P['mapping']))
    for mid, name, idx in P['mapping']:
        out += struct.pack('<Q', mid) + name.encode() + bytes([idx])
    out.append(P['is_diff'])
    return bytes(out)

if __name__ == '__main__':
    for name in sys.argv[1:]:
        for key, D in load_records(name):
            try:
                P = parse_cell(D)
                rt = serialize_cell(P)
                status = 'ROUND-TRIP EXACT' if rt == D else f'RT DIFFERS ({len(rt)} vs {len(D)})'
                print(f'{name} h{key[0]} {key[1:]}: {status}  range={P["range"]} inner={P["inner"]} '
                      f'mapping={[(m[0], m[1].strip(chr(0)), m[2]) for m in P["mapping"]]} is_diff={P["is_diff"]}')
            except AssertionError as e:
                print(f'{name} h{key[0]} {key[1:]}: PARSE FAIL: {e}')
