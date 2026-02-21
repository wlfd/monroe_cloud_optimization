from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={
        "coalesce": True,           # Run once if multiple missed executions stacked up (catch-up scenario)
        "max_instances": 1,         # Hard limit: only one ingestion job running at a time
        "misfire_grace_time": 300,  # 5-min grace: run a missed job if less than 5 min late
    },
    timezone="UTC",
)
