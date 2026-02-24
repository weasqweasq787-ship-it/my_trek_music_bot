import os
import asyncio
import logging
import aiohttp
import aiofiles
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from datetime import datetime
import uuid

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # API ключ OpenAI (ChatGPT + TTS)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")  # API ключ ElevenLabs для клонирования голоса
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")

if not BASE_URL:
    BASE_URL = "http://localhost"

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден!")
    exit(1)

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

# ========== СОСТОЯНИЯ ДЛЯ FSM ==========
class BotStates(StatesGroup):
    waiting_for_topic = State()           # ожидание темы песни
    waiting_for_voice_sample = State()     # ожидание образца голоса
    waiting_for_voice_topic = State()      # ожидание темы для голоса
    waiting_for_photo = State()             # ожидание фото
    waiting_for_photo_topic = State()       # ожидание темы для клипа

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def download_file(file_id: str, destination: str):
    """Скачивает файл из Telegram"""
    file = await bot.get_file(file_id)
    file_path = file.file_path
    await bot.download_file(file_path, destination)
    return destination

async def generate_lyrics_with_gpt(topic: str) -> str:
    """Генерирует текст песни через ChatGPT"""
    if not OPENAI_API_KEY:
        return f"❌ OpenAI API ключ не настроен. Текст песни на тему '{topic}':\n\n(здесь был бы сгенерированный текст)"
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "Ты профессиональный поэт-песенник. Напиши текст песни на заданную тему. Используй структуру: куплет-припев-куплет-припев-аутро."},
                    {"role": "user", "content": f"Напиши текст песни на тему: {topic}"}
                ],
                "temperature": 0.8,
                "max_tokens": 1000
            }
            
            async with session.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    return f"❌ Ошибка API: {resp.status}\n\nСгенерирован тестовый текст на тему '{topic}'."
    except Exception as e:
        logger.error(f"Ошибка при генерации текста: {e}")
        return f"❌ Ошибка: {str(e)}\n\nТестовый текст на тему '{topic}'."

async def clone_voice_with_elevenlabs(audio_path: str, text: str) -> str:
    """Клонирует голос и генерирует речь через ElevenLabs"""
    if not ELEVENLABS_API_KEY:
        return None
    
    try:
        # Сначала создаем голос из образца
        async with aiohttp.ClientSession() as session:
            # 1. Загружаем аудио для клонирования
            voice_name = f"voice_{uuid.uuid4().hex[:8]}"
            
            # Читаем аудиофайл
            async with aiofiles.open(audio_path, 'rb') as f:
                audio_data = await f.read()
            
            # Создаем форму для отправки
            form_data = aiohttp.FormData()
            form_data.add_field('name', voice_name)
            form_data.add_field('files', audio_data, filename='sample.mp3', content_type='audio/mpeg')
            
            headers = {
                'xi-api-key': ELEVENLABS_API_KEY
            }
            
            # Отправляем запрос на создание голоса
            async with session.post('https://api.elevenlabs.io/v1/voices/add', headers=headers, data=form_data) as resp:
                if resp.status == 200:
                    voice_data = await resp.json()
                    voice_id = voice_data['voice_id']
                    
                    # 2. Генерируем речь с новым голосом
                    tts_payload = {
                        'text': text,
                        'model_id': 'eleven_multilingual_v2',
                        'voice_settings': {
                            'stability': 0.5,
                            'similarity_boost': 0.75
                        }
                    }
                    
                    tts_url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
                    tts_headers = {
                        'xi-api-key': ELEVENLABS_API_KEY,
                        'Content-Type': 'application/json'
                    }
                    
                    async with session.post(tts_url, headers=tts_headers, json=tts_payload) as tts_resp:
                        if tts_resp.status == 200:
                            output_path = f'/tmp/output_{uuid.uuid4().hex}.mp3'
                            async with aiofiles.open(output_path, 'wb') as out_f:
                                await out_f.write(await tts_resp.read())
                            return output_path
                        else:
                            logger.error(f"Ошибка TTS: {tts_resp.status}")
                            return None
                else:
                    logger.error(f"Ошибка создания голоса: {resp.status}")
                    return None
    except Exception as e:
        logger.error(f"Ошибка в ElevenLabs: {e}")
        return None

async def generate_video_with_sd(photo_path: str, topic: str) -> str:
    """Генерирует видео с помощью Stable Video Diffusion (через Replicate.com)"""
    # Для генерации видео можно использовать Replicate.com
    # Нужен будет REPLICATE_API_TOKEN в переменных окружения
    
    # Пока возвращаем заглушку
    logger.info(f"Генерация видео по теме: {topic} с фото {photo_path}")
    return None

