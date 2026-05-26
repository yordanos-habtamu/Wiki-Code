"""
Encryption utility for at-rest protection of provider credentials.
Uses hardware/environmental signature for key derivation.
"""

import os
import sys
import json
import hashlib
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CredentialEncryptor:
    """
    Handles encryption/decryption of provider credentials using 
    environment-derived keys for at-rest protection.
    """
    
    def __init__(self, salt: Optional[bytes] = None):
        """
        Initialize the encryptor with a key derived from environmental signatures.
        """
        if salt is None:
            # Generate salt from machine-specific identifiers
            salt = self._generate_machine_salt()
        
        self.salt = salt
        self.key = self._derive_key()
        self.fernet = Fernet(self.key)

    def _generate_machine_salt(self) -> bytes:
        """
        Generate a deterministic salt from environmental signatures:
        - Hostname
        - Username
        - Home directory path
        This ensures the same machine always derives the same key.
        """
        machine_sig = f"{os.uname().nodename}-{os.getlogin()}-{os.path.expanduser('~')}"
        return hashlib.sha256(machine_sig.encode('utf-8')).digest()[:16]

    def _derive_key(self) -> bytes:
        """
        Derive a Fernet key from the machine signature using PBKDF2HMAC.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(b"wikihub-credential-protection"))

    def encrypt_data(self, plaintext: str) -> str:
        """
        Encrypt a string and return base64-encoded ciphertext.
        """
        encrypted = self.fernet.encrypt(plaintext.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')

    def decrypt_data(self, ciphertext: str) -> str:
        """
        Decrypt a base64-encoded ciphertext string.
        """
        try:
            decoded = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode('utf-8')
        except Exception as e:
            print(f"Error in CredentialEncryptor.decrypt_data: {e}", file=sys.stderr)
            raise

    def encrypt_file(self, input_path: str, output_path: str) -> bool:
        """
        Read a plaintext JSON file, encrypt it, and write to output path.
        """
        try:
            with open(input_path, 'r') as f:
                plaintext = f.read()
            
            ciphertext = self.encrypt_data(plaintext)
            
            with open(output_path, 'w') as f:
                f.write(ciphertext)
            
            print(f"Encrypted {input_path} -> {output_path}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"Error in CredentialEncryptor.encrypt_file: {e}", file=sys.stderr)
            return False

    def decrypt_file(self, input_path: str) -> Optional[str]:
        """
        Read an encrypted file and return the decrypted plaintext.
        """
        try:
            with open(input_path, 'r') as f:
                ciphertext = f.read()
            
            plaintext = self.decrypt_data(ciphertext)
            return plaintext
        except Exception as e:
            print(f"Error in CredentialEncryptor.decrypt_file: {e}", file=sys.stderr)
            return None
