from pathlib import Path, PurePosixPath
from typing import Protocol

class CertificateStorage(Protocol):
    def save(self, key: str, content: bytes) -> str: ...

    def read(self, key: str) -> bytes: ...

class LocalCertificateStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        path = PurePosixPath(key)
        if (
            not key
            or "\\" in key
            or ":" in key
            or path.is_absolute()
            or ".." in path.parts
        ):
            raise ValueError("invalid certificate storage key")

        target = (self.root / Path(*path.parts)).resolve()

        if target != self.root and self.root not in target.parents:
            raise ValueError("invalid certificate storage key")

        return target

    def save(self, key: str, content: bytes) -> str:
        target = self.path_for(key)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

        return key

    def read(self, key: str) -> bytes:
        return self.path_for(key).read_bytes()
