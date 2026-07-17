"""Regression suite for du_semantic (the semantic-model emitter rewrite, 2026-07-18).

Self-contained ground truth: each donor's shape is RECONSTRUCTED from its own owned
material cells, re-emitted through du_semantic, and byte-compared against the donor's
raw h3 records. No hand-written geometry specs.

Expectation classes:
  exact    -- byte-exact with default settings (canonical fresh-build payload)
  plain    -- byte-exact with yseam_payload=False (donor exported the plain form;
              payload is DU build state, nondeterministic)
  stale    -- POSITIONS-ONLY diff allowed (incremental-edit build state in the donor's
              payload cells; every material/vertex-key/structure byte must match)
"""
import sys, glob, re
sys.path.insert(0, '/home/du')
from du_squarion import load_records, parse_cell
from du_semantic import build_cell

EXPECT = {}
for n in ('3230 3238 3252 3236 3318 3320 3325 3307 3265 3273 3353 3355 3357 3359 3361 '
          '3363 3372 3374 3178 3367 3187 3376 3378 3404 3406 3380 3382 3493 3500 3502 '
          '3504 3506 3508 3510 3734 3736 3742 3744 3746 3748 3750 3752 3754 3756 3520 '
          '3522 3524 3526 3528 3530 3532 3534 3764 3768 3770 3772 3774 3778 3780 3536 '
          '3538 3540 3542 3544 3546 3550 3552 3554 3556 3559 3561 3563 3565 3567 3569 '
          '3571 3573 3575 3577 3579 3581 3583 3585 3588 3548 3646 3648 3590 3592 3718 '
          '3653 3657 3691 3693 3696 3707 3712 3723 3725 3728 3730 3758 3760 3762 3766 '
          '3776 3784 3786 3430 3432 3434 3442 3444 3446 3452 3459').split():
    EXPECT[n] = 'exact'
for n in ('3438', '3450'):
    EXPECT[n] = 'plain'
for n in ('3400', '3428', '3436', '3447', '3448', '3454', '3455', '3457'):
    EXPECT[n] = 'stale'


def _dicts(P):
    ro = P['range'][0]; rs = P['range'][1]
    def pos_of(i):
        x, r = divmod(i, rs[1] * rs[2]); y, z = divmod(r, rs[2])
        return (ro[0] + x, ro[1] + y, ro[2] + z)
    mats = {}; i = 0
    for mat, cnt in P['mats']:
        if mat is not None:
            for j in range(i, i + cnt): mats[pos_of(j)] = mat
        i += cnt
    verts = {}; i = 0
    for flags, cnt, quads in P['verts']:
        if flags & 1:
            j = i
            for pos, yet in quads:
                for k in range(j, j + yet): verts[pos_of(k)] = pos
                j += yet
        i += cnt
    return mats, verts


def run(name, expect):
    parsed = {key[1:]: (D, parse_cell(D)) for key, D in load_records(name) if key[0] == 3}
    vox = set()
    for ck, (D, P) in parsed.items():
        io = P['inner'][0]
        for c in _dicts(P)[0]:
            v = (c[0] - 1, c[1] - 1, c[2] - 1)
            if all(io[i] <= v[i] < io[i] + 32 for i in range(3)):
                vox.add(v)
    ok = True
    for ck, (D, P) in sorted(parsed.items()):
        mp = [(m[0], m[1], m[2]) for m in P['mapping']]
        mi = next((m[2] for m in mp if 'Debug' not in m[1]), 2)
        io = tuple(32 * c for c in ck)
        G = build_cell(vox, io, mapping=mp, mat_idx=mi,
                       yseam_payload=(expect != 'plain'))
        if G == D:
            print(f'SEM {name} {ck}: BYTE-EXACT')
            continue
        if expect == 'stale':
            md, vd = _dicts(P)
            mg, vg = _dicts(parse_cell(G))
            if md == mg and set(vd) == set(vg):
                nd = sum(1 for k in vd if vd[k] != vg[k])
                print(f'SEM {name} {ck}: STRUCT-EXACT (stale payload, {nd} cells)')
                continue
        print(f'SEM {name} {ck}: FAIL')
        ok = False
    return ok


if __name__ == '__main__':
    names = sys.argv[1:] or sorted(EXPECT, key=int)
    allok = True
    for n in names:
        allok &= run(n, EXPECT.get(n, 'exact'))
    print('=== SEMANTIC REGRESSION:', 'ALL PASS' if allok else 'FAILURES ABOVE', '===')
