#!/usr/bin/env python3
"""Regenerate test blueprints after each formula fix."""
import json, sys
from datetime import datetime
sys.path.insert(0, '/home/du')
from obj_to_du_blueprint import build_blueprint, MATERIALS

MAT_NQID, MAT_NAME_8 = MATERIALS['Carbon']
_TS = datetime.now().strftime('%m%d_%H%M')  # e.g. 0529_1823

def gen(name, voxels, grid_size):
    fname = f'{name}_{_TS}'
    bp = build_blueprint(
        set(voxels), grid_size, fname,
        'Static',
        MAT_NQID, MAT_NAME_8,
    )
    out = f'/home/du/tests/{fname}.json'
    with open(out, 'w') as f:
        json.dump(bp, f, separators=(',', ':'))
    h_counts = {}
    for e in bp['VoxelData']: h_counts[e.get('h')] = h_counts.get(e.get('h'),0)+1
    print(f'  wrote {out}  VoxelData={h_counts}')
    return out

print("Generating test blueprints...")

# XS single voxel — confirmed-working baseline (Format B, de=0)
gen('xs_single_v5', [(63, 63, 63)], grid_size=32)

# XS two adjacent voxels — 122_export format for de=1 shared chunks
# Shared chunks: 122_export format [FX=(0x20-de), 8-byte FG, scan=684]
# de=0 chunks: Format B (unchanged)
# If migration accepts 122_export de=1: 2 voxels should render
gen('xs_single_minn1', [(63, 63, 63)], grid_size=32)
gen('two_voxels_XS_minn1_v3', [(63, 63, 63), (63, 63, 62)], grid_size=32)

print("Done.")
