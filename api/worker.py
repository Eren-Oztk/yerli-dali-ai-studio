"""
api/worker.py
──────────────────────────────────────────────────────────────────────────────
GPU işlerini sıraya dizer — aynı anda sadece 1 upscale işlemi çalışır.
• queue.Queue: thread-safe FIFO kuyruk
• Tek worker thread: GPU'ya serialize erişim → VRAM patlaması yok
• Her iş bir Future gibi sonuç/hata döndürür
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from loguru import logger

from config.settings import settings


@dataclass
class _Job:
    fn: Callable[..., Any]
    args: tuple
    kwargs: dict
    result_event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: Optional[Exception] = None
    position: int = 0       # Kuyruktaki sıra numarası (bilgi amaçlı)


class UpscaleWorker:
    """Tek worker thread üzerinden GPU işlerini sıraya dizer."""

    def __init__(self, max_size: int = 50):
        self._q: queue.Queue[_Job] = queue.Queue(maxsize=max_size)
        self._counter = 0
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._loop,
            name="upscale-worker",
            daemon=True,
        )
        self._thread.start()
        logger.info("Upscale worker başlatıldı.")

    def submit(self, fn: Callable, *args, **kwargs) -> _Job:
        """
        İşi kuyruğa ekler ve _Job döndürür.
        job.result_event.wait(timeout) ile sonucu bekleyebilirsin.

        Raises:
            queue.Full: Kuyruk dolu (MAX_QUEUE_SIZE aşıldı).
        """
        with self._lock:
            self._counter += 1
            pos = self._counter

        job = _Job(fn=fn, args=args, kwargs=kwargs, position=pos)
        try:
            self._q.put_nowait(job)
            logger.debug(f"İş kuyruğa alındı (sıra: {pos}, kuyruk uzunluğu: {self._q.qsize()})")
        except queue.Full:
            raise queue.Full(
                f"Kuyruk dolu ({settings.MAX_QUEUE_SIZE} iş). Lütfen bekle."
            )
        return job

    def queue_length(self) -> int:
        return self._q.qsize()

    def _loop(self) -> None:
        """Worker loop — program kapanana kadar çalışır."""
        logger.info("Worker loop başladı.")
        while True:
            job: _Job = self._q.get()
            logger.debug(f"İş işleniyor (sıra: {job.position})")
            try:
                job.result = job.fn(*job.args, **job.kwargs)
            except Exception as e:
                job.error = e
                logger.error(f"Worker hatası: {e}")
            finally:
                job.result_event.set()      # Bekleyen thread'i uyandır
                self._q.task_done()
                logger.debug(f"İş tamamlandı (sıra: {job.position})")


# Uygulama genelinde tek worker instance
worker = UpscaleWorker(max_size=settings.MAX_QUEUE_SIZE)
