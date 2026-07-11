#!/usr/bin/env python3
"""
Byte-exact validation harness for h3_generator.py against real exports.
Checks both exports/ and exports/archive/ for each export number.
"""
import sys
import os
import json
import base64
import lz4.block

# repo root = nearest ancestor of this file containing exports/ (the suites
# moved into tests/archive/ on 2026-07-04, so don't hardcode the depth)
_ROOT = os.path.dirname(os.path.abspath(__file__))
while _ROOT != '/' and not os.path.isdir(os.path.join(_ROOT, 'exports')):
    _ROOT = os.path.dirname(_ROOT)

sys.path.insert(0, _ROOT)
import h3_generator as g


def find_export(num):
    for d in ('exports', 'exports/archive'):
        path = os.path.join(_ROOT, d, f'{num}_export.blueprint')
        if os.path.exists(path):
            return path
    return None


def decode_chunk(path, h, cx, cy, cz):
    with open(path) as f:
        bp = json.load(f)
    for entry in bp['VoxelData']:
        if (entry['h'] == h and entry['x']['$numberLong'] == cx
                and entry['y']['$numberLong'] == cy and entry['z']['$numberLong'] == cz):
            vraw = base64.b64decode(entry['records']['voxel']['data']['$binary'])
            dec = lz4.block.decompress(vraw[12:], uncompressed_size=int.from_bytes(vraw[4:8], 'little'))
            idx = dec.find(b'Debug1')
            return dec[64:idx - 13], int.from_bytes(dec[idx - 13:idx - 9], 'little')
    return None, None


def check(name, real, gen):
    match = real == gen
    status = 'PASS' if match else 'FAIL'
    print(f'  [{status}] {name}: real_len={len(real)} gen_len={len(gen)}')
    if not match:
        diffs = [(i, real[i], gen[i]) for i in range(min(len(real), len(gen))) if real[i] != gen[i]]
        for i, r, gg in diffs[:10]:
            print(f'      byte {i}: real=0x{r:02x} gen=0x{gg:02x}')
        if len(real) != len(gen):
            print(f'      LENGTH MISMATCH: real={len(real)} gen={len(gen)}')
    return match


