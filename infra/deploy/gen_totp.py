"""Genera el código TOTP actual para un secreto base32 (para pruebas de 2FA)."""
import base64, hashlib, hmac, struct, sys, time

secret = sys.argv[1].strip()
key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
msg = struct.pack(">Q", int(time.time() // 30))
h = hmac.new(key, msg, hashlib.sha1).digest()
o = h[-1] & 0x0F
code = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000
print("%06d" % code)
