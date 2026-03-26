from passlib.context import CryptContext

class PasswordHasher:
    def __init__(self) -> None:
        self._context = CryptContext(schemes=["bcrypt"])

    def hash(self, raw_password: str) -> str:
        return self._context.hash(raw_password)

    def verify(self, raw_password: str, hashed_password: str) -> bool:
        return self._context.verify(raw_password, hashed_password)

password_hasher = PasswordHasher()