# ========== КЛАВИАТУРА ==========
def get_main_keyboard():
    """Создает главную клавиатуру с кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✍️ Написать текст песни")],
            [KeyboardButton(text="🎤 Клонировать голос")],
            [KeyboardButton(text="🎬 Сделать клип по фото")]
        ],
        resize_keyboard=True
    )
    return keyboard

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    status_text = "✅ Все API настроены" if OPENAI_API_KEY and ELEVENLABS_API_KEY else "⚠️ Некоторые API не настроены"
    await message.answer(
        f"👋 Привет! Я музыкальный ИИ-бот с реальными функциями!\n\n"
        f"Статус: {status_text}\n\n"
        f"Я умею:\n"
        f"✍️ Писать тексты песен через ChatGPT\n"
        f"🎤 Клонировать голос через ElevenLabs\n"
        f"🎬 Создавать клипы по фото (в разработке)\n\n"
        f"Выбери действие на клавиатуре ниже:",
        reply_markup=get_main_keyboard()
    )

# ========== РЕЖИМ 1: ТЕКСТ ПЕСНИ ЧЕРЕЗ CHATGPT ==========
@dp.message(lambda message: message.text == "✍️ Написать текст песни")
async def choose_text(message: Message, state: FSMContext):
    """Пользователь выбрал написание текста"""
    await state.set_state(BotStates.waiting_for_topic)
    await message.answer(
        "📝 Отлично! Напиши тему будущей песни.\n"
        "Например: 'любовь на Марсе', 'грустный дождь', 'программист и кофе'\n\n"
        "Я сгенерирую текст через ChatGPT!"
    )

@dp.message(BotStates.waiting_for_topic)
async def generate_text(message: Message, state: FSMContext):
    """Получаем тему и генерируем текст через ChatGPT"""
    topic = message.text
    
    msg = await message.answer(f"🎵 Генерирую текст песни на тему: '{topic}' через ChatGPT...\nЭто займет несколько секунд.")
    
    # Генерируем текст через ChatGPT
    lyrics = await generate_lyrics_with_gpt(topic)
    
    await msg.delete()
    await message.answer(f"✅ Готово!\n\n{lyrics}")
    await message.answer("Что делаем дальше?", reply_markup=get_main_keyboard())
    await state.clear()

# ========== РЕЖИМ 2: КЛОНИРОВАНИЕ ГОЛОСА ЧЕРЕЗ ELEVENLABS ==========
@dp.message(lambda message: message.text == "🎤 Клонировать голос")
async def choose_voice(message: Message, state: FSMContext):
    """Пользователь выбрал клонирование голоса"""
    if not ELEVENLABS_API_KEY:
        await message.answer(
            "❌ ElevenLabs API ключ не настроен.\n"
            "Добавьте ELEVENLABS_API_KEY в переменные окружения на Render."
        )
        return
    
    await state.set_state(BotStates.waiting_for_voice_sample)
    await message.answer(
        "🎤 Отлично! Отправь мне **голосовое сообщение** (или аудиофайл) с речью человека, чей голос нужно клонировать.\n"
        "Длительность: 10-30 секунд, чистая речь без шума.\n\n"
        "После отправки я попрошу ввести текст для озвучки."
    )

@dp.message(BotStates.waiting_for_voice_sample)
async def process_voice_sample(message: Message, state: FSMContext):
    """Получаем образец голоса"""
    if message.voice or message.audio:
        # Получаем file_id
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        
        # Скачиваем файл
        audio_path = f"/tmp/sample_{uuid.uuid4().hex}.ogg"
        await download_file(file_id, audio_path)
        
        # Конвертируем в mp3 (тут нужна будет конвертация, но для простоты пропустим)
        mp3_path = f"/tmp/sample_{uuid.uuid4().hex}.mp3"
        os.rename(audio_path, mp3_path)  # временно, реально нужно конвертировать
        
        await state.update_data(voice_sample_path=mp3_path)
        await state.set_state(BotStates.waiting_for_voice_topic)
        await message.answer(
            "✅ Голос получен! Теперь напиши текст, который нужно озвучить этим голосом."
        )
    else:
        await message.answer("❌ Пожалуйста, отправь голосовое сообщение или аудиофайл.")

@dp.message(BotStates.waiting_for_voice_topic)
async def process_voice_text(message: Message, state: FSMContext):
    """Получаем текст и генерируем речь с клонированным голосом"""
    text = message.text
    data = await state.get_data()
    audio_path = data.get('voice_sample_path')
    
    if not audio_path:
        await message.answer("❌ Ошибка: не найден образец голоса. Начни заново.")
        await state.clear()
        return
    
    msg = await message.answer("🎵 Генерирую речь с клонированным голосом... Это займет 20-30 секунд.")
    
    # Клонируем голос и генерируем речь
    output_path = await clone_voice_with_elevenlabs(audio_path, text)
    
    if output_path and os.path.exists(output_path):
        # Отправляем аудио
        audio_file = FSInputFile(output_path)
        await message.answer_audio(audio_file, caption=f"✅ Голос сгенерирован!\nТекст: {text[:50]}...")
        
        # Удаляем временные файлы
        try:
            os.remove(audio_path)
            os.remove(output_path)
        except:
            pass
    else:
        await message.answer(
            "❌ Не удалось сгенерировать речь.\n"
            "Проверь API ключ ElevenLabs или попробуй другой образец голоса."
        )
    
    await msg.delete()
    await state.clear()
    await message.answer("Что делаем дальше?", reply_markup=get_main_keyboard())

# ========== РЕЖИМ 3: КЛИП ПО ФОТО (В РАЗРАБОТКЕ) ==========
@dp.message(lambda message: message.text == "🎬 Сделать клип по фото")
async def choose_photo(message: Message, state: FSMContext):
    """Пользователь выбрал создание клипа"""
    await state.set_state(BotStates.waiting_for_photo)
    await message.answer(
        "🎬 Отлично! Отправь мне фото,\n"
        "а затем напиши тему или настроение для клипа.\n\n"
        "⚠️ Функция в разработке. Пока будет демо-режим."
    )

@dp.message(BotStates.waiting_for_photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка фото и темы клипа"""
    if message.photo:
        photo = message.photo[-1]
        file_id = photo.file_id
        
        # Скачиваем фото
        photo_path = f"/tmp/photo_{uuid.uuid4().hex}.jpg"
        await download_file(file_id, photo_path)
        
        await state.update_data(photo_path=photo_path)
        await state.set_state(BotStates.waiting_for_photo_topic)
        await message.answer("✅ Фото получено! Теперь напиши тему или настроение для клипа.")
    
    elif message.text and await state.get_state() == BotStates.waiting_for_photo_topic:
        mood = message.text
        data = await state.get_data()
        photo_path = data.get('photo_path')
        
        msg = await message.answer(f"🎬 Создаю клип с настроением '{mood}'... Функция в разработке.")
        
        # Здесь будет генерация видео
        await asyncio.sleep(3)
        
        # Отправляем демо-ответ
        await message.answer_video(
            video="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4",
            caption=f"🎬 Демо-клип на тему '{mood}'\n(реальная генерация будет позже)"
        )
        
        # Удаляем временное фото
        try:
            os.remove(photo_path)
        except:
            pass
        
        await msg.delete()
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
    """Health check для Render"""
    return web.Response(text="OK", status=200)

async def handle_root(request):
    """Корневой маршрут"""
    return web.Response(text="🤖 Music Bot with Real AI is running!", status=200)

async def on_startup():
    """Действия при запуске бота"""
    try:
        await bot.set_webhook(WEBHOOK_URL)
        bot_info = await bot.me()
        logger.info(f"✅ Вебхук установлен на {WEBHOOK_URL}")
        logger.info(f"🤖 Бот @{bot_info.username} запущен с реальными AI функциями!")
        logger.info(f"OpenAI API: {'✅' if OPENAI_API_KEY else '❌'}")
        logger.info(f"ElevenLabs API: {'✅' if ELEVENLABS_API_KEY else '❌'}")
    except Exception as e:
        logger.error(f"❌ Ошибка установки вебхука: {e}")

async def on_shutdown():
    """Действия при остановке бота"""
    await bot.delete_webhook()
    logger.info("👋 Вебхук удален. Бот остановлен.")

async def main():
    """Главная функция запуска"""
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_root)
    app.on_startup.append(lambda _: on_startup())
    app.on_shutdown.append(lambda _: on_shutdown())
    
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Запуск сервера на порту {port}")
    return app

if __name__ == "__main__":
    web.run_app(main(), port=int(os.getenv("PORT", 8000)))
