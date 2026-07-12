#!/usr/bin/env python3
"""
decode_blueprints.py — Decode voxel_hex and meta_hex from *_decoded.json files.

Produces *_annotated.json with human-readable breakdown of each chunk's binary data.
"""
import struct, json, sys
from pathlib import Path

EXPORT_DIR = Path('/home/du/export')

GRAY = [0x01, 0x21, 0x20, 0x00]

def decode_header(raw64):
    """Parse 64-byte chunk header into named fields."""
    vals = struct.unpack_from('<16I', raw64)
    return {
        "magic":        f"0x{vals[0]:08x}",
        "field1":       vals[1],
        "field2":       f"0x{vals[2]:08x}",
        "h_level":      vals[3],
        "origin_x":     vals[4] if vals[4] < 0x80000000 else vals[4] - 0x100000000,
        "origin_y":     vals[5] if vals[5] < 0x80000000 else vals[5] - 0x100000000,
        "origin_z":     vals[6] if vals[6] < 0x80000000 else vals[6] - 0x100000000,
        "dim_a":        vals[7],
        "dim_b":        vals[8],
        "dim_c":        vals[9],
        "chunk_x":      vals[10],
        "chunk_y":      vals[11],
        "chunk_z":      vals[12],
        "size_x":       vals[13],
        "size_y":       vals[14],
        "size_z":       vals[15],
    }


def decode_scan(scan_bytes):
    """
    Annotate scan body as a list of (pair_index, byte0, byte1, annotation) entries.
    Only returns non-background pairs plus context.
    """
    n = len(scan_bytes) // 2
    pairs = [(scan_bytes[i*2], scan_bytes[i*2+1]) for i in range(n)]

    # Determine background direction from scan (ff00 = N odd, 00ff = N even)
    bg = (0xff, 0x00)  # default
    # Check first non-leading pair
    for i in range(n):
        b0, b1 = pairs[i]
        if b0 == 0x00 and b1 == 0xff:
            continue  # leading 00ff
        if b0 == 0xff and b1 == 0x00:
            bg = (0xff, 0x00)
            break
        if b0 == 0x00 and b1 == 0x00:
            bg = (0x00, 0xff)  # N even
            break
        break

    annotated = []
    i = 0
    while i < n:
        b0, b1 = pairs[i]

        # Skip pure background (00ff leading or ff00/00ff trailing)
        is_bg_ff00 = (b0 == 0xff and b1 == 0x00)
        is_bg_00ff = (b0 == 0x00 and b1 == 0xff)

        if is_bg_ff00 or is_bg_00ff:
            i += 1
            continue

        # Non-background pair — annotate it
        # First-group declaration in 00ff region: [0x00, CV, 0x01, 0x02, de, 0x00]
        if (b0 == 0x00 and b1 not in (0x00, 0xff) and
                i+2 < n and pairs[i+1] == (0x01, 0x02)):
            CV = b1
            de = pairs[i+2][0]
            annotated.append({
                "pairs": f"{i}..{i+2}",
                "hex": "".join(f"{b:02x}" for b in scan_bytes[i*2:i*2+6]),
                "type": "DECLARATION",
                "CV": f"0x{CV:02x}",
                "de": de,
            })
            i += 3
            continue

        # Non-first declaration in ff00 region: [CV, 0x01, 0x02, 0x00]
        if (b0 not in (0x00, 0xff) and b1 == 0x01 and
                i+1 < n and pairs[i+1] == (0x02, 0x00)):
            CV = b0
            annotated.append({
                "pairs": f"{i}..{i+1}",
                "hex": "".join(f"{b:02x}" for b in scan_bytes[i*2:i*2+4]),
                "type": "DECLARATION_2ND+",
                "CV": f"0x{CV:02x}",
                "de": 0,
            })
            i += 2
            continue

        # FG block (8-byte group starting with 0x01): detect by b0==0x01 at even byte
        if b0 == 0x01 and i+3 < n:
            block = scan_bytes[i*2:i*2+16]
            annotated.append({
                "pairs": f"{i}..{i+7}",
                "hex": block.hex(),
                "type": "FG_GROUP",
                "inner0": f"0x{block[1]:02x}",
                "byte7": f"0x{block[7]:02x}",
                "inner1": f"0x{block[9]:02x}",
                "byte15": f"0x{block[15]:02x}",
            })
            i += 8
            continue

        # MARKER (single pair, not background and not decl/FG)
        annotated.append({
            "pairs": str(i),
            "hex": f"{b0:02x}{b1:02x}",
            "type": "MARKER_or_UNKNOWN",
            "b0": f"0x{b0:02x}",
            "b1": f"0x{b1:02x}",
        })
        i += 1

    return annotated


