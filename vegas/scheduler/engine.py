"""
Asynchronous Scheduler and Automation Engine for VEGAS AIOS.
Allows the agent to register background loops, cron timers, and notification triggers.
"""

import math
import time
import threading
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timedelta

class ScheduledJob:
    def __init__(self, job_id: str, interval_seconds: float, func: Callable, max_iterations: Optional[int] = None):
        if (isinstance(interval_seconds, bool)
                or not isinstance(interval_seconds, (int, float))
                or not math.isfinite(interval_seconds) or interval_seconds <= 0):
            raise ValueError("interval_seconds must be a finite positive number")
        if max_iterations is not None and (
                isinstance(max_iterations, bool) or not isinstance(max_iterations, int)
                or max_iterations <= 0):
            raise ValueError("max_iterations must be a positive integer or None")
        if not callable(func):
            raise ValueError("func must be callable")
        self.job_id = job_id
        self.interval_seconds = interval_seconds
        self.func = func
        self.max_iterations = max_iterations
        self.iterations = 0
        self.last_run: Optional[datetime] = None
        self.next_run = datetime.now() + timedelta(seconds=interval_seconds)

class VegasScheduler:
    def __init__(self):
        self.jobs: Dict[str, ScheduledJob] = {}
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the background scheduler thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="VegasSchedulerThread")
        self._thread.start()
        print("VegasScheduler: Background automation engine started.", flush=True)

    def stop(self):
        """Stops the scheduler loop."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("VegasScheduler: Background automation engine stopped.", flush=True)

    def register_job(self, job_id: str, interval_seconds: float, func: Callable, max_iterations: Optional[int] = None) -> str:
        """
        Registers a job to run periodically.
        """
        job = ScheduledJob(job_id, interval_seconds, func, max_iterations)
        self.jobs[job_id] = job
        print(f"VegasScheduler: Job '{job_id}' registered (interval {interval_seconds}s).", flush=True)
        return job_id

    def cancel_job(self, job_id: str):
        if job_id in self.jobs:
            del self.jobs[job_id]
            print(f"VegasScheduler: Job '{job_id}' cancelled.", flush=True)

    def _run_loop(self):
        while self.running:
            now = datetime.now()
            jobs_to_run = []
            
            for job_id, job in list(self.jobs.items()):
                if now >= job.next_run:
                    jobs_to_run.append(job)
                    
            for job in jobs_to_run:
                try:
                    print(f"VegasScheduler: Dispatching background job '{job.job_id}' at {now.isoformat()}", flush=True)
                    job.func()
                    job.last_run = now
                    job.iterations += 1
                    
                    if job.max_iterations and job.iterations >= job.max_iterations:
                        self.cancel_job(job.job_id)
                    else:
                        job.next_run = now + timedelta(seconds=job.interval_seconds)
                except Exception as e:
                    print(f"VegasScheduler: Exception running job '{job.job_id}': {e}", flush=True)
                    # Reschedule on exception to ensure system robustness
                    job.next_run = now + timedelta(seconds=job.interval_seconds)
                    
            time.sleep(1.0)

# Global scheduler engine
scheduler = VegasScheduler()
