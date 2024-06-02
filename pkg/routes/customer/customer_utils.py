import hashlib
import secrets


def generate_temp_password(length=8):
    # Generate a random temporary password
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()"
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return temp_password


def hash_password(password):
    # Hash the password using SHA-256
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    return hashed_password


def verify_password(plain_password, hashed_password):
    # Verify the plain password against the hashed password
    return hash_password(plain_password) == hashed_password
