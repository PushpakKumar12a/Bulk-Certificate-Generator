import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

@dataclass
class QueueMessage:
    id: str
    pop_receipt: str
    content: dict[str, Any]
    dequeue_count: int = 1

class AzureStorageQueueClient:

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.queue_client = None
        self.poison_client = None
        self.init_clients()

    def init_clients(self) -> None:
        from azure.storage.queue import (
            QueueClient,
            TextBase64DecodePolicy,
            TextBase64EncodePolicy,
        )

        queue_name = self.settings.azure_storage_queue_name
        poison_name = self.settings.azure_storage_poison_queue_name

        if self.settings.azure_storage_connection_string:
            self.queue_client = QueueClient.from_connection_string(
                self.settings.azure_storage_connection_string,
                queue_name=queue_name,
                message_encode_policy=TextBase64EncodePolicy(),
                message_decode_policy=TextBase64DecodePolicy(),
            )
            self.poison_client = QueueClient.from_connection_string(
                self.settings.azure_storage_connection_string,
                queue_name=poison_name,
                message_encode_policy=TextBase64EncodePolicy(),
                message_decode_policy=TextBase64DecodePolicy(),
            )
        elif self.settings.azure_storage_account_name:
            from azure.identity import DefaultAzureCredential

            credential = (
                DefaultAzureCredential(managed_identity_client_id=self.settings.azure_client_id)
                if self.settings.azure_client_id
                else DefaultAzureCredential()
            )
            base_url = f"https://{self.settings.azure_storage_account_name}.queue.core.windows.net"

            self.queue_client = QueueClient(
                account_url=base_url,
                queue_name=queue_name,
                credential=credential,
                message_encode_policy=TextBase64EncodePolicy(),
                message_decode_policy=TextBase64DecodePolicy(),
            )
            self.poison_client = QueueClient(
                account_url=base_url,
                queue_name=poison_name,
                credential=credential,
                message_encode_policy=TextBase64EncodePolicy(),
                message_decode_policy=TextBase64DecodePolicy(),
            )
        else:
            raise ValueError(
                "Neither AZURE_STORAGE_CONNECTION_STRING nor AZURE_STORAGE_ACCOUNT_NAME is configured"
            )

    def send_message(self, content: dict[str, Any]) -> str:
        text = json.dumps(content)
        receipt = self.queue_client.send_message(text)
        return receipt.id

    def receive_messages(
        self, max_messages: int = 1, visibility_timeout: int = 300
    ) -> list[QueueMessage]:
        results: list[QueueMessage] = []
        response = self.queue_client.receive_messages(
            messages_per_page=max_messages,
            visibility_timeout=visibility_timeout,
        )
        for msg in response:
            try:
                data = json.loads(msg.content)
            except Exception:
                data = {"raw": msg.content}

            results.append(
                QueueMessage(
                    id=msg.id,
                    pop_receipt=msg.pop_receipt,
                    content=data,
                    dequeue_count=msg.dequeue_count,
                )
            )
        return results

    def delete_message(self, message: QueueMessage) -> None:
        self.queue_client.delete_message(message.id, message.pop_receipt)

    def move_to_poison(self, message: QueueMessage, reason: str = "") -> None:
        poison_payload = dict(message.content)
        poison_payload["_poison_reason"] = reason
        poison_payload["_poisoned_at"] = datetime.now(timezone.utc).isoformat()
        poison_payload["_dequeue_count"] = message.dequeue_count

        try:
            self.poison_client.send_message(json.dumps(poison_payload))
        except Exception as exc:
            logger.error(f"Failed to enqueue into poison queue: {exc}")

        self.delete_message(message)

    def ping(self) -> bool:
        try:
            self.queue_client.get_queue_properties()
            return True
        except Exception as exc:
            logger.error(f"Queue ping failed: {exc}")
            return False

def get_queue_client(settings: Settings | None = None) -> AzureStorageQueueClient:
    cfg = settings or get_settings()
    return AzureStorageQueueClient(cfg)