"""Standalone process for the always-on autonomous scheduler.

The web API can still expose manual controls, but production Compose runs this
module as a separate service so scheduled work is not coupled to Uvicorn's
reload/restart lifecycle.
"""

import asyncio
import signal

from backend.app.core.database import init_auth_db, init_db
from backend.app.core.event_logger import agent_logger
from backend.app.tasks.scheduler_daemon import scheduler_daemon


async def run_worker() -> None:
    init_db()
    init_auth_db()
    await scheduler_daemon.start_daemon()
    reminder_task = asyncio.create_task(scheduler_daemon.run_follow_up_reminder_loop())
    stop_event = asyncio.Event()

    def request_stop() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, request_stop)
        except (NotImplementedError, RuntimeError):
            # Windows and embedded event loops may not support signal handlers.
            pass

    agent_logger.log_event("DAEMON", "Standalone scheduler worker is running.")
    await stop_event.wait()
    reminder_task.cancel()
    try:
        await reminder_task
    except asyncio.CancelledError:
        pass
    await scheduler_daemon.stop_daemon()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
