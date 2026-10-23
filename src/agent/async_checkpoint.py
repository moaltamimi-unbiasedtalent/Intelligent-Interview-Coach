"""Async bridge over the existing official saver; same durable threads, no second store.

The synchronous application remains supported. Blocking saver methods run in worker
threads so astream_events v2 can use the same saver and serialization lock.
"""
from __future__ import annotations

import asyncio
from functools import partial

from langgraph.checkpoint.base import BaseCheckpointSaver


class AsyncCheckpointBridge(BaseCheckpointSaver):
    def __init__(self, saver):
        super().__init__(serde=saver.serde)
        self.saver = saver

    @property
    def config_specs(self):
        return self.saver.config_specs

    def get_tuple(self, config):
        return self.saver.get_tuple(config)

    def get_next_version(self, current, channel):
        return self.saver.get_next_version(current, channel)

    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.saver.get_tuple, config)

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self.saver.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        return await asyncio.to_thread(self.saver.put_writes, config, writes, task_id, task_path)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        rows = await asyncio.to_thread(lambda: list(self.saver.list(config, filter=filter, before=before, limit=limit)))
        for row in rows:
            yield row

    async def adelete_thread(self, thread_id):
        return await asyncio.to_thread(partial(self.saver.delete_thread, thread_id))
