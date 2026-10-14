from contextlib import asynccontextmanager

import psycopg
from django.conf import settings
from django.core.management.base import CommandError


@asynccontextmanager
async def worker_lock(chat_id):
    database = settings.DATABASES["default"]
    connection = await psycopg.AsyncConnection.connect(
        dbname=database["NAME"], user=database["USER"], password=database["PASSWORD"],
        host=database["HOST"], port=database["PORT"], autocommit=True,
    )
    async with connection:
        cursor = await connection.execute("SELECT pg_try_advisory_lock(%s)", (chat_id,))
        acquired, = await cursor.fetchone()
        if not acquired:
            raise CommandError("Another Telegram importer is already watching this group")
        yield
