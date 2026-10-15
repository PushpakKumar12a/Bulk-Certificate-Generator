import asyncio
from datetime import UTC, datetime
import logging
from uuid import UUID

from app.core.config import Settings, get_settings
from app.db.models import Job, JobStatus
from app.db.session import session_maker
from app.queue.client import AzureStorageQueueClient, QueueMessage, get_queue_client
from app.worker.tasks import BatchRetryError, process

logger = logging.getLogger(__name__)

async def handle_poison_job(job_id: UUID, reason: str) -> None:
    if session_maker is None:
        return
    try:
        async with session_maker() as db:
            job = await db.get(Job, job_id)
            if job and job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                if job.done > 0 and job.success > 0:
                    job.status = JobStatus.COMPLETED_WITH_ERRORS
                else:
                    job.status = JobStatus.FAILED
                job.completed_at = datetime.now(UTC)
                await db.commit()
                logger.warning(f"Marked poisoned job {job_id} as {job.status} ({reason})")
    except Exception as exc:
        logger.error(f"Failed to update database for poisoned job {job_id}: {exc}")

async def process_one_message(
    queue_client: AzureStorageQueueClient,
    message: QueueMessage,
    settings: Settings,
) -> bool:
    raw_job_id = message.content.get("job_id")
    if not raw_job_id:
        logger.error(f"Message {message.id} has no job_id: {message.content}. Moving to poison queue.")
        queue_client.move_to_poison(message, reason="Missing job_id")
        return True

    try:
        job_id = UUID(str(raw_job_id))
    except (ValueError, AttributeError) as exc:
        logger.error(f"Message {message.id} has invalid job_id: {raw_job_id}. Moving to poison queue.")
        queue_client.move_to_poison(message, reason=f"Invalid job_id format: {exc}")
        return True

    if message.dequeue_count > settings.worker_max_retries:
        reason = f"Max dequeue count ({settings.worker_max_retries}) exceeded (count={message.dequeue_count})"
        logger.error(f"Job {job_id} exceeded retry limit. Routing to poison queue: {reason}")
        queue_client.move_to_poison(message, reason=reason)
        await handle_poison_job(job_id, reason)
        return True

    logger.info(f"Processing job {job_id} (attempt {message.dequeue_count}/{settings.worker_max_retries})")
    try:
        await process(
            job_id,
            current_retry=message.dequeue_count - 1,
            max_retries=settings.worker_max_retries,
        )
        queue_client.delete_message(message)
        logger.info(f"Successfully completed and acknowledged job {job_id}")
        return True

    except BatchRetryError as exc:
        logger.warning(
            f"Job {job_id} has partial recipient failures (attempt {message.dequeue_count}/{settings.worker_max_retries}): {exc}"
        )
        if message.dequeue_count >= settings.worker_max_retries:
            reason = f"Exhausted retries with recipient failures: {exc}"
            queue_client.move_to_poison(message, reason=reason)
            await handle_poison_job(job_id, reason)
        return False

    except Exception as exc:
        logger.exception(f"Unexpected error processing job {job_id} (attempt {message.dequeue_count}): {exc}")
        if message.dequeue_count >= settings.worker_max_retries:
            reason = f"Fatal worker exception after max retries: {exc}"
            queue_client.move_to_poison(message, reason=reason)
            await handle_poison_job(job_id, reason)
        return False


async def run_worker_loop(
    single_batch: bool = False,
    max_empty_polls: int = 3,
    poll_interval: float = 2.0,
) -> int:
    settings = get_settings()
    queue_client = get_queue_client(settings)
    processed_count = 0
    empty_polls = 0

    logger.info(
        f"Starting Azure Storage Queue worker (single_batch={single_batch}, queue_name={settings.azure_storage_queue_name})"
    )

    while True:
        try:
            messages = queue_client.receive_messages(
                max_messages=1,
                visibility_timeout=settings.worker_visibility_timeout,
            )

            if not messages:
                empty_polls += 1
                if single_batch and empty_polls >= max_empty_polls:
                    logger.info(f"No messages found after {empty_polls} polls. Drained queue, shutting down.")
                    break
                await asyncio.sleep(poll_interval)
                continue

            empty_polls = 0
            for msg in messages:
                await process_one_message(queue_client, msg, settings)
                processed_count += 1

        except asyncio.CancelledError:
            logger.info("Worker received cancellation signal.")
            break
        except Exception as exc:
            logger.exception(f"Error in worker polling loop: {exc}")
            await asyncio.sleep(poll_interval)

    logger.info(f"Queue worker finished. Processed {processed_count} messages.")
    return processed_count