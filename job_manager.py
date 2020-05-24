import asyncio
import itertools
from copy import deepcopy
from dataclasses import dataclass
from typing import List

import tools


@dataclass
class Job:
    job_id: int
    worker_id: str
    data: list
    result: list = None


@dataclass
class WorkerDescriptor:
    status: bool
    assigned_jobs: int


class JobManager:
    SAFE_MODE = True  # data is deep-copied

    def __init__(self, workers=None):
        self._workers = {worker_id: WorkerDescriptor(True, 0) for worker_id in workers} if workers is not None else {}
        self._jobs = []
        self._jobs_done = None

    def _reset(self):
        self._workers = {worker_id: WorkerDescriptor(True, 0) for worker_id in self._workers}
        self._jobs = []
        self._jobs_done = None

    def _reset_workers_status(self):
        for worker_id in self._workers:
            self._workers[worker_id].status = True

    def _available_workers(self):
        workers = [worker_id for worker_id, descriptor in self._workers.items() if descriptor.status]
        if workers:
            return workers
        else:
            self._reset_workers_status()
            return list(self._workers.keys())

    def _get_one_worker(self):
        available_workers = self._available_workers()
        available_workers = {worker_jid: self._workers[worker_jid] for worker_jid in available_workers}
        worker, jobs = min(available_workers.items(),
                           key=lambda worker_and_descriptor: worker_and_descriptor[1].assigned_jobs)
        self._workers[worker].assigned_jobs += 1
        return worker

    async def create_jobs(self, data: list, max_jobs: int = None) -> List[Job]:
        """
        Create a list of job descriptors that can be used to run job tasks.

        :param data: list of data
        :param max_jobs: maximum number of jobs that data can be splitted to
        :return: list of job descriptors
        """
        if self._jobs:
            raise Exception('Cannot create jobs, jobs already created')

        workers = self._available_workers()
        nworkers = len(workers)
        max_jobs = nworkers if max_jobs is None else max_jobs
        njobs = min(max(max_jobs, 1), nworkers)
        chunks = tools.split_into_chunks(data, njobs)
        not_empty_chunks = list(filter(None, chunks))

        for i, chunk in enumerate(not_empty_chunks):
            worker = self._get_one_worker()
            job = Job(i, worker, data=chunk, result=[])
            self._jobs.append(job)

        if self._jobs_done is None:
            self._jobs_done = asyncio.Semaphore(value=0)

        if self.SAFE_MODE:
            return deepcopy(self._jobs)
        else:
            return self._jobs

    async def job_done(self, job: Job):
        """
        Notify manager that job has been done.

        :param job: job that has been finished
        """
        if not self._jobs:
            raise Exception('Jobs not created!')

        self._jobs[job.job_id] = job
        self._workers[job.worker_id].assigned_jobs -= 1
        self._workers[job.worker_id].status = True

        self._jobs_done.release()

    async def job_failed(self, job: Job) -> Job:
        """
        Notify manager that job failed and receive a new job descriptor (with a changed worker_id).

        :param job: job_descriptor of the job that failed
        :return: job descriptor with a new worker assigned
        """
        if not self._jobs:
            raise Exception('Jobs not created!')

        if job.worker_id not in self._workers:
            msg = 'Worker {} not found in JobManager (was worker_id of a job modified?)'.format(job.worker_id)
            raise ValueError(msg)

        self._workers[job.worker_id].assigned_jobs -= 1
        self._workers[job.worker_id].status = False
        new_worker = self._get_one_worker()

        self._jobs[job.job_id].worker_id = new_worker
        if self.SAFE_MODE:
            return deepcopy(self._jobs[job.job_id])
        else:
            return self._jobs[job.job_id]

    async def jobs_finished(self) -> List:
        """
        Wait for all jobs to be done.

        :return: result of computations
        """
        if not self._jobs:
            raise Exception('Jobs not created!')

        for _ in range(len(self._jobs)):
            await self._jobs_done.acquire()

        results = list(itertools.chain(*(job.result for job in self._jobs)))
        self._reset()

        return results
