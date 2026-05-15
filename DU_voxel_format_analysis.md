# DU Blueprint Voxel Format Analysis
# File: HMS Questionable Decision.json

## Top-level structure
```json
{
  "Model":    { metadata, bounds, JsonProperties },
  "VoxelData": [ 1136 chunk objects ],
  "Elements": [ 216 element objects ],
  "Links":    [ 81 link objects ]
}
```

## Model
- Size: 256 (voxel grid is 256x256x256)
- Bounds min: ~(103, 69, 110), max: ~(152, 188, 159) — occupied region in voxel units
- JsonProperties contains voxelGeometry, serverProperties, header etc.

## Elements (ignore per user instruction)
- 216 elements: seat, engine, weapon hardpoints etc.
- Each has: elementType (uint32 ID), position {x,y,z}, rotation {x,y,z,w quaternion}

## VoxelData chunks
- 1136 total chunks organised as a sparse multi-LOD octree
- Each chunk keyed by (x, y, z, h) coordinates

### LOD levels (h field)
| h | Count | Meaning                        |
|---|-------|-------------------------------|
| 3 | 839   | Finest LOD — leaf geometry    |
| 4 | 211   | LOD level 4                   |
| 5 | 56    | LOD level 5                   |
| 6 | 21    | LOD level 6                   |
| 7 | 8     | LOD level 7                   |
| 8 | 1     | Coarsest — single root chunk  |

- Chunk grid at h=3: x=0..22, y=0..24, z=0..24
- k field: always 0

### Per-chunk structure
Each chunk has three binary records: `voxel`, `meta`, `mesh`

### Binary blob wire format (same for all three records)
```
Bytes 0-3:   Magic = 0xFB14B6F9 (little-endian)
Bytes 4-11:  Uncompressed size (int64 little-endian) — used as LZ4 size hint
Bytes 12+:   LZ4 block-compressed payload
```
Decompress with: `lz4.block.decompress(payload, uncompressed_size=claimed)`

### Decompressed voxel blob layout
```
Bytes 0-7:   8-byte value (same across all h levels — likely a format hash/seed)
Bytes 8-15:  8-byte value (same)
Bytes 16-27: 3x int32 — bounding info specific to this LOD chunk
             (h=8 root has 0xFFFFFFFF here = "full extent")
Bytes 28-63: Further header fields (sizes, flags)
Bytes 64..N: Voxel body — variable length binary stream (NOT a fixed grid)
Last 22 bytes: Footer
  - 4-byte hash
  - b"Debug1\x00\x00\x01\x01"  (NQ internal debug label)
```

### Voxel body sizes (h=3 chunks)
- 571 of 839 chunks = 680 bytes (smallest — likely uniform/empty chunks)
- Remaining 268 chunks: 698 to 74135 bytes (surface geometry chunks)
- Both bytes carry full 0-255 range — NOT a simple (material, density) pair
- Variable-length binary stream — complex proprietary format

### Dominant pattern in voxel body
- Most data is repeating `00 FF` pairs
- Surface chunks have varied byte sequences
- Likely stores smooth-voxel surface data (Dual Contouring / Transvoxel style)

## Shell approach plan (next task)

Goal: Blender OBJ → voxel coordinate list → DU in-game Lua script

Pipeline:
1. Blender exports OBJ (triangulated mesh)
2. Python script (obj_to_du_voxels.py):
   a. Load OBJ vertices + faces
   b. Scale/centre to fit target grid (max 256x256x256)
   c. Surface voxelization: for each triangle, find intersecting voxels
      using triangle-AABB intersection (Möller SAT algorithm)
   d. Output: CSV list of (x,y,z,material) + Lua script
3. Lua script runs in-game to place voxels via construct.setVoxel()

### Why VoxelData binary generation is not feasible
- Full NQ proprietary format spec is undocumented
- Requires correct LZ4 block format with proper headers
- Requires multi-LOD octree construction
- Requires smooth voxel surface encoding

### Shell approach instead
- Bypass VoxelData entirely
- Output voxel coordinates as Lua/CSV
- Use in-game DU scripting API to place voxels

## Key details
- Source file: /var/www/vhosts/allumis.co.uk/eveTools/old files/HMS Questionable Decision.json
- Target repo: https://github.com/EveScientist/DU-3D-object-importer
- Local Windows path: F:\matta\Documents\GitHub\DU
- Input format: OBJ (Blender export, triangulated)
- numpy v1.26.4 available on server
- lz4 available on server (installed this session)
- Work in progress — to be continued in a new window