import asyncio
import logging
import os
import time

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from telegram_import.extraction import validate_provider
from telegram_import.locking import worker_lock
from telegram_import.models import TelegramCursor
from telegram_import.service import close_deleted_messages, delete_expired_loads, capture_message, retry_failed_messages, ttl_hours


logger = logging.getLogger(__name__)


def database_call(function, *args, **kwargs):
    close_old_connections()
    try:
        return function(*args, **kwargs)
    finally:
        close_old_connections()


run_db = sync_to_async(database_call)


class Command(BaseCommand):
    help = "Watch one Telegram group and import new load posts"

    def add_arguments(self, parser):
        parser.add_argument("--backfill", type=int, default=0)

    def handle(self, *args, **options):
        from telethon import TelegramClient, events, utils

        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        group_name = os.getenv("TELEGRAM_GROUP")
        if not all((api_id, api_hash, group_name)):
            raise CommandError("Set TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_GROUP")
        try:
            provider = validate_provider()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if options["backfill"] < 0:
            raise CommandError("--backfill must be non-negative")
        ttl_hours()

        async def run():
            client = TelegramClient("/app/.telegram_session/importer", int(api_id), api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                raise CommandError("Run telegram_login interactively first")
            group = await client.get_entity(group_name)
            chat_id = utils.get_peer_id(group)

            try:
                async with worker_lock(chat_id):
                    await watch(client, group, chat_id)
            finally:
                await client.disconnect()

        async def watch(client, group, chat_id):
            self.stdout.write(f"Watching {group_name} ({chat_id}); provider={provider}")
            @client.on(events.NewMessage(chats=group))
            @client.on(events.MessageEdited(chats=group))
            async def on_message(event):
                await process(event.message)

            @client.on(events.MessageDeleted(chats=group))
            async def on_deleted(event):
                await run_db(close_deleted_messages, chat_id, event.deleted_ids)

            async def parse_loop():
                while True:
                    count = 0
                    started = time.monotonic()
                    task = asyncio.create_task(asyncio.to_thread(database_call, retry_failed_messages, chat_id, on_result=self.report_result))
                    while not task.done():
                        done, _ = await asyncio.wait({task}, timeout=30)
                        if not done:
                            self.stdout.write(f"AI parsing in progress; elapsed={int(time.monotonic() - started)}s; Telegram intake remains active")
                    try:
                        count = await task
                        if count:
                            self.stdout.write(f"Parsed {count} saved message; elapsed={int(time.monotonic() - started)}s")
                    except Exception:
                        logger.exception("AI worker failed; saved messages remain queued")
                    await asyncio.sleep(1 if count else 10)

            parser_task = asyncio.create_task(parse_loop())
            cursor = await run_db(TelegramCursor.objects.filter(chat_id=chat_id).first)
            if cursor:
                async for message in client.iter_messages(group, min_id=cursor.last_message_id, reverse=True):
                    await process(message)
            elif options["backfill"]:
                messages = [message async for message in client.iter_messages(group, limit=options["backfill"])]
                for message in reversed(messages):
                    await process(message)
            else:
                latest = await client.get_messages(group, limit=1)
                if latest:
                    await run_db(TelegramCursor.objects.create, chat_id=chat_id, last_message_id=latest[0].id)

            async def expire_loop():
                while True:
                    try:
                        await run_db(delete_expired_loads)
                    except Exception:
                        logger.exception("Telegram import maintenance failed; retrying in 60 seconds")
                    await asyncio.sleep(60)

            await asyncio.gather(client.run_until_disconnected(), expire_loop(), parser_task)

        async def process(message):
            try:
                result = await run_db(capture_message,
                    chat_id=message.chat_id,
                    message_id=message.id,
                    group_name=group_name,
                    text=message.raw_text,
                    posted_at=message.date,
                )
                self.report_result(result)
            except Exception:
                logger.exception("Failed to import Telegram message %s", message.id)

        asyncio.run(run())

    def report_result(self, result):
        detail = f"; retry at {result.retry_at.isoformat()}; reason={result.detail[:160]}" if result.retry_at else ""
        self.stdout.write(f"Telegram message {result.message_id}: {result.status}{detail}")
