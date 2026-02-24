import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render сам создает эту переменную

if not BASE_URL:
    BASE_URL = "http://localhost"  # для локального тестирования

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
    logger.error("Добавьте BOT_TOKEN в переменные окружения на Render")
    exit(1)

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

# ========== СОСТОЯНИЯ ДЛЯ FSM ==========
class BotStates(StatesGroup):
    waiting_for_topic = State()      # ожидание темы песни
    waiting_for_voice = State()      # ожидание голосового сообщения
    waiting_for_photo = State()      # ожидание фото

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== КЛАВИАТУРА ==========
def get_main_keyboard():
    """Создает главную клавиатуру с кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✍️ Написать текст песни")],
            [KeyboardButton(text="🎤 Создать кавер голосом")],
            [KeyboardButton(text="🎬 Сделать клип по фото")]
        ],
        resize_keyboard=True
    )
    return keyboard

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Привет! Я музыкальный ИИ-бот!\n\n"
        "Я умею:\n"
        "✍️ Писать тексты песен на любую тему\n"
        "🎤 Клонировать голос и петь им песни\n"
        "🎬 Создавать анимированные клипы по фото\n\n"
        "Выбери действие на клавиатуре ниже:",
        reply_markup=get_main_keyboard()
    )

# ========== РЕЖИМ 1: НАПИСАТЬ ТЕКСТ ПЕСНИ ==========
@dp.message(lambda message: message.text == "✍️ Написать текст песни")
async def choose_text(message: Message, state: FSMContext):
    """Пользователь выбрал написание текста"""
    await state.set_state(BotStates.waiting_for_topic)
    await message.answer(
        "📝 Отлично! Напиши тему будущей песни.\n"
        "Например: 'любовь на Марсе', 'грустный дождь' или 'программист и кофе'"
    )

@dp.message(BotStates.waiting_for_topic)
async def generate_text(message: Message, state: FSMContext):
    """Получаем тему и генерируем текст"""
    topic = message.text
    
    await message.answer(f"🎵 Генерирую текст песни на тему: '{topic}'...\nЭто займет несколько секунд.")
    
    # Имитация генерации (заглушка)
    await asyncio.sleep(1)
    
    generated_text = f"""🎵 Текст песни на тему "{topic}":

Куплет 1:
В мире цифровом и суетном
Мы ищем то, что нам неведомо
{topic} - наша главная мечта
Что согревает нам сердца

Припев:
И в такт битам стучит душа
Музыка вечно хороша
{topic} ведет нас за собой
Мы за мечтой, мы за мечтой

Куплет 2:
Среди пикселей и огней
Мы становимся сильней
{topic} дарит новый свет
И оставляет яркий след