def decode_mat(mat40):
    """Parse 40-byte mat block."""
    if len(mat40) < 40:
        return {"raw": mat40.hex(), "note": "too short"}

    a_byte = mat40[0]
    # Material name at bytes 30..37 (8 chars)
    name_bytes = mat40[30:38]
    try:
        mat_name = name_bytes.rstrip(b'\x00').decode('ascii')
    except Exception:
        mat_name = name_bytes.hex()

    return {
        "byte0": f"0x{a_byte:02x}",
        "bytes_1_12": mat40[1:13].hex(),
        "debug_tag": mat40[13:19].decode('ascii', errors='replace').rstrip('\x00'),
        "bytes_19_29": mat40[19:30].hex(),
        "material_name": mat_name,
        "bytes_38_39": mat40[38:40].hex(),
        "raw": mat40.hex(),
    }


def decode_meta(raw):
    """Parse meta block into known fields."""
    result = {}

    if len(raw) < 8:
        return {"raw": raw.hex()}

    magic = raw[:4]
    result["magic"] = f"0x{struct.unpack_from('>I', magic)[0]:08x}"
    result["field_4"] = struct.unpack_from('<I', raw, 4)[0]

    if len(raw) >= 10:
        result["type_flags"] = f"0x{raw[8]:02x}{raw[9]:02x}"

    if len(raw) >= 18:
        result["blueprint_id"] = raw[10:18].hex()

    if len(raw) >= 28:
        result["bytes_18_27"] = raw[18:28].hex()

    if len(raw) >= 36:
        result["field_28"] = struct.unpack_from('<I', raw, 28)[0]
        result["field_32_35"] = raw[32:36].hex()

    # Find material name (e.g. "hcAlumin", "hcSodium", "hcCarbon")
    mat_pos = -1
    for name in [b'hcAlumin', b'hcSodium', b'hcCarbon', b'hcCopper', b'hcIron']:
        pos = raw.find(name)
        if pos >= 0:
            mat_pos = pos
            result["material_name_offset"] = pos
            result["material_name"] = name.decode() + raw[pos+8:pos+12].rstrip(b'\x00').decode('ascii', errors='replace')
            break

    if mat_pos >= 0:
        after = mat_pos + 10  # skip 8-char name + 2 null bytes
        if after + 2 <= len(raw):
            count16 = struct.unpack_from('<H', raw, after)[0]
            result["material_count_field"] = count16
            result["material_count_note"] = f"{count16} = 4 * {count16//4} voxels (estimated)"
        # Structure after name\0\0: [uint16 count][4 pad][flag byte][float64 x7]
        if after + 7 <= len(raw):
            flag = raw[after + 6]
            result["material_flag"] = f"0x{flag:02x}"
        # float64 values start at after+7
        float_offset = after + 7
        floats = []
        for j in range(7):
            if float_offset + j*8 + 8 <= len(raw):
                v = struct.unpack_from('<d', raw, float_offset + j*8)[0]
                floats.append(round(v, 6))
        result["material_quantities_f64"] = floats

    result["total_length"] = len(raw)
    result["raw_hex"] = raw.hex()
    return result


def decode_voxel(raw):
    """Parse full decompressed voxel payload."""
    if len(raw) < 104:
        return {"raw": raw.hex(), "note": "too short"}

    header = decode_header(raw[:64])
    mat = decode_mat(raw[-40:])
    scan_bytes = raw[64:-40]

    result = {
        "header": header,
        "scan_length_pairs": len(scan_bytes) // 2,
        "scan_annotated": decode_scan(scan_bytes),
        "scan_hex": scan_bytes.hex(),
        "mat": mat,
    }
    return result


def process_file(blueprint_name):
    decoded_path = EXPORT_DIR / f'{blueprint_name}_decoded.json'
    out_path = EXPORT_DIR / f'{blueprint_name}_annotated.json'

    with open(decoded_path) as f:
        data = json.load(f)

    result = {}
    for chunk_key, chunk_data in data.items():
        voxel_raw = bytes.fromhex(chunk_data['voxel_hex'])
        meta_raw = bytes.fromhex(chunk_data['meta_hex'])

        result[chunk_key] = {
            "voxel_decoded": decode_voxel(voxel_raw),
            "meta_decoded": decode_meta(meta_raw),
        }

    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Written: {out_path} ({out_path.stat().st_size // 1024}KB)")
    return result


if __name__ == '__main__':
    blueprints = ['F_2vox_diff_n1', 'G_4vox_diff_n1', 'H_2vox_same_n1', 'I_4vox_same_n1']
    for bp in blueprints:
        process_file(bp)
