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

mains = {
    "1496 (Ncols=1)": "+bYU+1oFAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeA+tAAkPAgD5H9HVAQCf5gEBfn5+AQAgCADUH8/oANQE0AEPAAP5DwIACYDRAgAAAMdoaS4F8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB",
    "1502 (Ncols=2)": "+bYU+8sGAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBDz4BCQ8CAPEfCF4CAJ/mAQF+fn4BACAIANQfz+gA1ATQAQ/wAN0P6APxDwIACYAIAgAAAMdoaZ8G8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB",
    "1504 (Ncols=3)": "+bYU+zgIAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBD5EAfg/PAQkPAgDnHz/lAgCf5gEBfn5+AQAgCADUH8/oANQE0AEP8AD/zg/OBOcPAgAJgD8CAAAAx2hpDAjwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=",
    "1506 (Ncols=4)": "+bYU+6UJAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBD5EA/xAPYAIJDwIA3R92bAMAn+YBAX5+fgEAIAgA1B/P6ADUBNABD/AA//+/D7QF3Q8CAAmAdgIAAADHaGl5CfANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==",
    "1508 (Ncols=5)": "+bYU+xILAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBD5EA/6EP8QIJDwIA0x+t8wMAn+YBAX5+fgEAIAgA1B/P6ADUBNABD/AA////sA+aBtMPAgAJgK0CAAAAx2hp5grwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=",
}

headers = {}
mats = {}
for name, b64 in mains.items():
    dec = decode_blob(b64)
    header, scan, mat, mat_counter = get_scan(dec)
    headers[name] = header
    mats[name] = mat
    print(f"{name}: header={header.hex()}  mat_counter={mat_counter}  mat_tail={mat[4:].hex()}")

ref = headers["1496 (Ncols=1)"]
for name, h in headers.items():
    print(f"{name}: header == 1496's header? {h == ref}")

refmat = mats["1496 (Ncols=1)"][4:]
for name, m in mats.items():
    print(f"{name}: mat[4:] == 1496's mat[4:]? {m[4:] == refmat}")
