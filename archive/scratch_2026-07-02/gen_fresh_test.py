#!/usr/bin/env python3
"""
Generate a fresh single-voxel blueprint with h3+h4+h5 using our generators.
Voxel at game position (0,0,0) → hcSodium, XS static core.

Uses generate_hollow_cube.build() with a single voxel.
"""
import json, struct
from pathlib import Path
import lz4.block
from generate_hollow_cube import build, STATIC_CORE_XS_NQID

# Single voxel at position (0,0,0) in a 32-grid construct
voxels = {(0, 0, 0)}
bp = build(voxels, 32, STATIC_CORE_XS_NQID, "FreshTest_h5", 'hcSodium', json_size=8)

out = Path('/home/du/tests/test_fresh_h5.blueprint')
out.parent.mkdir(exist_ok=True)
with open(out, 'w') as f:
    json.dump(bp, f)

print(f"VoxelData entries: {len(bp['VoxelData'])}")
for c in bp['VoxelData']:
    h = c['h']
    cx,cy,cz = c['x']['$numberLong'],c['y']['$numberLong'],c['z']['$numberLong']
    blob = bytes.fromhex(
        __import__('base64').b64decode(c['records']['voxel']['data']['$binary']).hex()
    )
    unc = struct.unpack('<I', blob[4:8])[0]
    raw = lz4.block.decompress(blob[12:], uncompressed_size=unc)
    print(f"  h={h} ({cx},{cy},{cz}): {len(raw)}B raw, scan={len(raw[64:-40])}B")

print(f"\nSaved: {out} ({out.stat().st_size//1024}KB)")
print("Import this in-game and verify it renders.")
