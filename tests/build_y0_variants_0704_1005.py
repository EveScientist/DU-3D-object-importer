"""Diagnostic variants for the y=0 one-sided-step import test (mirror of 3066:
heights boundary-first LOW [2,1] / HIGH [1,1]) after v1 failed to deploy with
"Deserializing invalid vertex" on both cells.

Post-mortem of v1: the LOW chunk deviated from the plain oracle plate by ONE
byte (ghost val 32 from the over-eager "chain reset"); the pairwise-prev value
rule (now in _y0_rebuild_fg, suite 46/46) makes LOW = the plain plate exactly.
The HIGH chunk still has two knobs no real ref discriminates:
  - far-row value: pairwise-prev -> 32 vs with-ghost-fwd-chain -> 31
  - TRI openers when the chunk's OWN side is flat (only ever seen with both
    sides stepping, 3062)

All variants share the SAME LOW chunk (plain plate) and mc (HIGH 719, LOW 658);
envelope 3066. Deploy in order until one works:
  v2  tests/y0_varying_tri_import_v2_0704_1005.blueprint  pairwise vals + TRI
  v3  tests/y0_varying_tri_import_v3_0704_1005.blueprint  fwd-chain vals + TRI
  v4  tests/y0_varying_tri_import_v4_0704_1005.blueprint  pairwise vals, NO TRI
EXPECTED IN-GAME (all variants, 10 vox, hcCarbon):
  Z=10.5: X in {10.5,11.5} x Y in {-1.5,-0.5,+0.5,+1.5}
  Z=11.5: X in {10.5,11.5} x Y = -0.5   (+ bevel on the +Y side if TRI is real)
Outcome decodes: v2 ok -> pairwise+TRI right. v2 fail, v3 ok -> fwd-chain vals.
v2/v3 fail, v4 ok -> no TRI on flat-own side (and v4's vals arbitrate values).
"""
import sys
sys.path.insert(0, "/home/du")
import du_solid as D
import du_assemble as A

TEMPLATE = '/home/du/exports/3066_export.blueprint'
MC_HIGH, MC_LOW = 719, 658

low = D.gen_seam_y0_low_varying([2, 1], [1, 1])       # = plain plate now

high_v2 = D.gen_seam_y0_high_varying([1, 1], [2, 1])  # pairwise vals + TRI

# v3: with-ghost fwd-chain values -> far rows (32,1) become (31,1)
high_v3 = high_v2.replace(bytes([32, 1, 1, 0x7e, 0x7e, 0x7e, 1, 0]),
                          bytes([31, 1, 1, 0x7e, 0x7e, 0x7e, 1, 0]))
assert high_v3 != high_v2

# v4: pairwise vals, TRI suppressed (rebuild with tri=False)
from du_solid import gen_heightmap_unified, _fg0, _y0_rebuild_fg
prof = [2, 1, 1]
gB = gen_heightmap_unified([[1] + prof] * 2, lx0=10, ly0=-2, lz0=10)
gA = gen_heightmap_unified([prof] * 2, lx0=10, ly0=-1, lz0=10)
fA = _fg0(gA)
gA = _y0_rebuild_fg(gA, prof, 2, 'high', tri=False, hB=1)
high_v4 = (gB[:_fg0(gB)] + gA[fA:])[:-2]
assert high_v4 != high_v2


def build(out, high):
    scans = {(8, 8, 8): (high, MC_HIGH), (8, 7, 8): (low, MC_LOW)}
    n = A.rebuild_h3(TEMPLATE, out, lambda cx, cy, cz: scans.get((cx, cy, cz)))
    assert n == 2, n
    print("wrote", out)


if __name__ == '__main__':
    build('/home/du/tests/y0_varying_tri_import_v2_0704_1005.blueprint', high_v2)
    build('/home/du/tests/y0_varying_tri_import_v3_0704_1005.blueprint', high_v3)
    build('/home/du/tests/y0_varying_tri_import_v4_0704_1005.blueprint', high_v4)
