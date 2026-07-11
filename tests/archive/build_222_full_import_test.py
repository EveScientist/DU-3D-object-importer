#!/usr/bin/env python3
"""role222 (pos-x/pos-y) full standalone import test: clone export 2147,
regenerate ALL 8 chunks (1 content + 7 empties) from scratch."""
import sys, os, json, base64, struct
import lz4.block
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import h3_generator as g
import generate_hollow_cube as ghc
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def find_export(num):
    for d in ('exports', 'exports/archive'):
        p = os.path.join(ROOT, d, f'{num}_export.blueprint')
        if os.path.exists(p):
            return p


def decode_chunk_from_blob(blob):
    unc = struct.unpack('<I', blob[4:8])[0]
    dec = lz4.block.decompress(blob[12:], uncompressed_size=unc)
    idx = dec.find(b'Debug1')
    return dec[64:idx - 13], int.from_bytes(dec[idx - 13:idx - 9], 'little')


def main():
    # 2147: x=+1.5,+2.5 (Nc2), y=+1.5,+2.5 (Ye2), z=+1.5,+2.5 (N2)
    with open(find_export(2147)) as f:
        bp = json.load(f)
    mat_info = ghc.MATERIALS_INFO['hcCarbon']
    n = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        cx, cy, cz = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        real_scan, real_mc = decode_chunk_from_blob(base64.b64decode(e['records']['voxel']['data']['$binary']))
        if (cx, cy, cz) == (2, 2, 2):
            gen, gmc = g.generate_222_dense_scan(1, 1, 2, 2, 1, 2)
        else:
            gen, gmc = g.generate_122_edge_empty_scan()
        assert gen == real_scan and gmc == real_mc, f'mismatch {(cx,cy,cz)}'
        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        e['records']['voxel']['data']['$binary'] = ghc._b64(ghc._blob(ghc._hdr(cx, cy, cz) + gen + mat))
        n += 1
    assert n == 8, n
    out = os.path.join(HERE, '222_full_import_test.blueprint')
    with open(out, 'w') as f:
        json.dump(bp, f)
    print(f'role222 full ({n} chunks generated): sanity OK. Written: {out}')


if __name__ == '__main__':
    main()
