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

main = "+bYU+1oFAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCOb9EBAgAAIQUAeA8zAY8f09UBhp/kAQF+fn4BACAIANQfz+gA1ATQAQ8cA5BwAgAAAMdoaS4F8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB"

dec = decode_blob(main)
header, scan, mat, mat_counter = get_scan(dec)
print(f"total len={len(dec)}, scan_len={len(scan)}, mat_len={len(mat)}, mat_counter=0x{mat_counter:x} ({mat_counter})")
print("header:", header.hex())
print("scan hex:")
for i in range(0, len(scan), 16):
    print(f"  {i:4d}: " + scan[i:i+16].hex())

# search for expected values
mvf = lambda lx,ly,lz: (201*lx+35*ly+lz+217)%256
own_val = mvf(15,1,14)
groupA_val = (own_val+19)%256
groupB_val = (212-14-35*29-0)%256
ystep_val = (304-14-1)%256
print()
print(f"own_val={own_val:#x}, groupA_val={groupA_val:#x}, groupB_val={groupB_val:#x}, ystep_val={ystep_val:#x}")

# find marker(own_val) and groupA halfblock
import re
marker_own = bytes([own_val,0x01,0x02,0x00,0x00])
marker_ystep = bytes([ystep_val,0x01,0x02,0x00,0x00])
hb_groupA = bytes([groupA_val,0x01,0x01,0x7e,0x7e,0x7e,0x01,0x00])
hb_groupB = bytes([groupB_val,0x01,0x01,0x7e,0x7e,0x7e,0x01,0x00])
mat_low = mat[0]
print("mat low byte:", hex(mat_low))
print("pos1 (marker_own):", scan.find(marker_own))
print("first ystep marker:", scan.find(marker_ystep))
print("groupA halfblock at:", scan.find(hb_groupA))
print("groupB halfblock at:", scan.find(hb_groupB))
print("mat_byte_pos (first mat_low after pos1, isolated):")
for i,b in enumerate(scan):
    if b==mat_low and i>170 and i<500:
        print("  candidate", i)
