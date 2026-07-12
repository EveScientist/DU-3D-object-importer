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

main = "+bYU+8sGAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBDz4BCQ8CAPEfCF4CAJ/mAQF+fn4BACAIANQfz+gA1ATQAQ/wAN0P6APxDwIACYAIAgAAAMdoaZ8G8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB"

dec = decode_blob(main)
header, scan, mat, mat_counter = get_scan(dec)
print(f"total len={len(dec)}, scan_len={len(scan)}, mat_len={len(mat)}, mat_counter=0x{mat_counter:x} ({mat_counter})")
print("header:", header.hex())

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

# find all marker_ystep and marker_xstep occurrences
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
print("ystep marker positions: count=", len(ystep_positions), "first=",ystep_positions[:3], "last=",ystep_positions[-3:] if ystep_positions else None)
print("xstep marker positions: count=", len(xstep_positions), "first=",xstep_positions[:3], "last=",xstep_positions[-3:] if xstep_positions else None)

gA_positions = find_all(scan, hb_groupA)
gB_positions = find_all(scan, hb_groupB)
default_positions = find_all(scan, hb_default)
print("groupA halfblock positions:", gA_positions)
print("groupB halfblock positions:", gB_positions)
print("default halfblock count:", len(default_positions), "first few:", default_positions[:5], "last few:", default_positions[-5:])

print("mat_byte_pos candidates (170..600):")
for i,b in enumerate(scan):
    if b==mat_low and 170<i<600:
        print("  candidate", i)

print()
print("full scan hex dump:")
for i in range(0, len(scan), 16):
    print(f"  {i:4d}: " + scan[i:i+16].hex())
