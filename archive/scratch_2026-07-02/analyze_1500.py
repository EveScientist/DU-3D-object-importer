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

main = "+bYU+1oFAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgD/FW/PAQIAACEFAHgPuQEJH9XVAf8Nn+IBAX5+fgEAIAgA1B/P6ADUBNABDxwDCnACAAAAx2hpLgXwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE="

dec = decode_blob(main)
header, scan, mat, mat_counter = get_scan(dec)
print(f"total len={len(dec)}, scan_len={len(scan)}, mat_len={len(mat)}, mat_counter=0x{mat_counter:x} ({mat_counter})")

mvf = lambda lx,ly,lz: (201*lx+35*ly+lz+217)%256
own_val = mvf(29,1,14)
groupA_val = (own_val+19)%256
groupB_val = (212-14-35*29-0)%256
ystep_val = (304-14-1)%256
print(f"own_val={own_val:#x}, groupA_val={groupA_val:#x}, groupB_val={groupB_val:#x}, ystep_val={ystep_val:#x}")

marker_own = bytes([own_val,0x01,0x02,0x00,0x00])
marker_ystep = bytes([ystep_val,0x01,0x02,0x00,0x00])
hb_groupA = bytes([groupA_val,0x01,0x01,0x7e,0x7e,0x7e,0x01,0x00])
hb_groupB = bytes([groupB_val,0x01,0x01,0x7e,0x7e,0x7e,0x01,0x00])
mat_low = mat[0]
print("mat low byte:", hex(mat_low))
pos1 = scan.find(marker_own)
print("pos1 (marker_own):", pos1)
print("first ystep marker:", scan.find(marker_ystep))
last_ystep = -1
i = 0
while True:
    j = scan.find(marker_ystep, i)
    if j == -1: break
    last_ystep = j
    i = j+1
print("last ystep marker at:", last_ystep, "-> last_marker_end =", last_ystep+5)
gA = scan.find(hb_groupA)
gB = scan.find(hb_groupB)
print("groupA halfblock at:", gA)
print("groupB halfblock at:", gB)
print("mat_byte_pos candidates (170..500):")
for i,b in enumerate(scan):
    if b==mat_low and 170<i<500:
        print("  candidate", i)

print()
print("scan hex around pos1:")
for i in range(max(0,pos1-16), pos1+160, 16):
    print(f"  {i:4d}: " + scan[i:i+16].hex())
print()
print("scan hex around groupA:")
for i in range(gA-16, gA+32, 16):
    print(f"  {i:4d}: " + scan[i:i+16].hex())
