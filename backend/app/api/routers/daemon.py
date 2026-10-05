"""24/7 autonomous scheduler control API."""

from fastapi import APIRouter

from backend.app.tasks.scheduler_daemon import scheduler_daemon

router = APIRouter()


@router.get("/daemon/status")
def get_daemon_status():
    return scheduler_daemon.get_status()


@router.post("/daemon/start")
async def start_autonomous_daemon():
    return await scheduler_daemon.start_daemon()


@router.post("/daemon/stop")
async def stop_autonomous_daemon():
    return await scheduler_daemon.stop_daemon()


@router.post("/daemon/trigger_nightly")
async def trigger_nightly_sweep_now():
    return await scheduler_daemon.trigger_nightly_sweep()


@router.post("/daemon/trigger_morning")
async def trigger_morning_prep_now():
    return await scheduler_daemon.trigger_morning_prep()
