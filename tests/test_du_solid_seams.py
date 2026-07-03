"""Byte-exact regression tests for du_solid's octant-seam generators.

Every test asserts a generator reproduces a KNOWN-POSITION game export
byte-for-byte (coordinates for every reference build are in
/home/du/EXPORTS_LOG.md). Consolidates the 2026-07-02/03 z=0 / x=0 / y=0
seam derivations so future edits can't silently regress them.

Run:  python3 tests/test_du_solid_seams.py
"""
import base64
import json
import struct
import sys

import lz4.block

sys.path.insert(0, "/home/du")
import du_solid as D
from tests.test_h3_generator import find_export

_cache = {}


def chunks(num):
    """{(cx,cy,cz): scan} for all h3 chunks of an export."""
    if num in _cache:
        return _cache[num]
    d = json.load(open(find_export(num)))
    out = {}
    for e in d["VoxelData"]:
        if e["h"] != 3:
            continue
        c = (int(e["x"]["$numberLong"]), int(e["y"]["$numberLong"]),
             int(e["z"]["$numberLong"]))
        b = e["records"]["voxel"]["data"]["$binary"]
        b = b["base64"] if isinstance(b, dict) else b
        raw = base64.b64decode(b)
        v = lz4.block.decompress(raw[12:],
                                 uncompressed_size=struct.unpack("<I", raw[4:8])[0])
        i = v.find(b"Debug1")
        out[c] = v[64:i - 13]
    _cache[num] = out
    return out


HIGH_Z, LOW_Z = (8, 8, 8), (8, 8, 7)
HIGH_X, LOW_X = (8, 8, 8), (7, 8, 8)
HIGH_Y, LOW_Y = (8, 8, 8), (8, 7, 8)

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


# ── z=0 seam: uniform depth ────────────────────────────────────────────────
for _num, _nx, _ny, _dep in [
        (2986, 2, 2, 2), (2983, 2, 2, 3), (2988, 2, 2, 4),
        (2990, 3, 3, 3), (2996, 5, 2, 3), (3000, 5, 2, 3), (2998, 6, 2, 3)]:
    def _t(num=_num, nx=_nx, ny=_ny, dep=_dep):
        c = chunks(num)
        assert D.gen_seam_z_high(nx, ny, depth=dep) == c[HIGH_Z], "HIGH"
        assert D.gen_seam_z_low(nx, ny, depth=dep) == c[LOW_Z], "LOW"
    CASES.append((f"z0_uniform_{_num}_{_nx}x{_ny}_d{_dep}", _t))


@case("z0_asym_2992_high_deep")
def _(num=2992):
    c = chunks(num)
    assert D.gen_seam_z_high(2, 2, depth=4, opp_depth=2) == c[HIGH_Z], "HIGH"
    assert D.gen_seam_z_low(2, 2, depth=2) == c[LOW_Z], "LOW"


@case("z0_asym_2994_low_deep")
def _(num=2994):
    c = chunks(num)
    assert D.gen_seam_z_high(2, 2, depth=2, opp_depth=4) == c[HIGH_Z], "HIGH"
    assert D.gen_seam_z_low(2, 2, depth=4) == c[LOW_Z], "LOW"


@case("z0_ny1_3034")
def _(num=3034):
    c = chunks(num)
    assert D.gen_seam_z_high(2, 1, depth=4) == c[HIGH_Z], "HIGH"
    assert D.gen_seam_z_low(2, 1, depth=4) == c[LOW_Z], "LOW"


