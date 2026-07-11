import base64
import lz4.block
import xxhash

MAGIC_SEED = 0xa1b2c3d4e5f6e7d8
MASK64 = 0xFFFFFFFFFFFFFFFF

def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size), raw

def encode_blob(data):
    compressed = lz4.block.compress(data, store_size=False)
    return b'\xf9\xb6\x14\xfb' + len(data).to_bytes(4, 'little') + b'\x00\x00\x00\x00' + compressed

def compute_hash(raw_bytes):
    return xxhash.xxh64(raw_bytes, seed=MAGIC_SEED).intdigest()

def to_signed64(u):
    u &= MASK64
    return u - (1 << 64) if u >= (1 << 63) else u
