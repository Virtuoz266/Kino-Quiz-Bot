import logging
import json
import os
from datetime import datetime, time, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# Импортируем данные из других файлов
from config import TOKEN
from quiz_data import QUESTIONS

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
LEADERBOARD_FILE = "leaderboard.json"
LEADERBOARD_RESET_DAY = 6  # 0=Понедельник, 6=Воскресенье
LEADERBOARD_RESET_TIME = time(hour=20, minute=0)  # 20:00

# Функции для работы с таблицей лидеров
def load_leaderboard():
    """Загружает таблицу лидеров из файла"""
    try:
        if os.path.exists(LEADERBOARD_FILE):
            with open(LEADERBOARD_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        logger.error(f"Ошибка при загрузке таблицы лидеров: {e}")
        return {}

def save_leaderboard(data):
    """Сохраняет таблицу лидеров в файл"""
    try:
        with open(LEADERBOARD_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Таблица лидеров сохранена")
    except Exception as e:
        logger.error(f"Ошибка при сохранении таблицы лидеров: {e}")

def update_leaderboard(user_id, username, score, total_questions):
    """Обновляет таблицу лидеров для пользователя"""
    leaderboard = load_leaderboard()
    
    # Преобразуем user_id в строку для JSON
    user_id_str = str(user_id)
    
    # Рассчитываем процент правильных ответов
    percentage = (score / total_questions) * 100
    
    # Проверяем, есть ли уже запись о пользователе
    if user_id_str in leaderboard:
        # Обновляем только если новый результат лучше
        old_score = leaderboard[user_id_str]["score"]
        old_percentage = leaderboard[user_id_str]["percentage"]
        
        if score > old_score or (score == old_score and percentage > old_percentage):
            leaderboard[user_id_str].update({
                "username": username,
                "score": score,
                "total_questions": total_questions,
                "percentage": percentage,
                "last_played": datetime.now().isoformat(),
                "games_played": leaderboard[user_id_str].get("games_played", 0) + 1
            })
    else:
        # Создаем новую запись
        leaderboard[user_id_str] = {
            "username": username,
            "score": score,
            "total_questions": total_questions,
            "percentage": percentage,
            "last_played": datetime.now().isoformat(),
            "games_played": 1
        }
    
    # Сохраняем обновленную таблицу
    save_leaderboard(leaderboard)
    return leaderboard

def format_leaderboard_message(leaderboard, top_n=10):
    """Форматирует таблицу лидеров для отображения"""
    if not leaderboard:
        return "🏆 Таблица лидеров пуста. Будьте первым, кто сыграет в викторину!\n\nИспользуйте /quiz чтобы начать."
    
    # Сортируем пользователей по убыванию счета, затем по проценту
    sorted_players = sorted(
        leaderboard.items(),
        key=lambda x: (x[1]["score"], x[1]["percentage"]),
        reverse=True
    )[:top_n]
    
    # Формируем сообщение
    message_lines = ["🏆 **ТАБЛИЦА ЛИДЕРОВ** 🏆\n"]
    
    # Определяем эмодзи для мест
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, data) in enumerate(sorted_players):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        username = data["username"]
        score = data["score"]
        total = data["total_questions"]
        percentage = data["percentage"]
        games_played = data.get("games_played", 1)
        
        # Сокращаем длинные имена
        if len(username) > 15:
            username = username[:12] + "..."
        
        message_lines.append(
            f"{medal} **{username}** - {score}/{total} ({percentage:.0f}%) "
            f"🎮 {games_played} игр"
        )
    
    # Добавляем статистику
    total_players = len(leaderboard)
    avg_score = sum(data["score"] for data in leaderboard.values()) / total_players
    avg_percentage = sum(data["percentage"] for data in leaderboard.values()) / total_players
    
    message_lines.extend([
        f"\n📊 **Статистика:**",
        f"• Всего игроков: {total_players}",
        f"• Средний счет: {avg_score:.1f}/{len(QUESTIONS)}",
        f"• Средний процент: {avg_percentage:.1f}%",
        f"\n🎯 Ваш лучший результат может быть здесь!",
        f"Используйте /quiz чтобы попробовать снова!"
    ])
    
    return "\n".join(message_lines)

# Функция сброса таблицы лидеров
async def reset_leaderboard(context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает таблицу лидеров"""
    try:
        # Получаем текущую таблицу лидеров перед сбросом
        old_leaderboard = load_leaderboard()
        
        if old_leaderboard:
            # Сохраняем бэкап старой таблицы лидеров
            backup_file = f"leaderboard_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(old_leaderboard, f, ensure_ascii=False, indent=2)
            logger.info(f"Создан бэкап таблицы лидеров: {backup_file}")
        
        # Сбрасываем таблицу лидеров
        save_leaderboard({})
        logger.info("Таблица лидеров сброшена (еженедельный сброс)")
        
        # Отправляем сообщение об обнулении
        reset_message = (
            "🔄 **ТАБЛИЦА ЛИДЕРОВ ОБНОВЛЕНА!**\n\n"
            "🎬 Рейтинг обнулен! Начинается новая игровая неделя!\n\n"
            "🏆 **Призы недели:**\n"
            "• 1 место: Звание 'Киногений недели' 🥇\n"
            "• 2 место: Почетное звание 'Киноман' 🥈\n"
            "• 3 место: Звание 'Знаток кино' 🥉\n\n"
            "🎯 Используйте /quiz, чтобы начать борьбу за первое место!\n"
            "📊 Таблица лидеров: /top"
        )
        
        # Отправляем сообщение в чат (если указан chat_id)
        if hasattr(context.job, 'chat_id') and context.job.chat_id:
            try:
                await context.bot.send_message(
                    chat_id=context.job.chat_id,
                    text=reset_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение о сбросе: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка при сбросе таблицы лидеров: {e}")

def get_next_reset_time():
    """Возвращает время следующего сброса таблицы лидеров"""
    now = datetime.now()
    
    # Вычисляем следующий день сброса (воскресенье)
    days_ahead = LEADERBOARD_RESET_DAY - now.weekday()
    if days_ahead <= 0:  # Если сегодня уже воскресенье или прошло
        days_ahead += 7  # Следующее воскресенье
    
    # Вычисляем дату следующего сброса
    next_reset_date = now.date() + timedelta(days=days_ahead)
    
    # Комбинируем дату и время
    return datetime.combine(next_reset_date, LEADERBOARD_RESET_TIME)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start"""
    # Получаем время следующего сброса
    next_reset = get_next_reset_time()
    
    await update.message.reply_text(
        "🎬 **Добро пожаловать в увлекательную викторину о кино!**\n\n"
        "🎯 **Основные команды:**\n"
        "• /quiz - Начать новую викторину (10 вопросов)\n"
        "• /top - Показать таблицу лидеров\n"
        "• /mystats - Показать вашу статистику\n"
        "• /nextreset - Время следующего сброса рейтинга\n"
        "• /help - Справка по всем командам\n\n"
        "🔄 **Система рейтинга:**\n"
        "• Таблица лидеров обновляется еженедельно\n"
        "• Следующий сброс: " + next_reset.strftime("%d.%m.%Y в %H:%M") + "\n"
        "• Сохраняются только лучшие результаты\n\n"
        "🎮 **Удачи в викторине!**"
    )

# Функция для отправки вопроса
async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question_index: int) -> None:
    """Отправляет вопрос по указанному индексу"""
    question_data = QUESTIONS[question_index]
    
    # Создаем клавиатуру с вариантами ответов
    keyboard = []
    for i, option in enumerate(question_data["options"]):
        keyboard.append([InlineKeyboardButton(f"{i+1}. {option}", callback_data=str(i))])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем вопрос с клавиатурой
    await update.message.reply_text(
        f"🎥 **Вопрос {question_index + 1}/{len(QUESTIONS)}**\n\n"
        f"❓ {question_data['question']}",
        reply_markup=reply_markup
    )

# Обработчик команды /quiz
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает викторину"""
    
    # Инициализируем данные пользователя
    context.user_data['current_question'] = 0
    context.user_data['score'] = 0
    
    # Отправляем первый вопрос
    await send_question(update, context, 0)
    
    logger.info(f"Пользователь {update.effective_user.id} начал викторину")

async def send_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question_index: int) -> None:
    """Отправляет следующий вопрос"""
    question_data = QUESTIONS[question_index]
    
    # Создаем клавиатуру с вариантами ответов
    keyboard = []
    for i, option in enumerate(question_data["options"]):
        keyboard.append([InlineKeyboardButton(f"{i+1}. {option}", callback_data=str(i))])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем следующий вопрос
    await context.bot.send_message(
        chat_id=update.callback_query.message.chat_id,
        text=f"🎥 **Вопрос {question_index + 1}/{len(QUESTIONS)}**\n\n"
             f"❓ {question_data['question']}",
        reply_markup=reply_markup
    )

# Обработчик нажатий на кнопки с вариантами ответов
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выбор варианта ответа"""
    query = update.callback_query
    
    # Подтверждаем получение callback
    await query.answer()
    
    # Получаем выбранный вариант
    selected_option = int(query.data)
    
    # Получаем текущий вопрос из user_data
    current_question_index = context.user_data.get('current_question', 0)
    question_data = QUESTIONS[current_question_index]
    
    # Проверяем, правильный ли ответ
    is_correct = selected_option == question_data["correct_option"]
    
    # Обновляем счет, если ответ правильный
    if is_correct:
        context.user_data['score'] = context.user_data.get('score', 0) + 1
    
    # Получаем интересный факт
    fun_fact = question_data.get('fun_fact', '')
    
    # Формируем сообщение с результатом
    if is_correct:
        result_text = "✅ **Верно!** Отличный ответ!"
    else:
        correct_answer = question_data["options"][question_data["correct_option"]]
        result_text = f"❌ **Неверно!**\n\n📌 Правильный ответ: *{correct_answer}*"
    
    # Добавляем интересный факт
    if fun_fact:
        result_text += f"\n\n📚 **Интересный факт:**\n{fun_fact}"
    
    # Добавляем текущий счет
    result_text += f"\n\n📊 **Ваш счет:** {context.user_data['score']}/{current_question_index + 1}"
    
    # Редактируем сообщение с вопросом, показывая результат
    await query.edit_message_text(
        text=result_text,
        parse_mode='Markdown'
    )
    
    # Увеличиваем номер текущего вопроса
    next_question_index = current_question_index + 1
    context.user_data['current_question'] = next_question_index
    
    # Ждем 2 секунды перед следующим действием
    import asyncio
    await asyncio.sleep(2)
    
    # Проверяем, есть ли еще вопросы
    if next_question_index < len(QUESTIONS):
        # Отправляем следующий вопрос
        await send_next_question(update, context, next_question_index)
    else:
        # Викторина окончена
        await show_final_results(update, context)

async def show_final_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает финальные результаты викторины и обновляет таблицу лидеров"""
    score = context.user_data.get('score', 0)
    total_questions = len(QUESTIONS)
    user = update.callback_query.from_user
    
    # Обновляем таблицу лидеров
    update_leaderboard(
        user_id=user.id,
        username=user.first_name or user.username or f"Игрок_{user.id}",
        score=score,
        total_questions=total_questions
    )
    
    # Определяем оценку
    percentage = (score / total_questions) * 100
    
    if percentage == 100:
        rating = "🏆 **ПОТРЯСАЮЩЕ!** Вы настоящий киноэксперт! 🎬"
        emoji = "🌟"
    elif percentage >= 80:
        rating = "🎖 **ОТЛИЧНО!** Вы отлично разбираетесь в кино! 👏"
        emoji = "💫"
    elif percentage >= 60:
        rating = "👍 **ХОРОШО!** Вы знаете много о кино! 😊"
        emoji = "✨"
    elif percentage >= 40:
        rating = "😐 **НЕПЛОХО!** Есть что посмотреть и узнать! 📚"
        emoji = "📖"
    else:
        rating = "🎞️ **ВРЕМЯ ПЕРЕСМОТРЕТЬ КЛАССИКУ!** 🍿"
        emoji = "🍿"
    
    # Получаем время следующего сброса
    next_reset = get_next_reset_time()
    
    # Формируем сообщение с результатами
    results_text = (
        f"🏁 **ВИКТОРИНА ЗАВЕРШЕНА!**\n\n"
        f"{emoji} {rating}\n\n"
        f"📊 **Ваш результат:** *{score} из {total_questions}*\n"
        f"📈 **Процент правильных ответов:** *{percentage:.0f}%*\n\n"
        f"🏆 **Ваш результат сохранен в таблице лидеров!**\n"
        f"Таблица обнуляется: {next_reset.strftime('%d.%m.%Y в %H:%M')}\n\n"
        f"📊 Ваша статистика: /mystats\n"
        f"🏆 Текущий рейтинг: /top\n"
        f"⏰ Следующий сброс: /nextreset\n\n"
        f"🔄 Хотите улучшить результат? /quiz"
    )
    
    await context.bot.send_message(
        chat_id=update.callback_query.message.chat_id,
        text=results_text,
        parse_mode='Markdown'
    )
    
    logger.info(f"Пользователь {user.id} завершил викторину с результатом {score}/{total_questions}")

# Обработчик команды /top
async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает таблицу лидеров"""
    leaderboard = load_leaderboard()
    message = format_leaderboard_message(leaderboard, top_n=10)
    
    # Добавляем информацию о следующем сбросе
    next_reset = get_next_reset_time()
    time_until_reset = next_reset - datetime.now()
    days_until_reset = time_until_reset.days
    
    reset_info = f"\n\n🔄 **Следующий сброс таблицы:** через {days_until_reset} дней в 20:00"
    message += reset_info
    
    await update.message.reply_text(
        text=message,
        parse_mode='Markdown'
    )

# Обработчик команды /nextreset
async def nextreset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает время следующего сброса таблицы лидеров"""
    next_reset = get_next_reset_time()
    time_until_reset = next_reset - datetime.now()
    
    # Преобразуем разницу во времени в читаемый формат
    days = time_until_reset.days
    hours = time_until_reset.seconds // 3600
    minutes = (time_until_reset.seconds % 3600) // 60
    
    # Формируем читаемое время до сброса
    time_parts = []
    if days > 0:
        time_parts.append(f"{days} {'день' if days == 1 else 'дня' if 2 <= days <= 4 else 'дней'}")
    if hours > 0:
        time_parts.append(f"{hours} {'час' if hours == 1 else 'часа' if 2 <= hours <= 4 else 'часов'}")
    if minutes > 0:
        time_parts.append(f"{minutes} {'минуту' if minutes == 1 else 'минуты' if 2 <= minutes <= 4 else 'минут'}")
    
    time_until_str = ", ".join(time_parts)
    
    # Загружаем текущую таблицу лидеров для статистики
    leaderboard = load_leaderboard()
    total_players = len(leaderboard)
    
    # Формируем сообщение
    message = (
        f"⏰ **СЛЕДУЮЩИЙ СБРОС ТАБЛИЦЫ ЛИДЕРОВ**\n\n"
        f"📅 Дата: {next_reset.strftime('%d.%m.%Y')}\n"
        f"🕐 Время: {next_reset.strftime('%H:%M')}\n"
        f"⏳ До сброса: {time_until_str}\n\n"
        f"📊 **Текущая статистика:**\n"
        f"• Активных игроков: {total_players}\n"
        f"• Всего вопросов: {len(QUESTIONS)}\n"
        f"• Частота сброса: раз в неделю (воскресенье)\n\n"
        f"🏆 Успейте улучшить свой результат!\n"
        f"🎮 Сыграть: /quiz\n"
        f"📊 Текущий рейтинг: /top"
    )
    
    await update.message.reply_text(
        text=message,
        parse_mode='Markdown'
    )

# Обработчик команды /mystats
async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает статистику текущего пользователя"""
    user = update.effective_user
    leaderboard = load_leaderboard()
    user_id_str = str(user.id)
    
    if user_id_str in leaderboard:
        data = leaderboard[user_id_str]
        
        # Находим место пользователя в рейтинге
        sorted_players = sorted(
            leaderboard.items(),
            key=lambda x: (x[1]["score"], x[1]["percentage"]),
            reverse=True
        )
        
        position = next(
            (i + 1 for i, (uid, _) in enumerate(sorted_players) if uid == user_id_str),
            None
        )
        
        # Преобразуем дату последней игры
        last_played = datetime.fromisoformat(data["last_played"])
        last_played_str = last_played.strftime("%d.%m.%Y %H:%M")
        
        # Получаем время следующего сброса
        next_reset = get_next_reset_time()
        
        stats_text = (
            f"📊 **ВАША СТАТИСТИКА**\n\n"
            f"👤 **Игрок:** {data['username']}\n"
            f"🏆 **Лучший результат:** {data['score']}/{data['total_questions']}\n"
            f"📈 **Процент правильных:** {data['percentage']:.1f}%\n"
            f"🥇 **Место в рейтинге:** {position}\n"
            f"🎮 **Сыграно игр:** {data.get('games_played', 1)}\n"
            f"🕐 **Последняя игра:** {last_played_str}\n\n"
        )
        
        # Добавляем рекомендацию
        if data["percentage"] == 100:
            stats_text += "🌟 Вы - киногений! Продолжайте в том же духе!"
        elif data["percentage"] >= 80:
            stats_text += "💫 Отличный результат! Почти идеально!"
        elif data["percentage"] >= 60:
            stats_text += "✨ Хорошие знания кино! Можно еще лучше!"
        else:
            stats_text += "📚 Есть куда расти! Пробуйте снова!"
            
        stats_text += f"\n\n🔄 **Следующий сброс рейтинга:**\n{next_reset.strftime('%d.%m.%Y в %H:%M')}"
        stats_text += "\n\n🎮 Сыграть еще раз: /quiz"
        
    else:
        # Получаем время следующего сброса для новых пользователей
        next_reset = get_next_reset_time()
        
        stats_text = (
            "📊 **У вас еще нет статистики!**\n\n"
            "Вы еще не играли в викторину.\n"
            "🎮 Используйте команду /quiz, чтобы начать игру и "
            "появиться в таблице лидеров!\n\n"
            f"🔄 **Следующий сброс рейтинга:**\n{next_reset.strftime('%d.%m.%Y в %H:%M')}"
        )
    
    await update.message.reply_text(
        text=stats_text,
        parse_mode='Markdown'
    )

# Обработчик команды /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет справку по командам"""
    # Получаем время следующего сброса
    next_reset = get_next_reset_time()
    
    help_text = (
        "📖 **КОМАНДЫ БОТА-ВИКТОРИНЫ**\n\n"
        "🎮 **Игра:**\n"
        "• /quiz - Начать новую викторину (10 вопросов)\n\n"
        "🏆 **Рейтинг и статистика:**\n"
        "• /top - Показать таблицу лидеров\n"
        "• /mystats - Ваша персональная статистика\n"
        "• /nextreset - Время следующего сброса рейтинга\n\n"
        "ℹ️ **Информация:**\n"
        "• /start - Главное меню\n"
        "• /help - Эта справка\n\n"
        "🔄 **Система рейтинга:**\n"
        "• Таблица лидеров обновляется еженедельно\n"
        "• Следующий сброс: " + next_reset.strftime("%d.%m.%Y в %H:%M") + "\n"
        "• Сохраняются только лучшие результаты\n\n"
        "🎯 **Как играть:**\n"
        "1. Используйте /quiz для начала\n"
        "2. Отвечайте на вопросы, выбирая варианты\n"
        "3. Узнавайте интересные факты о кино\n"
        "4. Соревнуйтесь с другими игроками!\n\n"
        "🎬 **Удачи в викторине о кино!**"
    )
    await update.message.reply_text(help_text)

def main() -> None:
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("mystats", mystats_command))
    application.add_handler(CommandHandler("nextreset", nextreset_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Регистрируем обработчик callback-запросов (нажатий на кнопки)
    application.add_handler(CallbackQueryHandler(handle_answer))
    
    # Проверяем наличие файла таблицы лидеров
    if not os.path.exists(LEADERBOARD_FILE):
        logger.info("Создаю новую таблицу лидеров...")
        save_leaderboard({})
    
    # Настройка еженедельного сброса таблицы лидеров
    # ВАЖНО: Для работы уведомлений о сбросе укажите chat_id вашего чата
    # Замените None на ID чата, куда бот будет отправлять уведомления
    NOTIFICATION_CHAT_ID = None  # Пример: 123456789
    
    # Планируем еженедельный сброс таблицы лидеров (по воскресеньям в 20:00)
    if NOTIFICATION_CHAT_ID:
        application.job_queue.run_daily(
            callback=reset_leaderboard,
            time=LEADERBOARD_RESET_TIME,
            days=(LEADERBOARD_RESET_DAY,),  # Воскресенье
            chat_id=NOTIFICATION_CHAT_ID,
            name="weekly_leaderboard_reset"
        )
        logger.info(f"Запланирован еженедельный сброс таблицы лидеров на воскресенье в {LEADERBOARD_RESET_TIME.strftime('%H:%M')}")
        logger.info(f"Уведомления о сбросе будут отправляться в чат: {NOTIFICATION_CHAT_ID}")
    else:
        logger.warning("NOTIFICATION_CHAT_ID не указан. Уведомления о сбросе таблицы лидеров отключены.")
        logger.info("Чтобы включить уведомления, замените NOTIFICATION_CHAT_ID = None на ID вашего чата")
    
    # Запускаем бота
    logger.info("Бот запущен...")
    print("=" * 50)
    print("🎬 Бот-викторина о кино успешно запущен!")
    print(f"📚 Загружено вопросов: {len(QUESTIONS)}")
    print(f"🏆 Таблица лидеров: {LEADERBOARD_FILE}")
    print(f"🔄 Еженедельный сброс: Воскресенье в 20:00")
    if NOTIFICATION_CHAT_ID:
        print(f"🔔 Уведомления о сбросе: ВКЛЮЧЕНЫ (чат: {NOTIFICATION_CHAT_ID})")
    else:
        print(f"🔔 Уведомления о сбросе: ВЫКЛЮЧЕНЫ")
    print("🤖 Ожидание команд...")
    print("=" * 50)
    
    application.run_polling()

if __name__ == '__main__':
    main()