# ── z=0 seam: varying +Z depth (HIGH), LOW uniform ─────────────────────────
for _num, _H, _ld in [
        (3004, [[3, 3], [2, 2]], 3),              # step-down diff 1
        (3006, [[4, 4], [2, 2]], 3),              # step-down diff 2
        (3008, [[2, 2], [3, 3]], 3),              # step-up
        (3010, [[4, 4], [3, 3], [2, 2]], 3),      # nx=3 descending
        (3012, [[2, 2], [4, 4], [2, 2]], 3),      # peak
        (3014, [[3, 2], [2, 2]], 3),              # y-varying, tall row 0
        (3016, [[2, 3], [2, 2]], 3),              # y-varying, tall row 1
        (3018, [[4, 3, 2], [2, 2, 2]], 3),        # ny=3 y-graded
        (3020, [[5, 4, 3, 2], [2, 2, 2, 2]], 3)]: # ny=4 (shifted-rDec engine)
    def _t(num=_num, H=_H, ld=_ld):
        c = chunks(num)
        assert D.gen_seam_z_high_varying(H) == c[HIGH_Z], "HIGH"
        assert D.gen_seam_z_low(len(H), len(H[0]), depth=ld) == c[LOW_Z], "LOW"
    CASES.append((f"z0_varying_high_{_num}", _t))


@case("z0_varying_reduces_to_uniform")
def _():
    for (nx, ny), dep in [((2, 2), 3), ((3, 3), 3)]:
        assert D.gen_seam_z_high_varying([[dep] * ny] * nx) == \
            D.gen_seam_z_high(nx, ny, depth=dep), f"{nx}x{ny} d{dep}"


# ── z=0 seam: varying -Z depth (LOW) + representation choice ───────────────
@case("z0_3022_extra1_folds_into_high")
def _(num=3022):
    c = chunks(num)
    assert D.gen_seam_z_high_varying([[4, 4], [3, 3]]) == c[HIGH_Z], "HIGH"
    assert D.gen_seam_z_low(2, 2, depth=3) == c[LOW_Z], "LOW"


@case("z0_3024_low_varying_descending")
def _(num=3024):
    c = chunks(num)
    assert D.gen_seam_z_high(2, 2, depth=3) == c[HIGH_Z], "HIGH"
    assert D.gen_seam_z_low_varying([[5, 5], [3, 3]]) == c[LOW_Z], "LOW"


@case("z0_3026_low_varying_ascending_nx3")
def _(num=3026):
    c = chunks(num)
    assert D.gen_seam_z_high(3, 2, depth=3) == c[HIGH_Z], "HIGH"
    assert D.gen_seam_z_low_varying([[3, 3], [4, 4], [5, 5]]) == c[LOW_Z], "LOW"


@case("z0_3028_both_sides_varying_independent")
def _(num=3028):
    c = chunks(num)
    assert D.gen_seam_z_high_varying([[3, 3], [2, 2]]) == c[HIGH_Z], "HIGH"
    assert D.gen_seam_z_low_varying([[5, 5], [3, 3]]) == c[LOW_Z], "LOW"


@case("z0_low_varying_reduces_to_uniform")
def _():
    for (nx, ny), dep in [((2, 2), 2), ((2, 2), 3), ((2, 2), 4),
                          ((3, 3), 3), ((5, 2), 3), ((6, 2), 3),
                          ((2, 3), 3), ((2, 4), 3)]:
        assert D.gen_seam_z_low_varying([[dep] * ny] * nx) == \
            D.gen_seam_z_low(nx, ny, depth=dep), f"{nx}x{ny} d{dep}"


# ── x=0 seam ────────────────────────────────────────────────────────────────
for _num, _nr, _h in [(3032, 2, 1), (3036, 3, 1), (3040, 2, 2)]:
    def _t(num=_num, nr=_nr, h=_h):
        c = chunks(num)
        assert D.gen_seam_x0_high(nr, h=h) == c[HIGH_X], "HIGH"
        assert D.gen_seam_x0_low(nr, h=h) == c[LOW_X], "LOW"
    CASES.append((f"x0_{_num}_n{_nr}_h{_h}", _t))


# ── y=0 seam ────────────────────────────────────────────────────────────────
@case("y0_3038")
def _(num=3038):
    c = chunks(num)
    assert D.gen_seam_y0_high(2) == c[HIGH_Y], "HIGH"
    assert D.gen_seam_y0_low(2) == c[LOW_Y], "LOW"


def main():
    passed = failed = 0
    for name, fn in CASES:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {name}: {e!r}")
    print(f"{passed} passed, {failed} failed ({len(CASES)} cases)")
    return failed


if __name__ == "__main__":
    sys.exit(main())
