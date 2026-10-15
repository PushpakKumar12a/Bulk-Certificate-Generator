import argparse
import asyncio
import logging
import sys

from app.worker.queue_worker import run_worker_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk Certificate Generator Queue Worker")
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously polling for incoming Azure Storage Queue messages",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Poll interval in seconds when queue is empty",
    )

    args, _ = parser.parse_known_args()
    asyncio.run(
        run_worker_loop(
            single_batch=not args.continuous,
            poll_interval=args.poll_interval,
        )
    )

if __name__ == "__main__":
    main()
