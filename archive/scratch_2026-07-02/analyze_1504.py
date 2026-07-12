import base64
import lz4.block

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size)

def get_scan(dec):
    idx = dec.find(b'Debug1')
    mat_start = idx - 13
    header = dec[:64]
    scan = dec[64:mat_start]
    mat = dec[mat_start:]
    mat_counter = int.from_bytes(mat[:4], 'little')
    return header, scan, mat, mat_counter

main = "+bYU+zgIAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBD5EAfg/PAQkPAgDnHz/lAgCf5gEBfn5+AQAgCADUH8/oANQE0AEP8AD/zg/OBOcPAgAJgD8CAAAAx2hpDAjwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE="

dec = decode_blob(main)
header, scan, mat, mat_counter = get_scan(dec)
print(f"total len={len(dec)}, scan_len={len(scan)}, mat_len={len(mat)}, mat_counter=0x{mat_counter:x} ({mat_counter})")

mvf = lambda lx,ly,lz: (201*lx+35*ly+lz+217)%256
own_val = mvf(1,1,14)
groupA_val = (own_val+19)%256
groupB_val = (212-14-35*29-0)%256
ystep_val = (304-14-1)%256
xstep_val = (234-35*29-0)%256
print(f"own_val={own_val:#x}, groupA_val={groupA_val:#x}, groupB_val={groupB_val:#x}, ystep_val={ystep_val:#x}, xstep_val={xstep_val:#x}")

marker_own = bytes([own_val,0x01,0x02,0x00,0x00])
marker_ystep = bytes([ystep_val,0x01,0x02,0x00,0x00])
marker_xstep = bytes([xstep_val,0x01,0x02,0x00,0x00])
hb_groupA = bytes([groupA_val,0x01,0x01,0x7e,0x7e,0x7e,0x01,0x00])
hb_groupB = bytes([groupB_val,0x01,0x01,0x7e,0x7e,0x7e,0x01,0x00])
hb_default = bytes([0x20,0x01,0x01,0x7e,0x7e,0x7e,0x01,0x00])
mat_low = mat[0]
print("mat low byte:", hex(mat_low))
pos1 = scan.find(marker_own)
print("pos1 (marker_own):", pos1)

def find_all(hay, needle):
    res = []
    i = 0
    while True:
        j = hay.find(needle, i)
        if j == -1: break
        res.append(j)
        i = j+1
    return res

ystep_positions = find_all(scan, marker_ystep)
xstep_positions = find_all(scan, marker_xstep)
print("ystep marker positions: count=", len(ystep_positions))
print("xstep marker positions:", xstep_positions)

gA_positions = find_all(scan, hb_groupA)
gB_positions = find_all(scan, hb_groupB)
default_positions = find_all(scan, hb_default)
print("groupA halfblock positions:", gA_positions)
print("groupB halfblock positions:", gB_positions)
print("default halfblock count:", len(default_positions))

# last marker end: find max over ystep and xstep positions + 5
last_marker_end = max(max(ystep_positions), max(xstep_positions)) + 5
print("last_marker_end:", last_marker_end, " marker_span=", last_marker_end - pos1)

print("mat_byte_pos candidates (>last_marker_end, <groups_start):")
gA = gA_positions[0]
for i,b in enumerate(scan):
    if b==mat_low and last_marker_end<i<gA:
        print("  candidate", i)

print()
print("groups_start =", gA)
print("groups_total_bytes = scan_len - groups stuff?")
gB_last = gB_positions[-1]
groups_end = gB_last + 240
print("groups_end (last GroupB + 240) =", groups_end)
print("groups_total_bytes =", groups_end - gA)
print("scan_len - groups_end (gap2) =", len(scan) - groups_end)
print("gap1 (groups_start - last_marker_end) =", gA - last_marker_end)

# Predictions
pred_marker_span = 5*3*29
pred_gap1 = 316-8*2
pred_gap2 = 296-8*2
pred_lme = pos1+pred_marker_span
pred_groups_start = pred_lme+pred_gap1
pred_groups_total = 4*240
pred_scan_len = pos1+pred_marker_span+pred_gap1+pred_groups_total+pred_gap2
pred_mat_byte_pos = pred_lme+pred_gap2
print()
print("PREDICTIONS: marker_span=",pred_marker_span,"last_marker_end=",pred_lme,"groups_start=",pred_groups_start,
      "groups_total=",pred_groups_total,"scan_len=",pred_scan_len,"mat_byte_pos=",pred_mat_byte_pos)
