#!/usr/bin/env python3
"""
generate_single_voxel.py — Generate a blueprint with a single boundary voxel.

CONFIRMED WORKING (2026-05-22): rendered single voxel in DU.

The approach: use D_export's scan bodies (correct format for all 8 boundary chunk types)
with headers remapped to construct-local positions.

For a voxel at world position (wx, wy, wz) in a Size=32 (128-voxel) construct deployed
at world origin (0,0,0):
  - Chunk coordinates: cx = wx//32, cy = wy//32, cz = wz//32
  - 8 chunks span (cx-1 or cx, cy-1 or cy, cz-1 or cz) boundaries

The scan format uses (from D_export analysis):
  n1 = 9 + (153*lx + 4*ly + lz)//31
  CV = (32*((4-Wx-3*Wy-Wz)%8) + BASE) % 256  [Wx=1 if lx==0]
  FG1 = n1+166 for most chunks, n1+165 for all-lower (Wx=Wy=Wz=1) corner
  FX1 = (F[cx]+G[cy]-32*cz)%256  [construct-local cx,cy,cz]
"""

import base64, json, lz4.block, struct, random, hashlib
from pathlib import Path

BLOB_MAGIC = bytes([0xF9,0xB6,0x14,0xFB])
_FX_F = [44, 12, 67, 67]
_FX_G = [96, 0, 221, 221]
_GRAY = [0x01, 0x21, 0x20, 0x00]

BASE_SODIUM = 249
BASE_CARBON = 179

MAT_SODIUM = bytes.fromhex(
    '0002000000c768690900000000446562756731000001'
    '69670374000000006863536f6469756d0201'
)

def _blob(p):
    c = lz4.block.compress(p, store_size=False)
    return BLOB_MAGIC + struct.pack('<I', len(p)) + b'\x00\x00\x00\x00' + c

def _hdr(cx, cy, cz):
    h = bytearray(64)
    vals = [666411027,6,3900781470,9,(cx*32-1)&0xFFFFFFFF,(cy*32-1)&0xFFFFFFFF,
            (cz*32-1)&0xFFFFFFFF,35,35,35,cx*32,cy*32,cz*32,32,32,32]
    for i,v in enumerate(vals): struct.pack_into('<I',h,i*4,v)
    return bytes(h)

