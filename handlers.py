import logging
from datetime import datetime, timedelta
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

import database as db
import ai_service as ai
 
logger = logging.getLogger(__name__)
router = Router()

class PlanStates(StatesGroup):
    aim = State()
    start_date = State()
    end_date = State()
    weekends = State()
    remind_time = State()
    edit_text = State()

def get_weekend_keyboard():
    buttons = [
        [KeyboardButton(text="Воскресенье")],
        [KeyboardButton(text="Суббота и воскресенье")],
        [KeyboardButton(text="Без выходных")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_working_days_count(start_dt, end_dt, weekend_type):
    current_dt = start_dt
    count = 0
    while current_dt <= end_dt:
        weekday = current_dt.weekday()
        if weekend_type == "Воскресенье" and weekday == 6:
            pass
        elif weekend_type == "Суббота и воскресенье" and weekday in [5, 6]:
            pass
        else:
            count += 1
        current_dt += timedelta(days=1)
    return count
 
 
def distribute_tasks_by_dates(start_dt, end_dt, weekend_type, ai_tasks) -> list:
    current_dt = start_dt
    tasks_with_dates = []
    task_index = 0
 
    while current_dt <= end_dt and task_index < len(ai_tasks):
        weekday = current_dt.weekday()
        is_weekend = False
        if weekend_type == "Воскресенье" and weekday == 6:
            is_weekend = True
        elif weekend_type == "Суббота и воскресенье" and weekday in [5, 6]:
            is_weekend = True
 
        if not is_weekend:
            date_str = current_dt.strftime("%d:%m:%Y")
            task_desc = ai_tasks[task_index].get("description", "Задача без описания")
            tasks_with_dates.append((date_str, task_desc))
            task_index += 1
 
        current_dt += timedelta(days=1)
    
    return tasks_with_dates

 
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    if await db.user_has_plan(message.from_user.id):
        await message.answer("Для повторного запуска бота сперва удали предыдущий: /delete_plan")
        return
 
    await state.clear()
    await message.answer(
        "Привет!\nЯ — твой AI-помощник в планировании.\n"
        "Я могу построить путь для достижения твоей цели.\n"
        "Какую цель ты бы хотел поставить? Напиши как можно более конкретно и подробно, "
        "чтобы мой план был корректным."
    )
    await state.set_state(PlanStates.aim)
 
 
@router.message(PlanStates.aim)
async def process_aim(message: types.Message, state: FSMContext):
    await state.update_data(aim=message.text)
    await message.answer("В какой день ты хочешь начать это дело? Введи дату в формате ДД:ММ:ГГГГ.")
    await state.set_state(PlanStates.start_date)
 
 
@router.message(PlanStates.start_date)
async def process_start_date(message: types.Message, state: FSMContext):
    try:
        # Проверяем валидность введенной даты
        datetime.strptime(message.text, "%d:%m:%Y")
        await state.update_data(start_date=message.text)
        await message.answer("В какой день ты хочешь завершить это дело? Введи дату в формате ДД:ММ:ГГГГ.")
        await state.set_state(PlanStates.end_date)
    except ValueError:
        await message.answer("Неверный формат! Введи дату строго в формате ДД:ММ:ГГГГ (например, 25:10:2024).")
 
 
@router.message(PlanStates.end_date)
async def process_end_date(message: types.Message, state: FSMContext):
    try:
        end_dt = datetime.strptime(message.text, "%d:%m:%Y")
        user_data = await state.get_data()
        start_dt = datetime.strptime(user_data['start_date'], "%d:%m:%Y")
 
        if end_dt < start_dt:
            await message.answer("Дата завершения не может быть раньше даты начала! Введи заново:")
            return
 
        await state.update_data(end_date=message.text)
        await message.answer(
            "Какие дни ты бы хотел сделать для себя выходными? Выбери из предложенных вариантов.",
            reply_markup=get_weekend_keyboard()
        )
        await state.set_state(PlanStates.weekends)
    except ValueError:
        await message.answer("Неверный формат! Введи дату строго в формате ДД:ММ:ГГГГ.")
 
 
@router.message(PlanStates.weekends, F.text.in_(["Воскресенье", "Суббота и воскресенье", "Без выходных"]))
async def process_weekends(message: types.Message, state: FSMContext):
    weekend_type = message.text
    await state.update_data(weekends=weekend_type)
    user_data = await state.get_data()
 
    start_dt = datetime.strptime(user_data['start_date'], "%d:%m:%Y")
    end_dt = datetime.strptime(user_data['end_date'], "%d:%m:%Y")

    n = get_working_days_count(start_dt, end_dt, weekend_type)
    
    if n <= 0:
        await message.answer("В выбранном диапазоне дат нет рабочих дней! Начни сначала: /start", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
 
    await message.answer(f"Подожди немного, я составляю план на {n} рабочих дней...", reply_markup=ReplyKeyboardRemove())
    ai_response = await ai.generate_plan(user_data['aim'], n)
 
    if not ai_response:
        await message.answer("Произошла ошибка при генерации плана нейросетью. Попробуй позже: /start")
        await state.clear()
        return

    tasks_with_dates = distribute_tasks_by_dates(start_dt, end_dt, weekend_type, ai_response)
    await db.save_user_settings(
        user_id=message.from_user.id,
        aim=user_data['aim'],
        start_date=user_data['start_date'],
        end_date=user_data['end_date'],
        weekends=weekend_type
    )
    await db.save_plan_tasks(message.from_user.id, tasks_with_dates)
    formatted_plan = await db.get_current_plan_text(message.from_user.id)
 
    await message.answer(
        f"Отлично! Вот твой подробный план действий на эти {n} дней:\n\n{formatted_plan}\n"
        "Теперь тебе остаётся лишь установить время для ежедневных напоминаний. "
        "В дни, выбранные тобою выходными, напоминания приходить не будут. Введи время в формате ЧЧ:ММ."
    )
    await state.set_state(PlanStates.remind_time)
 
 
@router.message(PlanStates.remind_time)
async def process_remind_time(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
        await db.save_remind_time(message.from_user.id, message.text)
        await message.answer(
            "Теперь Планировщик готов к работе.\n"
            "Тебе также доступны функции:\n"
            "/edit_plan — редактировать план и датировку вручную.\n"
            "/delete_plan — удалить план.\n"
            "/start — запустить бот заново.\n"
            "/help — напомнить о доступных тебе функциях."
        )
        await state.clear()
    except ValueError:
        await message.answer("Неверный формат времени! Введи время в формате ЧЧ:ММ (например, 09:00 или 18:30).")
 
 
@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Вот перечень доступных тебе функций:\n"
        "/edit_plan — редактировать план и датировку вручную.\n"
        "/delete_plan — удалить план.\n"
        "/start — запустить бот заново."
    )
 
 
@router.message(Command("delete_plan"))
async def cmd_delete_plan(message: types.Message):
    await db.delete_user_plan(message.from_user.id)
    await message.answer("Твой план был успешно удалён.")
 
 
@router.message(Command("edit_plan"))
async def cmd_edit_plan(message: types.Message, state: FSMContext):
    current_plan = await db.get_current_plan_text(message.from_user.id)
    
    if not current_plan:
        await message.answer("У тебя пока нет активного плана. Создай его с помощью команды /start")
        return
 
    await message.answer(
        f"Вот твой текущий план:\n{current_plan}\n"
        "Что бы ты хотел изменить? Введи новый план, сохраняя исходный формат."
    )
    await state.set_state(PlanStates.edit_text)
 
 
@router.message(PlanStates.edit_text)
async def process_edit_text(message: types.Message, state: FSMContext):
    success = await db.update_plan_text(message.from_user.id, message.text)
    
    if success:
        new_plan = await db.get_current_plan_text(message.from_user.id)
        await message.answer(f"Отлично! Вот твой новый план:\n{new_plan}")
        await state.clear()
    else:
        await message.answer(
            "Не удалось распознать формат! Пожалуйста, убедись, что каждая строчка содержит "
            "дату в квадратных скобках, дефис и описание. Пример:\n"
            "1. [25:10:2024] — Моя задача\n\nПопробуй ввести заново:"
        )