import logging
from pathlib import PurePosixPath

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

def sanitize_storage_key(key: str) -> str:
    if not key or not key.strip():
        raise ValueError("Storage key cannot be empty")

    path = PurePosixPath(key.strip())
    if (
        "\\" in key
        or ":" in key
        or path.is_absolute()
        or ".." in path.parts
    ):
        raise ValueError("Invalid storage key: directory traversal or absolute path detected")

    return str(path)

class CertificateStorage:
    
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = self.init_client()

    def init_client(self):
        from azure.storage.blob import BlobServiceClient

        if self.settings.azure_storage_connection_string:
            return BlobServiceClient.from_connection_string(
                self.settings.azure_storage_connection_string
            )
        if self.settings.azure_storage_account_name:
            from azure.identity import DefaultAzureCredential

            credential = (
                DefaultAzureCredential(managed_identity_client_id=self.settings.azure_client_id)
                if self.settings.azure_client_id
                else DefaultAzureCredential()
            )
            account_url = f"https://{self.settings.azure_storage_account_name}.blob.core.windows.net"
            return BlobServiceClient(account_url=account_url, credential=credential)

        raise ValueError(
            "Neither AZURE_STORAGE_CONNECTION_STRING nor AZURE_STORAGE_ACCOUNT_NAME is configured"
        )

    def save(self, key: str, content: bytes, container: str | None = None) -> str:
        target_container = container or self.settings.azure_storage_certificates_container
        clean_key = sanitize_storage_key(key)
        container_client = self.client.get_container_client(target_container)
        blob_client = container_client.get_blob_client(clean_key)

        content_type = "application/pdf" if clean_key.lower().endswith(".pdf") else "text/csv"
        from azure.storage.blob import ContentSettings

        blob_client.upload_blob(
            content,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return clean_key

    def read(self, key: str, container: str | None = None) -> bytes:
        target_container = container or self.settings.azure_storage_certificates_container
        clean_key = sanitize_storage_key(key)
        container_client = self.client.get_container_client(target_container)
        blob_client = container_client.get_blob_client(clean_key)
        try:
            download_stream = blob_client.download_blob()
            return download_stream.readall()
        except Exception as exc:
            raise FileNotFoundError(f"Blob {clean_key} not found in container {target_container}: {exc}") from exc

def get_storage() -> CertificateStorage:
    return CertificateStorage()