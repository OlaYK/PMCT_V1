#!/usr/bin/env python3
from cryptography.fernet import Fernet

key = Fernet.generate_key()
print("\nEncryption Key:")
print("=" * 50)
print(key.decode())
print("=" * 50)
print("\nAdd to .env:")
print(f"ENCRYPTION_KEY={key.decode()}")
print()