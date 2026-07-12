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

chunks = {
 "(1,1,2) corner": "+bYU+/YCAAAAAAAA8wIToLgnBgAAAJ4zgegJAAAAHwQAVz8AAAAjBAATIAQAE0AIAAQQAC8A/wIA/zsfek4B/zug/wB6AQAAAMdoadsCsABEZWJ1ZzEAAAEB",
 "(1,2,2) x-bound": "+bYU+/YCAAAAAAAA8wYToLgnBgAAAJ4zgegJAAAAHwAAAD8EABcjBABTIAAAAEAEAAAMAAQEAC8A/wIA/zsfek4B/zug/wB6AQAAAMdoadsCsABEZWJ1ZzEAAAEB",
 "(2,1,2) y-bound": "+bYU+/YCAAAAAAAA8wYToLgnBgAAAJ4zgegJAAAAPwAAAB8IABcjBABXQAAAACAIAAAMAAAEAC8A/wIA/zsfek4B/zug/wB6AQAAAMdoadsCsABEZWJ1ZzEAAAEB",
 "(2,2,2) main": "+bYU+1oFAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeA+tAAkPAgD5H9HVAQCf5gEBfn5+AQAgCADUH8/oANQE0AEPAAP5DwIACYDRAgAAAMdoaS4F8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB",
}

for name, b64 in chunks.items():
    dec = decode_blob(b64)
    header, scan, mat, mat_counter = get_scan(dec)
    print(f"=== {name} ===")
    print(f"total len={len(dec)}, scan_len={len(scan)}, mat_len={len(mat)}, mat_counter=0x{mat_counter:x} ({mat_counter})")
    print("header:", dec[:64].hex())
    print("scan hex:")
    for i in range(0, len(scan), 16):
        print(f"  {i:4d}: " + scan[i:i+16].hex())
    print()
