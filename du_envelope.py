"""du_envelope.py -- synthesize the blueprint JSON envelope for ANY core size/type.

Ports the core tables from Skygallant/du-blueprint (src/blueprint.rs) so we no longer
clone a template just to get the Model skeleton. This unlocks arbitrary core sizes (XS..
XXXXXL) and static/dynamic/space types -- the prerequisite for user-chosen core size and
multi-core tiling.

The VoxelData record LIST is still produced by obj_pipeline/du_semantic; this module only
builds the Model + Elements + top-level JSON around it.
"""

# height (octree depth) and voxel size per core size (blueprint.rs CoreSize).
# voxel size = (1 << (height-5)) * 32.
CORE_SIZES = {
    'XS':    (5,  32),
    'S':     (6,  64),
    'M':     (7,  128),
    'L':     (8,  256),
    'XL':    (9,  512),
    'XXL':   (10, 1024),
    'XXXL':  (11, 2048),
    'XXXXL': (12, 4096),
    'XXXXXL':(13, 8192),
}

CORE_KIND = {'dynamic': 4, 'static': 3, 'space': 5}

# element_id[type][size] (blueprint.rs CoreType::element_id)
ELEMENT_ID = {
    'dynamic': {'XS': 183890713, 'S': 183890525, 'M': 1418170469, 'L': 1417952990,
                'XL': 1417997710, 'XXL': 2177071767, 'XXXL': 2162422445,
                'XXXXL': 2148856665, 'XXXXXL': 2162446983},
    'static':  {'XS': 2738359963, 'S': 2738359893, 'M': 909184430, 'L': 910155097,
                'XL': 909203438, 'XXL': 238752214, 'XXXL': 238876751,
                'XXXXL': 237299411, 'XXXXXL': 30685981},
    'space':   {'XS': 3624942103, 'S': 3624940909, 'M': 5904195, 'L': 5904544},
}


def core_voxel_size(size):
    """Voxel edge length of a core size name (e.g. 'M' -> 128)."""
    return CORE_SIZES[size.upper()][1]


def core_height(size):
    return CORE_SIZES[size.upper()][0]


def build_envelope(voxel_records, size='M', core_type='static', name='Construct',
                   bbox=None):
    """Full construct JSON dict. voxel_records = the list already produced for
    out['VoxelData'] (each a dict with h/x/y/z/records...). bbox = ((minx,miny,minz),
    (maxx,maxy,maxz)) in VOXEL units for Model.Bounds; if None, derived from records is
    left to the caller (DU recomputes bounds on import, so a rough box is fine)."""
    import datetime
    size = size.upper()
    vsz = CORE_SIZES[size][1]
    kind = CORE_KIND[core_type]
    element = ELEMENT_ID[core_type][size]
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    center = vsz / 2.0 + 0.125
    if bbox is not None:
        (mnx, mny, mnz), (mxx, mxy, mxz) = bbox
        mins = {'x': mnx / 4.0, 'y': mny / 4.0, 'z': mnz / 4.0}
        maxs = {'x': mxx / 4.0, 'y': mxy / 4.0, 'z': mxz / 4.0}
    else:
        mins = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        maxs = {'x': vsz / 4.0, 'y': vsz / 4.0, 'z': vsz / 4.0}
    return {
        'Model': {
            'Id': 1, 'Name': name, 'Size': vsz, 'CreatedAt': now, 'CreatorId': 2,
            'JsonProperties': {
                'kind': kind, 'size': vsz,
                'serverProperties': {
                    'creatorId': {'playerId': 2, 'organizationId': 0},
                    'originConstructId': 1, 'blueprintId': None, 'isFixture': None,
                    'isBase': None, 'isFlaggedForModeration': None,
                    'isDynamicWreck': False, 'fuelType': None, 'fuelAmount': None,
                    'rdmsTags': {'constructTags': [], 'elementsTags': []},
                    'compacted': False, 'dynamicFixture': None,
                    'constructCloneSource': None,
                },
                'header': None,
                'voxelGeometry': {'size': vsz, 'kind': 1, 'voxelLod0': 3, 'radius': None,
                                  'minRadius': None, 'maxRadius': None},
                'planetProperties': None, 'isNPC': False, 'isUntargetable': False,
            },
            'Static': core_type != 'dynamic',
            'Bounds': {'min': mins, 'max': maxs},
            'FreeDeploy': False, 'MaxUse': None, 'HasMaterials': False, 'DataId': None,
        },
        'VoxelData': voxel_records,
        'Elements': [{
            'elementId': 1, 'localId': 1, 'constructId': 0, 'playerId': 0,
            'elementType': element,
            'position': {'x': center, 'y': center, 'z': center},
            'rotation': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0},
            'properties': [['drmProtected', {'type': 1, 'value': False}]],
            'serverProperties': {}, 'links': [],
        }],
        'Links': [],
    }
