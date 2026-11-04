"""Generate VAPID keys for Web Push.

Usage (inside the backend container or any env with pywebpush installed):
    python scripts/generate_vapid.py
Copy the printed values into your .env file.
"""
import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


vapid = Vapid01()
vapid.generate_keys()
public = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")

print(f"VAPID_PUBLIC_KEY={b64(public)}")
print(f"VAPID_PRIVATE_KEY={b64(private)}")
