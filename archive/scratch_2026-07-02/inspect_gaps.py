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

cases = {
    "1496 (Ncols=1)": dict(
        b64="+bYU+1oFAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeA+tAAkPAgD5H9HVAQCf5gEBfn5+AQAgCADUH8/oANQE0AEPAAP5DwIACYDRAgAAAMdoaS4F8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB",
        pos1=29, Ncols=1, Yextent=29, lme=174, groups_start=490, groups_total=480, scan_len=1266, gap1=316, gap2=296,
    ),
    "1508 (Ncols=5)": dict(
        b64="+bYU+xILAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBD5EA/6EP8QIJDwIA0x+t8wMAn+YBAX5+fgEAIAgA1B/P6ADUBNABD/AA////sA+aBtMPAgAJgK0CAAAAx2hp5grwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=",
        pos1=29, Ncols=5, Yextent=29, lme=754, groups_start=1032, groups_total=1440, scan_len=2730, gap1=278, gap2=258,
    ),
}

for name, c in cases.items():
    dec = decode_blob(c["b64"])
    header, scan, mat, mat_counter = get_scan(dec)
    print(f"=== {name} ===  scan_len={len(scan)} (expected {c['scan_len']})")

    pos1 = c["pos1"]
    lme = c["lme"]
    gs = c["groups_start"]
    gt = c["groups_total"]
    sl = c["scan_len"]

    print(f"background [0:{pos1}):")
    pre = scan[0:pos1]
    print(" ", pre.hex())
    print("  parity check (even idx -> 0x00, odd idx -> 0xff):",
          all((b==0x00 if i%2==0 else b==0xff) for i,b in enumerate(pre)))

    print(f"gap1 [{lme}:{gs}) ({gs-lme} bytes):")
    g1 = scan[lme:gs]
    print(" ", g1.hex())
    print("  parity even=0x00/odd=0xff:", all((b==0x00 if i%2==0 else b==0xff) for i,b in enumerate(g1)))
    print("  parity even=0xff/odd=0x00:", all((b==0xff if i%2==0 else b==0x00) for i,b in enumerate(g1)))

    ge = gs+gt
    print(f"gap2 [{ge}:{sl}) ({sl-ge} bytes):")
    g2 = scan[ge:sl]
    print(" ", g2.hex())
    print("  parity even=0x00/odd=0xff:", all((b==0x00 if i%2==0 else b==0xff) for i,b in enumerate(g2)))
    print("  parity even=0xff/odd=0x00:", all((b==0xff if i%2==0 else b==0x00) for i,b in enumerate(g2)))
    print(f"  (Ncols*Yextent = {c['Ncols']*c['Yextent']}, parity={'odd' if (c['Ncols']*c['Yextent'])%2 else 'even'})")
    print()