def main():
    results = []

    print('=== (2,1,2) pos-x main ===')
    tests_212 = [(1545, 1, 4, 29), (1547, 2, 4, 29), (1549, 3, 4, 29), (1551, 4, 4, 29),
                 (1567, 1, 14, 25), (1569, 1, 14, 13), (1571, 1, 14, 12)]
    for num, Nc, lz, Ye in tests_212:
        path = find_export(num)
        real, mc = decode_chunk(path, 3, 2, 1, 2)
        gen = g.generate_212_scan(Nc, mc, lz=lz, Yextent=Ye)
        results.append(check(f'{num} Nc={Nc} lz={lz} Ye={Ye}', real, gen))

    print('=== (2,2,2) pos-x pos-y ===')
    tests_222 = [(1545, 1), (1547, 2), (1549, 3), (1551, 4)]
    for num, Nc in tests_222:
        path = find_export(num)
        real, mc = decode_chunk(path, 3, 2, 2, 2)
        gen = g.generate_222_scan(Nc, mc)
        results.append(check(f'{num} Nc={Nc}', real, gen))

    print('=== (1,2,2) pos-x pos-y boundary (constant) ===')
    for num in [1545, 1547, 1549, 1551]:
        path = find_export(num)
        real, mc = decode_chunk(path, 3, 1, 2, 2)
        gen = g.generate_122_scan(mc)
        results.append(check(f'{num}', real, gen))

    print('=== (1,1,2) boundary (pos-x only) ===')
    tests_112 = [(1557, 14, 1), (1559, 14, 2), (1561, 14, 5), (1571, 14, 12),
                 (1569, 14, 13), (1567, 14, 25), (1545, 4, 29)]
    for num, lz, Ye in tests_112:
        path = find_export(num)
        real, mc = decode_chunk(path, 3, 1, 1, 2)
        gen = g.generate_112_scan(mc, lz=lz, Yextent=Ye)
        results.append(check(f'{num} lz={lz} Ye={Ye}', real, gen))

    print('=== (1,1,2) neg-x main role ===')
    for num, lz, Ye in [(1573, 14, 30)]:
        path = find_export(num)
        real, mc = decode_chunk(path, 3, 1, 1, 2)
        gen = g.generate_112_main_scan(1, mc, lz=lz, Yextent=Ye)
        results.append(check(f'{num} lz={lz} Ye={Ye}', real, gen))

    print('=== (2,1,2) neg-x boundary role ===')
    for num, lz, Ye in [(1573, 14, 30)]:
        path = find_export(num)
        real, mc = decode_chunk(path, 3, 2, 1, 2)
        gen = g.generate_212_bnd_scan(1, mc, lz=lz, Yextent=Ye)
        results.append(check(f'{num} lz={lz} Ye={Ye}', real, gen))

    print('=== (2,2,2) neg-x ===')
    for num, lz, Ye in [(1573, 14, 30), (1575, 14, 5), (1577, 14, 1)]:
        path = find_export(num)
        real, mc = decode_chunk(path, 3, 2, 2, 2)
        gen = g.generate_222_neg_scan(1, mc, lz=lz, Yextent=Ye)
        results.append(check(f'{num} lz={lz} Ye={Ye}', real, gen))

    print('=== (1,2,2) neg-x ===')
    for num, lz, Ye in [(1573, 14, 30), (1575, 14, 5), (1577, 14, 1)]:
        path = find_export(num)
        real, mc = decode_chunk(path, 3, 1, 2, 2)
        gen = g.generate_122_neg_scan(1, mc, lz=lz, Yextent=Ye)
        results.append(check(f'{num} lz={lz} Ye={Ye}', real, gen))

    print('=== cz=1 derivation (lz=0 special case) ===')
    for num in [1626, 1628]:
        path = find_export(num)
        for cx, cy in [(2, 1), (2, 2), (1, 1), (1, 2)]:
            real2, mc2 = decode_chunk(path, 3, cx, cy, 2)
            pos1_2 = next(i for i in range(len(real2))
                          if real2[i] != (0x00 if i % 2 == 0 else 0xff))
            cz2_marker = real2[pos1_2]
            real1, mc1 = decode_chunk(path, 3, cx, cy, 1)
            gen1, gen_mc1 = g.generate_cz1_scan(cx, cy, cz2_marker)
            ok = check(f'{num} ({cx},{cy},1)', real1, gen1)
            results.append(ok and mc1 == gen_mc1)

    print('=== X-axis spanning (Nc_neg=1, Nc_pos=1, Ye=1, lz=14) ===')
    path = find_export(1652)
    own_212 = (126 - 35 * 1) % 256
    own_222 = (161 + 55 * 1 + 35) % 256
    own_112 = (158 - 35 * 1) % 256
    own_122 = (own_222 + 32) % 256
    for role, cx, cy, cz, own, pos1 in [
            ('212', 2, 1, 2, own_212, 19), ('222', 2, 2, 2, own_222, 9),
            ('112', 1, 1, 2, own_112, 325), ('122', 1, 2, 2, own_122, 317)]:
        real, real_mc = decode_chunk(path, 3, cx, cy, cz)
        gen = g.generate_xspan_scan(role, own, real_mc, pos1)
        results.append(check(f'1652 {role} ({cx},{cy},{cz})', real, gen))

    print('=== Y-axis spanning (Ye_neg=1, Ye_pos=1, Nc=1, lz=14) ===')
    path = find_export(1658)
    for role, cx, cy, cz, base_own, base_mc, pos1 in [
            ('212', 2, 1, 2, 1, 631, 29), ('222', 2, 2, 2, 161, 727, 19),
            ('112', 1, 1, 2, 33, 599, 335), ('122', 1, 2, 2, 193, 695, 325)]:
        real, real_mc = decode_chunk(path, 3, cx, cy, cz)
        gen, gen_mc = g.generate_yspan_scan(role, base_own, base_mc, pos1)
        results.append(check(f'1658 {role} ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)

    print('=== Z-axis spanning, far-z pairing (Nc=1, neither side at lz=0) ===')
    path = find_export(1665)
    for role, cx, cy, base_own, base_mc, pos1 in [
            ('212', 2, 1, 1, 631, 29), ('222', 2, 2, 161, 727, 19),
            ('112', 1, 1, 33, 599, 335), ('122', 1, 2, 193, 695, 325)]:
        cz2_scan, cz2_mc, cz1_scan, cz1_mc = g.generate_zspan_farz_pair(role, base_own, base_mc, pos1)
        real2, real_mc2 = decode_chunk(path, 3, cx, cy, 2)
        real1, real_mc1 = decode_chunk(path, 3, cx, cy, 1)
        results.append(check(f'1665 {role} ({cx},{cy},2)', real2, cz2_scan) and real_mc2 == cz2_mc)
        results.append(check(f'1665 {role} ({cx},{cy},1)', real1, cz1_scan) and real_mc1 == cz1_mc)

    print('=== Multi-z stacking, contiguous (Nc=1, Ye=1) ===')
    base_map = {
        (2, 1): ('212', 1, 631, 29), (2, 2): ('222', 161, 727, 19),
        (1, 1): ('112', 33, 599, 335), (1, 2): ('122', 193, 695, 325),
    }
    path = find_export(1628)  # lz_near=0, lz_far=14 (touches cz=1)
    for (cx, cy), (role, base_own, base_mc, pos1) in base_map.items():
        real2, real_mc2 = decode_chunk(path, 3, cx, cy, 2)
        gen2, gen_mc2, first_marker = g.generate_multiz_scan(role, base_own, base_mc, 0, 14, pos1)
        results.append(check(f'1628 {role} ({cx},{cy},2)', real2, gen2) and real_mc2 == gen_mc2)
        real1, real_mc1 = decode_chunk(path, 3, cx, cy, 1)
        gen1, gen_mc1 = g.generate_cz1_scan(cx, cy, first_marker)
        results.append(check(f'1628 {role} ({cx},{cy},1)', real1, gen1) and real_mc1 == gen_mc1)

    path = find_export(1583)  # lz_near=12, lz_far=14, range=2 (no cz=1)
    for (cx, cy), (role, base_own, base_mc, pos1) in base_map.items():
        real2, real_mc2 = decode_chunk(path, 3, cx, cy, 2)
        gen2, gen_mc2, _ = g.generate_multiz_scan(role, base_own, base_mc, 12, 14, pos1)
        results.append(check(f'1583 {role} ({cx},{cy},2)', real2, gen2) and real_mc2 == gen_mc2)

    path = find_export(1907)  # lz_near=7, lz_far=14, range=8, contiguous (no cz=1)
    for (cx, cy), (role, base_own, base_mc, pos1) in base_map.items():
        real2, real_mc2 = decode_chunk(path, 3, cx, cy, 2)
        gen2, gen_mc2, _ = g.generate_multiz_scan(role, base_own, base_mc, 7, 14, pos1)
        results.append(check(f'1907 {role} ({cx},{cy},2)', real2, gen2) and real_mc2 == gen_mc2)

    print('=== Sparse multi-z, K=2 (single gap between two real z-levels) ===')
    path = find_export(1581)  # lz_near=7, lz_far=14, no cz=1
    for (cx, cy), (role, base_own, base_mc, pos1) in base_map.items():
        real, real_mc = decode_chunk(path, 3, cx, cy, 2)
        gen, gen_mc = g.generate_sparse_multiz_scan(role, base_own, base_mc, 7, 14, pos1)
        results.append(check(f'1581 {role} ({cx},{cy},2)', real, gen) and real_mc == gen_mc)

    path = find_export(1579)  # lz_near=0, lz_far=14 (touches cz=1)
    for (cx, cy), (role, base_own, base_mc, pos1) in base_map.items():
        real2, real_mc2 = decode_chunk(path, 3, cx, cy, 2)
        gen2, gen_mc2 = g.generate_sparse_multiz_scan(role, base_own, base_mc, 0, 14, pos1)
        results.append(check(f'1579 {role} ({cx},{cy},2)', real2, gen2) and real_mc2 == gen_mc2)
        marker1 = (base_own + 14 + 0 + 7) % 256
        real1, real_mc1 = decode_chunk(path, 3, cx, cy, 1)
        gen1, gen_mc1 = g.generate_cz1_scan(cx, cy, marker1)
        results.append(check(f'1579 {role} ({cx},{cy},1)', real1, gen1) and real_mc1 == gen_mc1)

    print('=== Sparse multi-z K=2 + Nc=2 (1903) -- generalizes Ncols beyond 1 ===')
    path = find_export(1903)
    for role, cx, cy, own, mc_nc2, pos1 in [
            ('212', 2, 1, 1, 686, 29), ('222', 2, 2, 161, 526, 19),
            ('112', 1, 1, 33, 599, 335), ('122', 1, 2, 193, 695, 325)]:
        real, real_mc = decode_chunk(path, 3, cx, cy, 2)
        gen, gen_mc = g.generate_sparse_multiz_scan(role, own, mc_nc2, 0, 14, pos1, Ncols=2)
        results.append(check(f'1903 {role}', real, gen) and real_mc == gen_mc)

    print('=== Sparse multi-z K=2, multi-level segment widths (1911: w0=2,w1=1) ===')
    path = find_export(1911)
    for role, cx, cy, own, mc_singlez, pos1 in [
            ('212', 2, 1, 1, 631, 29), ('222', 2, 2, 161, 727, 19),
            ('112', 1, 1, 33, 599, 335), ('122', 1, 2, 193, 695, 325)]:
        real, real_mc = decode_chunk(path, 3, cx, cy, 2)
        gen, gen_mc = g.generate_sparse_multiz_scan(role, own, mc_singlez, 10, 14, pos1, w0=2, w1=1)
        results.append(check(f'1911 {role}', real, gen) and real_mc == gen_mc)

    print('=== Sparse multi-z, K=3 (two gaps, real at lz=10,12,14) ===')
    path = find_export(1675)
    for (cx, cy), (role, base_own, base_mc, pos1) in base_map.items():
        real, real_mc = decode_chunk(path, 3, cx, cy, 2)
        gen, gen_mc = g.generate_multigap_multiz_scan(role, base_own, base_mc, [10, 12, 14], pos1)
        results.append(check(f'1675 {role} ({cx},{cy},2)', real, gen) and real_mc == gen_mc)

    print('=== Sparse multi-z, K=3, multi-level sub-runs (1915: widths 2,1,2) ===')
    path = find_export(1915)
    for (cx, cy), (role, base_own, base_mc, pos1) in base_map.items():
        real, real_mc = decode_chunk(path, 3, cx, cy, 2)
        gen, gen_mc = g.generate_multigap_multiz_scan(role, base_own, base_mc, [(10, 11), 13, (15, 16)], pos1)
        results.append(check(f'1915 {role} ({cx},{cy},2)', real, gen) and real_mc == gen_mc)

    print('=== Multi-z + Nc=2, Ye=1 (1636) ===')
    path = find_export(1636)
    for role, cx, cy, base_own, base_mc_nc2, base_cz1_mc, pos1 in [
            ('212', 2, 1, 1, 686, 578, 29), ('222', 2, 2, 161, 526, 674, 19)]:
        real2, real_mc2 = decode_chunk(path, 3, cx, cy, 2)
        gen2, gen_mc2 = g.generate_multiz_nc2_scan(role, base_own, base_mc_nc2, 0, 14, pos1)
        results.append(check(f'1636 {role} ({cx},{cy},2)', real2, gen2) and real_mc2 == gen_mc2)
        cz2_marker1 = (base_own + 14 + 0 + 7) % 256
        real1, real_mc1 = decode_chunk(path, 3, cx, cy, 1)
        gen1, gen_mc1 = g.generate_cz1_nc2_scan(role, cz2_marker1, base_cz1_mc, pos1)
        results.append(check(f'1636 {role} ({cx},{cy},1)', real1, gen1) and real_mc1 == gen_mc1)
    for role, cx, cy, base_own, base_mc, pos1 in [
            ('112', 1, 1, 33, 599, 335), ('122', 1, 2, 193, 695, 325)]:
        real, real_mc = decode_chunk(path, 3, cx, cy, 2)
        gen, gen_mc, _ = g.generate_multiz_scan(role, base_own, base_mc, 0, 14, pos1)
        results.append(check(f'1636 {role} ({cx},{cy},2) (boundary, unaffected by Nc)', real, gen) and real_mc == gen_mc)

    print('=== Multi-z + Nc>1 AND Ye>1 (1638: Nc=2,Ye=2; 1640: Nc=3,Ye=2) ===')
    for exp_num, Ncols, mc222 in [(1638, 2, 526), (1640, 3, 581)]:
        path = find_export(exp_num)
        real, real_mc = decode_chunk(path, 3, 2, 1, 2)
        gen, gen_mc = g.generate_multiz_nc_ye_212family_scan(
            '212', Ncols, 222, 686 if Ncols == 2 else 741, 0, 14, 2, 27)
        results.append(check(f'{exp_num} 212', real, gen) and real_mc == gen_mc)

        real, real_mc = decode_chunk(path, 3, 1, 1, 2)
        gen, gen_mc = g.generate_multiz_nc_ye_212family_scan('112', Ncols, 254, 599, 0, 14, 2, 333)
        results.append(check(f'{exp_num} 112', real, gen) and real_mc == gen_mc)

        real, real_mc = decode_chunk(path, 3, 2, 2, 2)
        gen, gen_mc = g.generate_multiz_nc_ye_222family_scan('222', Ncols, 161, mc222, 0, 14, 2, 19)
        results.append(check(f'{exp_num} 222', real, gen) and real_mc == gen_mc)

        real, real_mc = decode_chunk(path, 3, 1, 2, 2)
        gen, gen_mc = g.generate_multiz_nc_ye_222family_scan('122', Ncols, 193, 695, 0, 14, 2, 325)
        results.append(check(f'{exp_num} 122', real, gen) and real_mc == gen_mc)

    print('=== Multi-z + Nc>1 AND Ye>1, cz=1 siblings (1638: Nc=2; 1640: Nc=3) ===')
    for exp_num, Ncols in [(1638, 2), (1640, 3)]:
        path = find_export(exp_num)
        real, real_mc = decode_chunk(path, 3, 2, 1, 1)
        gen, gen_mc = g.generate_cz1_nc_ye_212family_scan('212', True, Ncols, 208, 578, 2, 27)
        results.append(check(f'{exp_num} 212 cz1', real, gen) and real_mc == gen_mc)

        real, real_mc = decode_chunk(path, 3, 1, 1, 1)
        gen, gen_mc = g.generate_cz1_nc_ye_212family_scan('112', False, Ncols, 240, 546, 2, 335)
        results.append(check(f'{exp_num} 112 cz1', real, gen) and real_mc == gen_mc)

        real, real_mc = decode_chunk(path, 3, 2, 2, 1)
        gen, gen_mc = g.generate_cz1_nc_ye_222family_scan('222', True, Ncols, 147, 674, 19)
        results.append(check(f'{exp_num} 222 cz1', real, gen) and real_mc == gen_mc)

        real, real_mc = decode_chunk(path, 3, 1, 2, 1)
        gen, gen_mc = g.generate_cz1_nc_ye_222family_scan('122', False, Ncols, 179, 642, 325)
        results.append(check(f'{exp_num} 122 cz1', real, gen) and real_mc == gen_mc)

    print('=== Multi-z + Nc=2 AND Ye=3 (1899) -- generalizes Ye beyond 2 ===')
    path = find_export(1899)
    real, real_mc = decode_chunk(path, 3, 2, 1, 2)
    gen, gen_mc = g.generate_multiz_nc_ye_212family_scan('212', 2, 187, 686, 0, 14, 3, 27)
    results.append(check('1899 212 cz2', real, gen) and real_mc == gen_mc)
    real, real_mc = decode_chunk(path, 3, 1, 1, 2)
    gen, gen_mc = g.generate_multiz_nc_ye_212family_scan('112', 2, 219, 599, 0, 14, 3, 333)
    results.append(check('1899 112 cz2', real, gen) and real_mc == gen_mc)
    real, real_mc = decode_chunk(path, 3, 2, 2, 2)
    gen, gen_mc = g.generate_multiz_nc_ye_222family_scan('222', 2, 161, 526, 0, 14, 3, 19)
    results.append(check('1899 222 cz2', real, gen) and real_mc == gen_mc)
    real, real_mc = decode_chunk(path, 3, 1, 2, 2)
    gen, gen_mc = g.generate_multiz_nc_ye_222family_scan('122', 2, 193, 695, 0, 14, 3, 325)
    results.append(check('1899 122 cz2', real, gen) and real_mc == gen_mc)
    real, real_mc = decode_chunk(path, 3, 2, 1, 1)
    gen, gen_mc = g.generate_cz1_nc_ye_212family_scan('212', True, 2, 173, 578, 3, 27)
    results.append(check('1899 212 cz1', real, gen) and real_mc == gen_mc)
    real, real_mc = decode_chunk(path, 3, 1, 1, 1)
    gen, gen_mc = g.generate_cz1_nc_ye_212family_scan('112', False, 2, 205, 546, 3, 333)
    results.append(check('1899 112 cz1', real, gen) and real_mc == gen_mc)
    real, real_mc = decode_chunk(path, 3, 2, 2, 1)
    gen, gen_mc = g.generate_cz1_nc_ye_222family_scan('222', True, 2, 147, 674, 19)
    results.append(check('1899 222 cz1', real, gen) and real_mc == gen_mc)
    real, real_mc = decode_chunk(path, 3, 1, 2, 1)
    gen, gen_mc = g.generate_cz1_nc_ye_222family_scan('122', False, 2, 179, 642, 325)
    results.append(check('1899 122 cz1', real, gen) and real_mc == gen_mc)

    print('=== Offset/staggered voxel sets, Ncols=2, Ye=1-each (1806: offset=0, 1677: +1, 1804: -1) ===')
    for exp_num, row_offset in [(1806, 0), (1677, 1), (1804, -1)]:
        path = find_export(exp_num)
        real, real_mc = decode_chunk(path, 3, 2, 1, 2)
        gen = g.generate_offset_212family_scan('212', 1, 199, row_offset, real_mc, 29)
        results.append(check(f'{exp_num} 212', real, gen))

        real, real_mc = decode_chunk(path, 3, 2, 2, 2)
        gen = g.generate_offset_212family_scan('222', 161, 199, row_offset, real_mc, 19)
        results.append(check(f'{exp_num} 222', real, gen))

    print('=== Offset/staggered voxel sets, Ncols=3 (1927: offsets +1,+2 from col1) ===')
    path = find_export(1927)
    real, real_mc = decode_chunk(path, 3, 2, 1, 2)
    gen = g.generate_offset_212family_multicol_scan(1, 199, [1, 2], real_mc, 29)
    results.append(check('1927 212 Ncols=3', real, gen))

    print('=== Offset/staggered, cross-chunk sign-crossing (1804 n_extra=1, 1925 n_extra=2) ===')
    path = find_export(1804)
    real, real_mc = decode_chunk(path, 3, 2, 2, 2)
    gen = g.generate_offset_crosschunk_other_scan('222', 161, 1, real_mc, 19)
    results.append(check('1804 222 n_extra=1', real, gen))

    path = find_export(1925)
    real, real_mc = decode_chunk(path, 3, 2, 1, 2)
    gen = g.generate_offset_212family_scan('212', 1, 199, -1, real_mc, 29)
    results.append(check('1925 212 anchor unchanged', real, gen))
    real, real_mc = decode_chunk(path, 3, 2, 2, 2)
    gen = g.generate_offset_crosschunk_other_scan('222', 161, 2, real_mc, 19)
    results.append(check('1925 222 n_extra=2', real, gen))

    print('=== Y positive far edge, isolated (1739) -- pure role relabel ===')
    path = find_export(1739)
    real, real_mc = decode_chunk(path, 3, 2, 2, 2)
    results.append(check('(2,2,2) as 212-role', real, g.generate_212_scan(1, real_mc, lz=14, Yextent=1)))
    real, real_mc = decode_chunk(path, 3, 2, 3, 2)
    results.append(check('(2,3,2) as 222-role', real, g.generate_222_scan(1, real_mc)))
    real, real_mc = decode_chunk(path, 3, 1, 2, 2)
    results.append(check('(1,2,2) as 112-role', real, g.generate_112_scan(real_mc, lz=14, Yextent=1)))
    real, real_mc = decode_chunk(path, 3, 1, 3, 2)
    results.append(check('(1,3,2) as 122-role', real, g.generate_122_scan(real_mc)))

    print('=== X negative far edge, isolated (1737) -- role-shift + universal +35/-35 ===')
    path = find_export(1737)
    real, real_mc = decode_chunk(path, 3, 1, 1, 2)
    results.append(check('(1,1,2) shifted 212', real, g.generate_zspan_side_scan('212', 36, real_mc, 29)))
    real, real_mc = decode_chunk(path, 3, 1, 2, 2)
    results.append(check('(1,2,2) shifted 222', real, g.generate_zspan_side_scan('222', 196, real_mc, 19)))
    real, real_mc = decode_chunk(path, 3, 0, 1, 2)
    results.append(check('(0,1,2) shifted 112', real, g.generate_zspan_side_scan('112', 68, real_mc, 335)))
    real, real_mc = decode_chunk(path, 3, 0, 2, 2)
    results.append(check('(0,2,2) shifted 122', real, g.generate_zspan_side_scan('122', 228, real_mc, 325)))

    print('=== Y negative far edge, isolated (1745) -- role-shift + doubled +70/-70 ===')
    path = find_export(1745)
    real, real_mc = decode_chunk(path, 3, 2, 1, 2)
    results.append(check('(2,1,2) shifted 222', real, g.generate_zspan_side_scan('222', 231, real_mc, 19)))
    real, real_mc = decode_chunk(path, 3, 2, 0, 2)
    results.append(check('(2,0,2) shifted 212', real, g.generate_zspan_side_scan('212', 71, real_mc, 29)))
    real, real_mc = decode_chunk(path, 3, 1, 1, 2)
    results.append(check('(1,1,2) shifted 122', real, g.generate_yneg_faredge_122_scan(7, real_mc)))
    real, real_mc = decode_chunk(path, 3, 1, 0, 2)
    results.append(check('(1,0,2) shifted 112', real, g.generate_zspan_side_scan('112', 103, real_mc, 335)))

    print('=== X positive far edge, isolated (1735) -- new +32 chunk-pairing ===')
    path = find_export(1735)
    real, real_mc = decode_chunk(path, 3, 2, 1, 2)
    results.append(check('(2,1,2) main', real, g.generate_xpos_faredge_main_scan('212', 178, real_mc)))
    real, real_mc = decode_chunk(path, 3, 2, 2, 2)
    results.append(check('(2,2,2) main', real, g.generate_xpos_faredge_main_scan('222', 82, real_mc)))
    real, real_mc = decode_chunk(path, 3, 3, 1, 2)
    results.append(check('(3,1,2) edge', real, g.generate_xpos_faredge_edge_scan('212', 178, real_mc)))
    real, real_mc = decode_chunk(path, 3, 3, 2, 2)
    results.append(check('(3,2,2) edge', real, g.generate_xpos_faredge_edge_scan('222', 82, real_mc)))

    print('=== X positive far edge, Nc_normal=1 (1919) -- generalizes beyond isolated ===')
    path = find_export(1919)
    real, real_mc = decode_chunk(path, 3, 2, 1, 2)
    gen = g.generate_xpos_faredge_main_scan('212', (178 + 55 * 1) % 256, real_mc, Nc_normal=1)
    results.append(check('1919 (2,1,2) main', real, gen))
    real, real_mc = decode_chunk(path, 3, 2, 2, 2)
    gen = g.generate_xpos_faredge_main_scan('222', (82 + 55 * 1) % 256, real_mc, Nc_normal=1)
    results.append(check('1919 (2,2,2) main', real, gen))
    real, real_mc = decode_chunk(path, 3, 3, 1, 2)
    results.append(check('1919 (3,1,2) edge', real, g.generate_xpos_faredge_edge_scan('212', 178, real_mc)))
    real, real_mc = decode_chunk(path, 3, 3, 2, 2)
    results.append(check('1919 (3,2,2) edge', real, g.generate_xpos_faredge_edge_scan('222', 82, real_mc)))

    print('=== Z positive far edge, isolated (1747) -- matches X+ pairing, distinct cz=3 groups shape ===')
    path = find_export(1747)
    for role, cx, cy, marker_cz2, pos1 in [
            ('212', 2, 1, 52, 29), ('222', 2, 2, 212, 19),
            ('112', 1, 1, 84, 335), ('122', 1, 2, 244, 325)]:
        real2, real_mc2 = decode_chunk(path, 3, cx, cy, 2)
        real3, real_mc3 = decode_chunk(path, 3, cx, cy, 3)
        cz2_scan, cz3_scan, gen_mc3 = g.generate_zpos_faredge_pair_scan(role, marker_cz2, real_mc2, pos1)
        results.append(check(f'{role} ({cx},{cy},2)', real2, cz2_scan))
        results.append(check(f'{role} ({cx},{cy},3)', real3, cz3_scan) and real_mc3 == gen_mc3)

    print('=== Z negative far edge, isolated (1750) -- reuses near-pairing marker, own mc shift ===')
    path = find_export(1750)
    for role, cx, cy, marker_cz1, pos1 in [
            ('212', 2, 1, 22, 29), ('222', 2, 2, 182, 19),
            ('112', 1, 1, 54, 335), ('122', 1, 2, 214, 325)]:
        real1, real_mc1 = decode_chunk(path, 3, cx, cy, 1)
        real0, real_mc0 = decode_chunk(path, 3, cx, cy, 0)
        cz1_scan, cz0_scan, gen_mc0 = g.generate_zneg_faredge_pair_scan(role, marker_cz1, real_mc1, pos1)
        results.append(check(f'{role} ({cx},{cy},1)', real1, cz1_scan))
        results.append(check(f'{role} ({cx},{cy},0)', real0, cz0_scan) and real_mc0 == gen_mc0)

    print('=== True 3-axis corner, 2x2x2 cube at origin (1679) -- fully-specified template ===')
    path = find_export(1679)
    for c in [(2, 1, 2), (2, 2, 2), (1, 2, 2), (1, 1, 2), (2, 1, 1), (2, 2, 1), (1, 2, 1), (1, 1, 1)]:
        real, real_mc = decode_chunk(path, 3, *c)
        gen, gen_mc = g.generate_3axis_corner_2x2x2_scan(*c)
        results.append(check(str(c), real, gen) and real_mc == gen_mc)

    print('=== role122 DENSE rectangular fill (general Ncols x Ye x N solid block) ===')
    # (exp, lx_FAR, ly_near, Ncols, Ye, lz_near, lz_far) -- N>=2, ly_near=1, not the 29&29 corner
    dense_122 = [
        ('1979', 2, 1, 2, 2, 1, 2), ('1981', 2, 1, 2, 2, 5, 6), ('1983', 3, 1, 3, 2, 1, 2),
        ('1985', 2, 1, 2, 3, 1, 2), ('1991', 2, 1, 2, 4, 1, 2), ('1995', 2, 1, 2, 15, 1, 2),
        ('1997', 2, 1, 2, 22, 1, 2), ('1999', 2, 1, 2, 29, 1, 2), ('2001', 2, 1, 2, 8, 1, 2),
        ('2007', 2, 1, 2, 2, 1, 10), ('2009', 2, 1, 2, 7, 1, 2), ('2011', 5, 1, 5, 2, 1, 2),
        ('2013', 7, 1, 7, 2, 1, 2), ('2015', 12, 1, 12, 2, 1, 2), ('2017', 26, 1, 26, 2, 1, 2),
        ('1993', 30, 1, 30, 4, 1, 2),
        # ly_near > 1 (period-7 drift on pos1/mat_off/gap2)
        ('2055', 2, 5, 2, 2, 1, 2), ('2003', 2, 10, 2, 4, 1, 2),
        ('2057', 2, 15, 2, 2, 1, 2), ('2005', 2, 20, 2, 2, 1, 2),
        # N=1 thin plate (single z-level; simple groups, no extra-pair)
        ('2059', 2, 1, 2, 2, 14, 14), ('1975', 1, 1, 1, 29, 14, 14), ('1977', 2, 1, 2, 29, 14, 14),
        # large N, and the extreme Ye&N corner (mat_off -2)
        ('2061', 2, 1, 2, 2, 1, 29), ('2063', 2, 1, 2, 24, 1, 24), ('1969', 30, 1, 30, 29, 1, 29),
        # ABSOLUTE neg-x edge touched (lx_FAR=31): MAIN (1,2,2) chunk, edge envelope
        ('2053', 31, 1, 2, 2, 1, 2), ('2065', 31, 1, 3, 2, 1, 2), ('2067', 31, 1, 2, 4, 1, 2),
        ('2069', 31, 1, 2, 2, 1, 10), ('2071', 31, 5, 2, 2, 1, 2), ('2073', 31, 1, 2, 8, 1, 2),
    ]
    for exp, lxF, lyN, Nc, Ye, lzn, lzf in dense_122:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 2, 2)
        gen, gen_mc = g.generate_122_dense_scan(lxF, lyN, Nc, Ye, lzn, lzf)
        results.append(check(f'122-dense {exp}', real, gen) and real_mc == gen_mc)

    print('=== role122 absolute neg-x edge: spawned cx=0 boundary + empty chunks ===')
    for exp, Ye, lzn, lzf, ly in [('2053', 2, 1, 2, 1), ('2067', 4, 1, 2, 1), ('2073', 8, 1, 2, 1),
                                   ('2069', 2, 1, 10, 1), ('2071', 2, 1, 2, 5)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 0, 2, 2)
        gen, gen_mc = g.generate_122_edge_cx0_scan(Ye, lzn, lzf, ly)
        results.append(check(f'122-edge-cx0 {exp}', real, gen) and real_mc == gen_mc)
    for c in [(0, 1, 1), (0, 2, 1), (1, 1, 1), (1, 2, 1), (0, 1, 2), (1, 1, 2)]:
        real, real_mc = decode_chunk(find_export('2053'), 3, *c)
        gen, gen_mc = g.generate_122_edge_empty_scan()
        results.append(check(f'122-edge-empty {c}', real, gen) and real_mc == gen_mc)

    print('=== role122 pos-x spanning-awareness (2,2,2) chunk (always spawned) ===')
    for exp, Ye, lzn, lzf, ly in [('1979', 2, 1, 2, 1), ('1985', 3, 1, 2, 1), ('1991', 4, 1, 2, 1),
                                   ('2009', 7, 1, 2, 1), ('2001', 8, 1, 2, 1), ('2007', 2, 1, 10, 1),
                                   ('1981', 2, 5, 6, 1), ('2055', 2, 1, 2, 5), ('2005', 2, 1, 2, 20),
                                   ('2081', 2, 1, 2, 29)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 2)
        gen, gen_mc = g.generate_122_spanning_222_scan(Ye, lzn, lzf, ly)
        results.append(check(f'122-span222 {exp}', real, gen) and real_mc == gen_mc)

    print('=== role122 Y+ edge (y=+30.5) boundary chunks (1,3,2) and (2,3,2) ===')
    for exp, Nc, lzn, lzf in [('2081', 2, 1, 2), ('2083', 3, 1, 2), ('2085', 2, 1, 2), ('2087', 2, 1, 10)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 3, 2)
        gen, gen_mc = g.generate_122_yedge_132_scan(Nc, lzn, lzf)
        results.append(check(f'122-yedge132 {exp}', real, gen) and real_mc == gen_mc)
        N = lzf - lzn + 1
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 3, 2)
        gen, gen_mc = g.generate_122_yedge_232_scan(N, lzf)
        results.append(check(f'122-yedge232 {exp}', real, gen) and real_mc == gen_mc)

    print('=== role122 Z+ edge (z=+30.5) boundary chunks (1,2,3) and (2,2,3) ===')
    for exp, Nc, Ye in [('2091', 2, 2), ('2093', 3, 2), ('2095', 2, 3), ('2097', 2, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 2, 3)
        gen, gen_mc = g.generate_122_zedge_123_scan(Nc, Ye)
        results.append(check(f'122-zedge123 {exp}', real, gen) and real_mc == gen_mc)
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 3)
        gen, gen_mc = g.generate_122_zedge_223_scan(Ye)
        results.append(check(f'122-zedge223 {exp}', real, gen) and real_mc == gen_mc)

    print('=== role212 (2,1,2) pos-x/neg-y dense fill (mirror of role122) ===')
    # (exp, lx_near, ly_near, Ncols, Ye, lz_near, lz_far)
    for exp, lxn, lyn, Nc, Ye, lzn, lzf in [
            ('2101', 1, 1, 2, 2, 1, 2), ('2103', 1, 1, 2, 2, 5, 6), ('2105', 2, 1, 2, 2, 1, 2),
            ('2107', 1, 2, 2, 2, 1, 2), ('2109', 1, 1, 3, 2, 1, 2), ('2111', 1, 1, 2, 3, 1, 2),
            ('2117', 10, 1, 2, 2, 1, 2), ('2127', 1, 10, 2, 2, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 1, 2)
        gen, gen_mc = g.generate_212_dense_scan(lxn, lyn, Nc, Ye, lzn, lzf)
        results.append(check(f'212-dense {exp}', real, gen) and real_mc == gen_mc)

    print('=== role212 spanning (2,2,2) chunk (spawned iff ly_near=1) ===')
    for exp, lxn, Nc, lzn, lzf in [('2101', 1, 2, 1, 2), ('2103', 1, 2, 5, 6), ('2105', 2, 2, 1, 2),
                                    ('2109', 1, 3, 1, 2), ('2111', 1, 2, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 2)
        gen, gen_mc = g.generate_212_spanning_222_scan(lxn, Nc, lzn, lzf)
        results.append(check(f'212-span {exp}', real, gen) and real_mc == gen_mc)

    print('=== role212 pos-x edge (x=+30.5): main, (3,1,2), (3,2,2), spanning ===')
    for exp, Ye, lzn, lzf in [('2115', 2, 1, 2), ('2119', 3, 1, 2), ('2121', 2, 5, 6)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 3, 1, 2)
        gen, gen_mc = g.generate_212_xedge_312_scan(Ye, lzn, lzf)
        results.append(check(f'212-xedge312 {exp}', real, gen) and real_mc == gen_mc)
    # full pos-x edge (2115): main(edge), spanning, (3,1,2), (3,2,2), 4 empties
    for cx, cy, cz, fn in [
            (2, 1, 2, lambda: g.generate_212_dense_scan(29, 1, 2, 2, 1, 2)),
            (2, 2, 2, lambda: g.generate_212_spanning_222_scan(29, 2, 1, 2)),
            (3, 1, 2, lambda: g.generate_212_xedge_312_scan(2, 1, 2)),
            (3, 2, 2, lambda: g.generate_122_yedge_232_scan(2, 2))]:
        real, real_mc = decode_chunk(find_export('2115'), 3, cx, cy, cz)
        gen, gen_mc = fn()
        results.append(check(f'212-xedge full ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)

    print('=== role212 neg-y edge (y=-31.5): main + (2,0,2) boundary ===')
    for exp, Nc, lzn, lzf in [('2125', 2, 1, 2), ('2133', 2, 5, 6), ('2135', 2, 1, 6), ('2129', 3, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 0, 2)
        gen, gen_mc = g.generate_212_negyedge_202_scan(Nc, lzn, lzf)
        results.append(check(f'212-negy202 {exp}', real, gen) and real_mc == gen_mc)
    for cx, cy, cz, fn in [
            (2, 1, 2, lambda: g.generate_212_dense_scan(1, 30, 2, 2, 1, 2)),
            (2, 0, 2, lambda: g.generate_212_negyedge_202_scan(2, 1, 2))]:
        real, real_mc = decode_chunk(find_export('2125'), 3, cx, cy, cz)
        gen, gen_mc = fn()
        results.append(check(f'212-negy full ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)

    print('=== role212 z edge (z=+30.5): (2,1,3) and (2,2,3) cz=3 chunks ===')
    for exp, Nc, Ye in [('2139', 2, 2), ('2141', 3, 2), ('2143', 2, 3)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 1, 3)
        gen, gen_mc = g.generate_212_zedge_213_scan(Nc, Ye)
        results.append(check(f'212-zedge213 {exp}', real, gen) and real_mc == gen_mc)
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 3)
        gen, gen_mc = g.generate_212_zedge_223_scan(Nc)
        results.append(check(f'212-zedge223 {exp}', real, gen) and real_mc == gen_mc)

    print('=== role222 (2,2,2) pos-x/pos-y dense fill (reference corner, no spanning) ===')
    for exp, lxn, lyn, Nc, Ye, lzn, lzf in [
            ('2147', 1, 1, 2, 2, 1, 2), ('2149', 1, 1, 2, 2, 5, 6), ('2151', 2, 1, 2, 2, 1, 2),
            ('2153', 1, 2, 2, 2, 1, 2), ('2155', 1, 1, 3, 2, 1, 2), ('2157', 1, 1, 2, 3, 1, 2),
            ('2171', 1, 10, 2, 2, 1, 2), ('2173', 1, 15, 2, 2, 1, 2), ('2175', 1, 22, 2, 2, 1, 2),
            ('2169', 1, 29, 2, 2, 1, 2)]:  # high-ly drift (pos1/mat_off split-phase period-7)
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 2)
        gen, gen_mc = g.generate_222_dense_scan(lxn, lyn, Nc, Ye, lzn, lzf)
        results.append(check(f'222-dense {exp}', real, gen) and real_mc == gen_mc)

    print('=== role222 pos-y edge (y=+30.5): CLEAN main + (2,3,2) cy=3 boundary ===')
    for exp, lxn, Nc, lzn, lzf in [
            ('2169', 1, 2, 1, 2), ('2177', 1, 3, 1, 2), ('2179', 1, 2, 5, 6),
            ('2181', 1, 2, 1, 6), ('2183', 2, 2, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 3, 2)
        gen, gen_mc = g.generate_222_yedge_232_scan(lxn, Nc, lzn, lzf)
        results.append(check(f'222-yedge232 {exp}', real, gen) and real_mc == gen_mc)
    for cx, cy, cz, fn in [
            (2, 2, 2, lambda: g.generate_222_dense_scan(1, 29, 2, 2, 1, 2)),
            (2, 3, 2, lambda: g.generate_222_yedge_232_scan(1, 2, 1, 2))]:
        real, real_mc = decode_chunk(find_export('2169'), 3, cx, cy, cz)
        gen, gen_mc = fn()
        results.append(check(f'222-yedge full ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)

    print('=== role222 z edge (z=+30.5): CLEAN main + (2,2,3) cz=3 N=1 plate ===')
    for exp, lxn, Nc, Ye in [('2187', 1, 2, 2), ('2189', 1, 3, 2), ('2191', 1, 2, 3), ('2193', 2, 2, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 3)
        gen, gen_mc = g.generate_222_zedge_223_scan(lxn, 1, Nc, Ye)
        results.append(check(f'222-zedge223 {exp}', real, gen) and real_mc == gen_mc)
    for cx, cy, cz, fn in [
            (2, 2, 2, lambda: g.generate_222_dense_scan(1, 1, 2, 2, 29, 30)),
            (2, 2, 3, lambda: g.generate_222_zedge_223_scan(1, 1, 2, 2))]:
        real, real_mc = decode_chunk(find_export('2187'), 3, cx, cy, cz)
        gen, gen_mc = fn()
        results.append(check(f'222-zedge full ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)

    print('=== role222 pos-x edge (x=+30.5): CLEAN main + (3,2,2)=role122 spanning (reused) ===')
    # main stays dense; cx=3 boundary reuses role122 spanning chunk. Full standalone @ Nc2.
    for cx, cy, cz, fn in [
            (2, 2, 2, lambda: g.generate_222_dense_scan(29, 1, 2, 2, 1, 2)),
            (3, 2, 2, lambda: g.generate_122_spanning_222_scan(2, 1, 2, 1))]:
        real, real_mc = decode_chunk(find_export('2161'), 3, cx, cy, cz)
        gen, gen_mc = fn()
        results.append(check(f'222-xedge full ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)
    # (3,2,2) reuse is Ncols-independent (confirmed Nc2/Nc3/Nc4):
    for exp in ('2161', '2163', '2167'):
        real, real_mc = decode_chunk(find_export(exp), 3, 3, 2, 2)
        gen, gen_mc = g.generate_122_spanning_222_scan(2, 1, 2, 1)
        results.append(check(f'222-xedge (3,2,2)reuse {exp}', real, gen) and real_mc == gen_mc)

    print('=== role112 (1,1,2) neg-x/neg-y dense fill (LAST role; 3 spanning chunks WIP) ===')
    for exp, lxn, lyn, Nc, Ye, lzn, lzf in [
            ('2197', 1, 1, 2, 2, 1, 2), ('2199', 1, 1, 2, 2, 5, 6), ('2201', 2, 1, 2, 2, 1, 2),
            ('2203', 1, 2, 2, 2, 1, 2), ('2205', 1, 1, 3, 2, 1, 2), ('2207', 1, 1, 2, 3, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 1, 2)
        gen, gen_mc = g.generate_112_dense_scan(lxn, lyn, Nc, Ye, lzn, lzf)
        results.append(check(f'112-dense {exp}', real, gen) and real_mc == gen_mc)

    print('=== role112 3 spanning chunks (x-span / y-span / xy-corner) ===')
    for exp, lyn, Ye, lzn, lzf in [('2197', 1, 2, 1, 2), ('2199', 1, 2, 5, 6),
                                   ('2203', 2, 2, 1, 2), ('2205', 1, 2, 1, 2), ('2207', 1, 3, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 1, 2)
        gen, gen_mc = g.generate_112_xspan_212_scan(lyn, Ye, lzn, lzf)
        results.append(check(f'112-xspan {exp}', real, gen) and real_mc == gen_mc)
    for exp, lxn, Nc, lzn, lzf in [('2197', 1, 2, 1, 2), ('2199', 1, 2, 5, 6),
                                   ('2201', 2, 2, 1, 2), ('2205', 1, 3, 1, 2), ('2207', 1, 2, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 2, 2)
        gen, gen_mc = g.generate_112_yspan_122_scan(lxn, Nc, lzn, lzf)
        results.append(check(f'112-yspan {exp}', real, gen) and real_mc == gen_mc)
    for exp, lzn, lzf in [('2197', 1, 2), ('2199', 5, 6), ('2205', 1, 2), ('2207', 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 2)
        gen, gen_mc = g.generate_112_corner_222_scan(lzn, lzf)
        results.append(check(f'112-corner {exp}', real, gen) and real_mc == gen_mc)
    # full role112 interior standalone (2197): main + 3 spanning + 4 empties
    for cx, cy, cz, fn in [
            (1, 1, 2, lambda: g.generate_112_dense_scan(1, 1, 2, 2, 1, 2)),
            (2, 1, 2, lambda: g.generate_112_xspan_212_scan(1, 2, 1, 2)),
            (1, 2, 2, lambda: g.generate_112_yspan_122_scan(1, 2, 1, 2)),
            (2, 2, 2, lambda: g.generate_112_corner_222_scan(1, 2))]:
        real, real_mc = decode_chunk(find_export('2197'), 3, cx, cy, cz)
        gen, gen_mc = fn()
        results.append(check(f'112-interior full ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)

    print('=== role112 neg-x edge (x=-31.5): main re-envelope + (0,1,2) cx=0 boundary ===')
    for exp, lxn, lyn, Nc, Ye in [('2213', 30, 5, 2, 2), ('2214', 29, 5, 3, 2), ('2218', 30, 5, 2, 3)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 1, 2)
        gen, gen_mc = g.generate_112_dense_scan(lxn, lyn, Nc, Ye, 1, 2)
        results.append(check(f'112-negx main {exp}', real, gen) and real_mc == gen_mc)
    for exp, ly, Ye, lzn, lzf in [('2213', 5, 2, 1, 2), ('2216', 5, 2, 5, 6), ('2218', 5, 3, 1, 2),
                                  ('2220', 6, 2, 1, 2), ('2214', 5, 2, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 0, 1, 2)
        gen, gen_mc = g.generate_112_negxedge_012_scan(ly, Ye, lzn, lzf)
        results.append(check(f'112-negx012 {exp}', real, gen) and real_mc == gen_mc)

    print('=== role112 main high-ly drift sweep (ly 10/14/20/28, deep-x) ===')
    for exp, lyn in [('2226', 10), ('2228', 14), ('2224', 20), ('2230', 28)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 1, 2)
        gen, gen_mc = g.generate_112_dense_scan(5, lyn, 2, 2, 1, 2)
        results.append(check(f'112-dense-highly {exp}', real, gen) and real_mc == gen_mc)

    print('=== role112 neg-y edge (y=-31.5): CLEAN main (hardened dense) + (1,0,2) cy=0 ===')
    for exp, lxn, Nc, lzn, lzf in [('2222', 5, 2, 1, 2), ('2234', 5, 2, 5, 6), ('2232', 5, 3, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 0, 2)
        gen, gen_mc = g.generate_112_negyedge_102_scan(lxn, Nc, lzn, lzf)
        results.append(check(f'112-negy102 {exp}', real, gen) and real_mc == gen_mc)
    for cx, cy, cz, fn in [
            (1, 1, 2, lambda: g.generate_112_dense_scan(5, 30, 2, 2, 1, 2)),
            (1, 0, 2, lambda: g.generate_112_negyedge_102_scan(5, 2, 1, 2))]:
        real, real_mc = decode_chunk(find_export('2222'), 3, cx, cy, cz)
        gen, gen_mc = fn()
        results.append(check(f'112-negy full ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)

    print('=== role112 z edge (z=+30.5): main re-envelope(-2) + (1,1,3) cz=3 plate [LAST EDGE] ===')
    for exp, lxn, lyn, Nc, Ye in [('2240', 5, 5, 2, 2), ('2242', 5, 5, 3, 2), ('2244', 5, 5, 2, 3),
                                  ('2248', 5, 10, 2, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 1, 3)
        gen, gen_mc = g.generate_112_zedge_113_scan(lxn, lyn, Nc, Ye)
        results.append(check(f'112-zedge113 {exp}', real, gen) and real_mc == gen_mc)
    for cx, cy, cz, fn in [
            (1, 1, 2, lambda: g.generate_112_dense_scan(5, 5, 2, 2, 29, 30)),
            (1, 1, 3, lambda: g.generate_112_zedge_113_scan(5, 5, 2, 2))]:
        real, real_mc = decode_chunk(find_export('2240'), 3, cx, cy, cz)
        gen, gen_mc = fn()
        results.append(check(f'112-zedge full ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)

    print('=== NEGATIVE Z (cz=1) dense mains -- all 4 roles ===')
    # role222 (pos-x/pos-y): clean shift
    for exp, lzn, lzf in [('2254', 1, 2), ('2256', 5, 6)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 1)
        gen, gen_mc = g.generate_222_dense_scan(1, 1, 2, 2, lzn, lzf, cz=1)
        results.append(check(f'222-cz1 {exp}', real, gen) and real_mc == gen_mc)
    # role212 (pos-x/neg-y): clean shift
    real, real_mc = decode_chunk(find_export('2260'), 3, 2, 1, 1)
    gen, gen_mc = g.generate_212_dense_scan(5, 5, 2, 2, 5, 6, cz=1)
    results.append(check('212-cz1 2260', real, gen) and real_mc == gen_mc)
    # role122 (neg-x/pos-y): anchor+zsh, mat_off+38/gap2-(38+2(Nc-2)), mc+(2lz+6)
    for exp, lxF, Nc, Ye, lzn, lzf in [('2258', 6, 2, 2, 5, 6), ('2263', 6, 2, 2, 1, 2),
                                       ('2273', 7, 3, 2, 5, 6), ('2285', 6, 2, 3, 5, 6)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 2, 1)
        gen, gen_mc = g.generate_122_dense_scan(lxF, 5, Nc, Ye, lzn, lzf, cz=1)
        results.append(check(f'122-cz1 {exp}', real, gen) and real_mc == gen_mc)
    # role112 (neg-x/neg-y): anchor+zsh, mc-zsh, mat_off-2/gap2+2, pos1 ceil-residual
    for exp, Nc, lzn, lzf in [('2265', 2, 5, 6), ('2267', 2, 1, 2), ('2269', 2, 10, 11), ('2271', 3, 5, 6)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 1, 1)
        gen, gen_mc = g.generate_112_dense_scan(5, 5, Nc, 2, lzn, lzf, cz=1)
        results.append(check(f'112-cz1 {exp}', real, gen) and real_mc == gen_mc)
    # cz=1 Z-SPAN (lz_near=1 adjacent to z=0) == the role's z-EDGE cz=3 chunk REUSED:
    real, real_mc = decode_chunk(find_export('2267'), 3, 1, 1, 2)
    gen, gen_mc = g.generate_112_zedge_113_scan(5, 5, 2, 2)
    results.append(check('112-zspan==zedge113 2267', real, gen) and real_mc == gen_mc)
    real, real_mc = decode_chunk(find_export('2254'), 3, 2, 2, 2)
    gen, gen_mc = g.generate_222_zedge_223_scan(1, 1, 2, 2)
    results.append(check('222-zspan==zedge223 2254', real, gen) and real_mc == gen_mc)
    # role122 z-span (1,2,2) = lx/ly-general zedge_123 (exports 2263 lx5, 2275 lx10):
    for exp, lxn in [('2263', 5), ('2275', 10)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 2, 2)
        gen, gen_mc = g.generate_122_zedge_123_scan(2, 2, lx_near=lxn, ly_near=5)
        results.append(check(f'122-zspan {exp}', real, gen) and real_mc == gen_mc)
    # role212 z-span (2,1,2) -- own dense-N=1 plate (NOT zedge_213); neg-y mirror
    # of role222 zedge_223 (exports 2277/2279/2281/2283):
    for exp, lxn, lyn, Ye in [('2277', 5, 5, 2), ('2279', 2, 5, 2), ('2281', 5, 2, 2), ('2283', 5, 5, 3)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 1, 2)
        gen, gen_mc = g.generate_212_zspan_212_scan(lxn, lyn, 2, Ye)
        results.append(check(f'212-zspan {exp}', real, gen) and real_mc == gen_mc)
    # cz=1 + neg-x EDGE composition (export 2287): main suppresses cz=1 structural
    # delta at the edge but keeps value shifts; (0,1,1) boundary takes cz=1 shift.
    for cx, cy, cz, fn in [
            (1, 1, 1, lambda: g.generate_112_dense_scan(30, 5, 2, 2, 5, 6, cz=1)),
            (0, 1, 1, lambda: g.generate_112_negxedge_012_scan(5, 2, 5, 6, cz=1))]:
        real, real_mc = decode_chunk(find_export('2287'), 3, cx, cy, cz)
        gen, gen_mc = fn()
        results.append(check(f'112-negxedge+cz1 ({cx},{cy},{cz})', real, gen) and real_mc == gen_mc)

    print('=== MULTI-QUADRANT: neg-x crossing side (1,2,2), x=0 crossing ===')
    for exp, nc, ly, Ye, lzn, lzf in [('2291', 1, 1, 2, 1, 2), ('2295', 2, 1, 2, 1, 2),
                                      ('2252', 3, 1, 2, 1, 2), ('2297', 1, 1, 2, 5, 6),
                                      ('2300', 1, 2, 2, 1, 2), ('2303', 1, 1, 3, 1, 2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 1, 2, 2)
        gen, gen_mc = g.generate_negx_crossing_122_scan(nc, ly, Ye, lzn, lzf)
        results.append(check(f'negx-crossing {exp}', real, gen) and real_mc == gen_mc)

    print('=== MULTI-QUADRANT: pos-x crossing side (2,2,2) -- interface, both sides ===')
    for exp, nn, pp, ly, Ye, lzn, lzf in [('2291',1,1,1,2,1,2),('2293',1,2,1,2,1,2),
            ('2295',2,1,1,2,1,2),('2338',3,1,1,2,1,2),('2340',1,3,1,2,1,2),
            ('2252',3,3,1,2,1,2),('2297',1,1,1,2,5,6),('2300',1,1,2,2,1,2),('2303',1,1,1,3,1,2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 2)
        gen, gen_mc = g.generate_posx_crossing_222_scan(nn, pp, ly, Ye, lzn, lzf)
        results.append(check(f'posx-crossing {exp}', real, gen) and real_mc == gen_mc)

    print('=== MULTI-QUADRANT: y=0 crossing -- neg-y (2,1,2) + pos-y (2,2,2) ===')
    for exp, lxn, nr, Nc, lzn, lzf in [('2342',1,1,2,1,2),('2346',1,2,2,1,2),
            ('2348',1,1,2,5,6),('2350',1,1,3,1,2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 1, 2)
        gen, gen_mc = g.generate_negy_crossing_212_scan(lxn, nr, Nc, lzn, lzf)
        results.append(check(f'negy-crossing {exp}', real, gen) and real_mc == gen_mc)
    for exp, lxn, nr, pr, Nc, lzn, lzf in [('2342',1,1,1,2,1,2),('2344',1,1,2,2,1,2),
            ('2346',1,2,1,2,1,2),('2354',1,3,1,2,1,2),('2348',1,1,1,2,5,6),('2350',1,1,1,3,1,2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 2)
        gen, gen_mc = g.generate_posy_crossing_222_scan(lxn, nr, pr, Nc, lzn, lzf)
        results.append(check(f'posy-crossing {exp}', real, gen) and real_mc == gen_mc)

    print('=== MULTI-QUADRANT: z=0 crossing -- cz=1 neg-z (2,2,1) + cz=2 pos-z (2,2,2) ===')
    for exp, nz, Nc, Ye in [('2352',1,2,2),('2358',2,2,2),('2360',1,3,2),('2362',1,2,3),('2356',1,2,2)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 1)
        gen, gen_mc = g.generate_negz_crossing_222_scan(1, 1, nz, Nc, Ye)
        results.append(check(f'negz-crossing {exp}', real, gen) and real_mc == gen_mc)
    for exp, nz, pz, Nc, Ye in [('2352',1,1,2,2),('2356',1,2,2,2),('2358',2,1,2,2),('2360',1,1,3,2),('2362',1,1,2,3)]:
        real, real_mc = decode_chunk(find_export(exp), 3, 2, 2, 2)
        gen, gen_mc = g.generate_posz_crossing_222_scan(1, 1, nz, pz, Nc, Ye)
        results.append(check(f'posz-crossing {exp}', real, gen) and real_mc == gen_mc)
    # lx2 generalization (both z=0 sides):
    real, real_mc = decode_chunk(find_export('2364'), 3, 2, 2, 1)
    gen, gen_mc = g.generate_negz_crossing_222_scan(2, 1, 1, 2, 2)
    results.append(check('negz-crossing 2364 lx2', real, gen) and real_mc == gen_mc)
    real, real_mc = decode_chunk(find_export('2364'), 3, 2, 2, 2)
    gen, gen_mc = g.generate_posz_crossing_222_scan(2, 1, 1, 1, 2, 2)
    results.append(check('posz-crossing 2364 lx2', real, gen) and real_mc == gen_mc)

    print('=== MULTI-AXIS: x=0 + y=0 EDGE crossing -- all 4 (cx,cy,2) chunks ===')
    # (export, neg_cols, pos_cols, neg_rows, pos_rows): minimal (2366),
    # 2 pos-x cols (2368), 2 pos-y rows (2370), 2 neg-x cols / m_x sat (2372),
    # 2 neg-y rows / m_y sat (2374)
    for exp, nc, pc, nr, pr in [('2366', 1, 1, 1, 1), ('2368', 1, 2, 1, 1),
                                ('2370', 1, 1, 1, 2), ('2372', 2, 1, 1, 1),
                                ('2374', 1, 1, 2, 1), ('2376', 2, 1, 2, 1)]:
        for chunk in [(2, 2, 2), (2, 1, 2), (1, 2, 2), (1, 1, 2)]:
            real, real_mc = decode_chunk(find_export(exp), 3, *chunk)
            gen, gen_mc = g.generate_xyedge_crossing_scan(chunk, nc, pc, nr, pr, 1, 2)
            results.append(check(f'xyedge-crossing {exp} {chunk}', real, gen) and real_mc == gen_mc)

    print('=== MULTI-AXIS: x=0 + z=0 EDGE crossing -- 4 (cx,2,cz) chunks ===')
    # (export, neg_cols, pos_cols, ly_near, neg_z, pos_z): minimal (2378),
    # 2 pos-x cols (2381), 2 pos-z levels (2383), 2 pos-y rows (2385),
    # 2 neg-x cols / m_x sat (2387), 2 neg-z levels / m_z sat (2389),
    # combined m_x + m_z saturation (2391)
    for exp, nc, pc, ly, nz, pz in [('2378', 1, 1, 1, 1, 1), ('2381', 1, 2, 1, 1, 1),
                                    ('2383', 1, 1, 1, 1, 2), ('2385', 1, 1, 2, 1, 1),
                                    ('2387', 2, 1, 1, 1, 1), ('2389', 1, 1, 1, 2, 1),
                                    ('2391', 2, 1, 1, 2, 1)]:
        for chunk in [(2, 2, 2), (1, 2, 2), (2, 2, 1), (1, 2, 1)]:
            real, real_mc = decode_chunk(find_export(exp), 3, *chunk)
            gen, gen_mc = g.generate_xzedge_crossing_scan(chunk, nc, pc, ly, nz, pz)
            results.append(check(f'xzedge-crossing {exp} {chunk}', real, gen) and real_mc == gen_mc)

    print('=== MULTI-AXIS: y=0 + z=0 EDGE crossing -- 4 (2,cy,cz) chunks ===')
    # (export, neg_cols, pos_cols, neg_y, pos_y, neg_z, pos_z): minimal (2393),
    # 2 pos-x cols (2395), 2 pos-y lvls (2397), 2 pos-z lvls (2399),
    # 2 neg-y lvls / m_y sat (2403), 2 neg-z lvls / m_z sat (2409)
    for exp, nc, pc, ny, py, nz, pz in [('2393', 1, 1, 1, 1, 1, 1), ('2395', 1, 2, 1, 1, 1, 1),
                                        ('2397', 1, 1, 1, 2, 1, 1), ('2399', 1, 1, 1, 1, 1, 2),
                                        ('2403', 1, 1, 2, 1, 1, 1), ('2409', 1, 1, 1, 1, 2, 1)]:
        for chunk in [(2, 2, 2), (2, 1, 2), (2, 2, 1), (2, 1, 1)]:
            real, real_mc = decode_chunk(find_export(exp), 3, *chunk)
            gen, gen_mc = g.generate_yzedge_crossing_scan(chunk, nc, pc, ny, py, nz, pz)
            results.append(check(f'yzedge-crossing {exp} {chunk}', real, gen) and real_mc == gen_mc)
    # neg-x saturation: all 8 (cx,cy,cz) chunks (cx=1 source side now carries edge content)
    for exp, nc, pc, ny, py, nz, pz in [('2401', 2, 1, 1, 1, 1, 1), ('2411', 2, 1, 1, 1, 1, 2),
                                        ('2413', 2, 1, 1, 2, 1, 1), ('2415', 3, 1, 1, 1, 1, 1),
                                        ('2417', 2, 2, 1, 1, 1, 1)]:
        for chunk in [(2, 2, 2), (2, 1, 2), (2, 2, 1), (2, 1, 1),
                      (1, 2, 2), (1, 1, 2), (1, 2, 1), (1, 1, 1)]:
            real, real_mc = decode_chunk(find_export(exp), 3, *chunk)
            gen, gen_mc = g.generate_yzedge_crossing_scan(chunk, nc, pc, ny, py, nz, pz)
            results.append(check(f'yzedge-crossing {exp} {chunk}', real, gen) and real_mc == gen_mc)

    print('=== MULTI-AXIS: 3-PLANE CORNER -- all 8 (cx,cy,cz) octants ===')
    # (export, neg_cols, pos_cols, neg_y, pos_y, neg_z, pos_z): min (2419),
    # pos-x cols (2421), pos-y rows (2423), pos-z lvls (2425), neg-x sat (2427;
    # == yz-edge neg-x), neg-y sat (2429), neg-z sat (2431)
    for exp, nc, pc, ny, py, nz, pz in [('2419', 1, 1, 1, 1, 1, 1), ('2421', 1, 2, 1, 1, 1, 1),
                                        ('2423', 1, 1, 1, 2, 1, 1), ('2425', 1, 1, 1, 1, 1, 2),
                                        ('2427', 2, 1, 1, 1, 1, 1), ('2429', 1, 1, 2, 1, 1, 1),
                                        ('2431', 1, 1, 1, 1, 2, 1),
                                        ('2475', 2, 2, 2, 2, 2, 2), ('2477', 3, 3, 3, 3, 3, 3)]:
        for chunk in [(2, 2, 2), (2, 2, 1), (2, 1, 2), (2, 1, 1),
                      (1, 2, 2), (1, 2, 1), (1, 1, 2), (1, 1, 1)]:
            real, real_mc = decode_chunk(find_export(exp), 3, *chunk)
            gen, gen_mc = g.generate_corner_crossing_scan(chunk, nc, pc, ny, py, nz, pz)
            results.append(check(f'corner-crossing {exp} {chunk}', real, gen) and real_mc == gen_mc)

    print()
    n_pass = sum(results)
    print(f'TOTAL: {n_pass}/{len(results)} passed')
    return 0 if n_pass == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
