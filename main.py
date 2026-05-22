import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import database as db
from handlers import router
from config import BOT_TOKEN
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
 
 
async def send_daily_reminders(bot: Bot):
    now = datetime.now()
    current_date = now.strftime("%d:%m:%Y")
    current_time = now.strftime("%H:%M")
    reminders = await db.get_tasks_for_remind(current_date, current_time)
    
    for user_id, description in reminders:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"Твоя задача на сегодня:\n{description}"
            )
            logger.info(f"Напоминание успешно отправлено пользователю {user_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить напоминание {user_id}: {e}")
 
 
async def main():
    from aiogram.client.default import DefaultBotProperties
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await db.init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_reminders, 
        trigger="cron", 
        minute="*", 
        args=[bot]
    )

    scheduler.start()
    logger.info("Планировщик напоминаний успешно запущен.")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот принудительно остановлен.")