def make_boundary_voxel_body(cx, cy, cz, lx, ly, lz, base=BASE_SODIUM):
    """
    Generate h=3 voxel body for ONE CORNER of a boundary-crossing voxel.
    Confirmed working via D_export analysis and single voxel render test.
    """
    A = _GRAY[cz % 4]
    Wx = 1 if lx==0 else 0
    Wy = 1 if ly==0 else 0
    Wz = 1 if lz==0 else 0
    n = (4-Wx-3*Wy-Wz) % 8
    CV = (32*n + base) % 256

    # n1 = scan position for the corner declaration
    n1 = 9 + (153*lx + 4*ly + lz)//31

    # FG1 = n1+165 when ALL-LOWER (n=7, Wx=Wy=Wz=1), else n1+166
    fg_base_offset = 165 if n == 7 else 166
    FG1 = n1 + fg_base_offset
    FG2 = FG1 + 12
    # XX00 marker at pair 169 (always, regardless of n1)
    xx00_val = 0x9f ^ A  # derived from D_export analysis

    FX1 = (_FX_F[min(cx,3)] + _FX_G[min(cy,3)] - 32*cz) % 256
    FX2 = 0x21 ^ A
    FX3 = (FX1 + 23) % 256
    decl_end = A & 0x20

    # Scan size: FG2_end + 1 + trailing
    # trailing ≈ max(0, 167 - n1 - (cz//2)%2)
    fg_cz_offset = (cz//2) % 2
    trailing = max(0, 167 - n1 - fg_cz_offset)
    SCAN_PAIRS = FG2 + 8 + trailing

    mat = bytes([A & 0xFE]) + MAT_SODIUM[1:]  # mat[0] = A & 0xFE

    scan = bytearray(SCAN_PAIRS * 2)
    # (00,ff) before n1
    for i in range(n1): scan[i*2]=0x00; scan[i*2+1]=0xff
    # Corner declaration at n1
    scan[n1*2]=0x00; scan[n1*2+1]=CV
    scan[n1*2+2]=0x01; scan[n1*2+3]=0x02
    scan[n1*2+4]=decl_end; scan[n1*2+5]=0x00
    # XX00 marker at pair 169 (if after decl and before FG)
    if n1+3 <= 169 < FG1:
        scan[169*2]=xx00_val; scan[169*2+1]=0x00
    # (ff,00) everywhere else
    for i in range(n1+3, SCAN_PAIRS):
        if not (i==169 and n1+3 <= 169 < FG1):
            scan[i*2]=0xff; scan[i*2+1]=0x00
    # FG1: 2 groups
    scan[FG1*2:FG1*2+16] = bytes([FX1,0x01,A,0x7e,0x7e,0x7e,A,0x00,
                                   FX2,0x01,A,0x7e,0x7e,0x7e,A,0x00])
    for i in range(FG1+8, FG2): scan[i*2]=0xff; scan[i*2+1]=0x00
    # FG2: group1 + z_side=0 terminator
    scan[FG2*2:FG2*2+16] = bytes([FX3,0x01,A,0x7e,0x7e,0x7e,A,0x00,
                                   FX2,0x01,0x00,0x7e,0x7e,0x7e,0x00,0x00])

    return _blob(bytes(_hdr(cx,cy,cz)) + bytes(scan) + mat)


def make_lod_body(cx, cy, cz):
    h = bytearray(64)
    vals = [666411027,6,3900781470,9,(cx*32-1)&0xFFFFFFFF,(cy*32-1)&0xFFFFFFFF,
            (cz*32-1)&0xFFFFFFFF,35,35,35,cx*32,cy*32,cz*32,32,32,32]
    for i,v in enumerate(vals): struct.pack_into('<I',h,i*4,v)
    s = bytearray(672)
    for i in range(0,672,2): s[i]=0x00; s[i+1]=0xff
    s[334]=0x00; s[335]=0x7a; s[670]=0x00; s[671]=0x7a
    return _blob(bytes(h)+bytes(s)+bytes.fromhex('01000000c76869090000000044656275673100000101'))


def make_single_voxel_blueprint(name="single_voxel", core_nqid=2738359963):
    """
    Generate a blueprint with a single voxel at world (31-32, 31-32, 31-32).
    The voxel spans all 8 construct chunks (0-1, 0-1, 0-1).
    """
    now = "2025-01-01T00:00:00.000000+00:00"
    model_id = random.randint(10_000_000, 99_999_999)
    mesh = _blob(bytes.fromhex('1c974a7503000000000000000000000000000000'))

    # Load reference meta from 122_export
    ref_meta_path = Path(__file__).parent / 'export' / '122_export.blueprint'
    with open(ref_meta_path) as f:
        bp_ref = json.load(f)
    ref_meta = {(c['x']['$numberLong'],c['y']['$numberLong'],c['z']['$numberLong']):
                base64.b64decode(c['records']['meta']['data']['$binary'])
                for c in bp_ref['VoxelData'] if c['h']==3}

    def entry(h, cx, cy, cz, vb, mb):
        return {
            "created_at":{"$date":now},"h":h,"k":0,
            "metadata":{"mversion":0,"pversion":4,"uptodate":True,"version":8},
            "oid":{"$numberLong":model_id},
            "records":{
                "mesh":{"data":{"$binary":base64.b64encode(mesh).decode(),"$type":"0x0"},"hash":{"$numberLong":0},"updated_at":{"$date":now}},
                "meta":{"data":{"$binary":base64.b64encode(mb).decode(),"$type":"0x0"},"hash":{"$numberLong":0},"updated_at":{"$date":now}},
                "voxel":{"data":{"$binary":base64.b64encode(vb).decode(),"$type":"0x0"},"hash":{"$numberLong":0},"updated_at":{"$date":now}},
            },
            "updated_at":{"$date":now},"version":{"$numberLong":3},
            "x":{"$numberLong":cx},"y":{"$numberLong":cy},"z":{"$numberLong":cz}
        }

    # 8 boundary voxel corners: (cx,cy,cz, lx,ly,lz)
    corners = [
        (0,0,0, 31,31,31), (1,0,0, 0,31,31), (0,1,0, 31,0,31), (1,1,0, 0,0,31),
        (0,0,1, 31,31,0),  (1,0,1, 0,31,0),  (0,1,1, 31,0,0),  (1,1,1, 0,0,0),
    ]

    vd = []
    for cx,cy,cz,lx,ly,lz in corners:
        vb = make_boundary_voxel_body(cx,cy,cz,lx,ly,lz)
        vd.append(entry(3,cx,cy,cz,vb,ref_meta[(cx,cy,cz)]))
    for cx4 in range(2):
        for cy4 in range(2):
            for cz4 in range(2):
                vd.append(entry(4,cx4,cy4,cz4,make_lod_body(cx4,cy4,cz4),ref_meta[(cx4*2,cy4*2,cz4*2)]))
    vd.append(entry(5,0,0,0,make_lod_body(0,0,0),ref_meta[(0,0,0)]))

    return {
        "Model":{"Id":model_id,"Name":name,"Size":32,"CreatedAt":now,"CreatorId":0,
                 "JsonProperties":{"kind":4,"size":32,"serverProperties":{"creatorId":{"playerId":0,"organizationId":0},"originConstructId":0,"blueprintId":0,"isFixture":None,"isBase":None,"isFlaggedForModeration":None,"isDynamicWreck":False,"fuelType":None,"fuelAmount":None,"rdmsTags":{"constructTags":[],"elementsTags":[]},"compacted":False,"dynamicFixture":None,"constructCloneSource":None},"header":{"uniqueIdentifier":None,"parentUniqueIdentifier":None,"constructIdHint":None,"prettyName":"UnknownOrigin","fixtureHash":None,"folder":None,"artWorkSVNRevision":None,"biomeEditorVersion":None,"biomeEditorGitRevision":None},"voxelGeometry":{"size":32,"kind":1,"voxelLod0":3,"radius":None,"minRadius":None,"maxRadius":None},"planetProperties":None,"isNPC":False,"isUntargetable":False},
                 "Static":False,"Bounds":{"min":{"x":0.,"y":0.,"z":0.},"max":{"x":32.,"y":32.,"z":32.}},"FreeDeploy":False,"MaxUse":None,"HasMaterials":True,"DataId":None},
        "VoxelData":vd,
        "Elements":[{"elementId":random.randint(4_000_000_000,4_294_967_295),"localId":1,"constructId":0,"playerId":0,"elementType":core_nqid,"position":{"x":16.,"y":16.,"z":16.},"rotation":{"x":0.,"y":0.,"z":0.,"w":1.},"properties":[["drmProtected",{"type":1,"value":True}]],"serverProperties":{},"links":[]}],
        "Links":[]
    }


if __name__ == '__main__':
    import os
    bp = make_single_voxel_blueprint("test_single_voxel_gen")
    out = '/home/du/test_single_voxel_gen.json'
    with open(out,'w') as f: json.dump(bp, f, separators=(',',':'))
    print(f"Written: {out} ({os.path.getsize(out)//1024}KB)")