Припев:
И в такт битам стучит душа
Музыка вечно хороша
{topic} ведет нас за собой
Мы за мечтой, мы за мечтой"""
    
    await message.answer(f"✅ Готово!\n\n{generated_text}")
    await message.answer("Что делаем дальше?", reply_markup=get_main_keyboard())
    await state.clear()

# ========== РЕЖИМ 2: КАВЕР ГОЛОСОМ ==========
@dp.message(lambda message: message.text == "🎤 Создать кавер голосом")
async def choose_voice(message: Message, state: FSMContext):
    """Пользователь выбрал создание кавера"""
    await state.set_state(BotStates.waiting_for_voice)
    await message.answer(
        "🎤 Отлично! Отправь мне голосовое сообщение (напой мелодию или просто скажи пару фраз),\n"
        "а затем напиши тему песни в текстовом сообщении."
    )

@dp.message(BotStates.waiting_for_voice)
async def process_voice(message: Message, state: FSMContext):
    """Обработка голосового сообщения и темы"""
    
    # Если прислали голосовое сообщение
    if message.voice:
        file_id = message.voice.file_id
        await message.answer("✅ Голосовое сообщение получено! Теперь напиши тему песни.")
        await state.update_data(voice_file_id=file_id)
    
    # Если прислали текст (тему песни)
    else:
        topic = message.text
        data = await state.get_data()
        voice_file_id = data.get('voice_file_id')
        
        if voice_file_id:
            await message.answer(f"🎵 Создаю кавер на тему '{topic}' с твоим голосом...\nЭто займет около 30 секунд.")
            
            # Имитация генерации
            await asyncio.sleep(2)
            
            await message.answer(
                f"✅ Кавер готов! (здесь будет аудиофайл)\n"
                f"Тема: {topic}\n"
                f"🎤 Использован твой голос"
            )
            await state.clear()
            await message.answer("Что делаем дальше?", reply_markup=get_main_keyboard())
        else:
            await message.answer("❌ Сначала отправь голосовое сообщение!")

# ========== РЕЖИМ 3: КЛИП ПО ФОТО ==========
@dp.message(lambda message: message.text == "🎬 Сделать клип по фото")
async def choose_photo(message: Message, state: FSMContext):
    """Пользователь выбрал создание клипа"""
    await state.set_state(BotStates.waiting_for_photo)
    await message.answer(
        "🎬 Отлично! Отправь мне фото,\n"
        "а затем напиши тему или настроение для клипа."
    )

@dp.message(BotStates.waiting_for_photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка фото и темы клипа"""
    
    # Если прислали фото
    if message.photo:
        photo = message.photo[-1]  # берем самое качественное фото
        file_id = photo.file_id
        await message.answer("✅ Фото получено! Теперь напиши тему для клипа.")
        await state.update_data(photo_file_id=file_id)
    
    # Если прислали текст (тему клипа)
    else:
        mood = message.text
        data = await state.get_data()
        photo_file_id = data.get('photo_file_id')
        
        if photo_file_id:
            await message.answer(f"🎬 Создаю клип с настроением '{mood}'...\nЭто займет около 40 секунд.")
            
            # Имитация генерации
            await asyncio.sleep(2)
            
            await message.answer(
                f"✅ Клип готов! (здесь будет видеофайл)\n"
                f"Настроение: {mood}"
            )
            await state.clear()
            await message.answer("Что делаем дальше?", reply_markup=get_main_keyboard())
        else:
            await message.answer("❌ Сначала отправь фото!")

# ========== ОБРАБОТЧИК НЕИЗВЕСТНЫХ СООБЩЕНИЙ ==========
@dp.message()
async def unknown_message(message: Message):
    """Обработчик любых других сообщений"""
    await message.answer(
        "🤔 Я не понимаю эту команду.\n"
        "Пожалуйста, используй кнопки на клавиатуре.",
        reply_markup=get_main_keyboard()
    )

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER ==========
async def handle_webhook(request):
    """Обработчик вебхуков от Telegram"""
    try:
        update = await request.json()
        await dp.feed_update(bot, types.Update(**update))
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}")
        return web.Response(status=500)

async def handle_health(request):
    """Health check для Render (чтобы бот не засыпал)"""
    return web.Response(text="OK", status=200)

async def handle_root(request):
    """Корневой маршрут"""
    return web.Response(text="🤖 Music Bot is running! Webhook is active.", status=200)

async def on_startup():
    """Действия при запуске бота"""
    try:
        await bot.set_webhook(WEBHOOK_URL)
        bot_info = await bot.me()
        logger.info(f"✅ Вебхук установлен на {WEBHOOK_URL}")
        logger.info(f"🤖 Бот @{bot_info.username} запущен и готов к работе!")
    except Exception as e:
        logger.error(f"❌ Ошибка установки вебхука: {e}")

async def on_shutdown():
    """Действия при остановке бота"""
    await bot.delete_webhook()
    logger.info("👋 Вебхук удален. Бот остановлен.")

async def main():
    """Главная функция запуска"""
    # Создаем aiohttp приложение
    app = web.Application()
    
    # Добавляем маршруты
    app.router.add_post(WEBHOOK_PATH, handle_webhook)  # вебхук от Telegram
    app.router.add_get("/health", handle_health)        # проверка здоровья
    app.router.add_get("/", handle_root)                 # корневой маршрут
    
    # Регистрируем startup и shutdown
    app.on_startup.append(lambda _: on_startup())
    app.on_shutdown.append(lambda _: on_shutdown())
    
    # Получаем порт из переменных окружения Render
    port = int(os.getenv("PORT", 8000))
    
    # Запускаем сервер
    logger.info(f"🚀 Запуск сервера на порту {port}")
    return app

# ========== ТОЧКА ВХОДА ==========
if __name__ == "__main__":
    web.run_app(main(), port=int(os.getenv("PORT", 8000)))