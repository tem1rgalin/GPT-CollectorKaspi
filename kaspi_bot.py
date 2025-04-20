import telebot
import pytesseract
import cv2
import numpy as np
from PIL import Image
import io
import re


pytesseract.pytesseract.tesseract_cmd = r"D:\Tesseract\tesseract.exe"
TOKEN = "7591267995:AAHiDshjNlPpqbzdKfHlotYzJgw8v10_gys"
bot = telebot.TeleBot(TOKEN)

donations = {}
goal = 10500
pending_check = set()
used_receipts = set()



@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, f"Привет, {message.from_user.first_name}! Бот работает!")

@bot.message_handler(commands=['донат'])
def send_donation_info(message):
    user_id = message.from_user.id
    pending_check.add(user_id)
    bot.reply_to(message,
    "📤 Чтобы скинуть на GPT+:\n\n"
    "💳 Kaspi Gold: +7 708 24 54 513\n"
    "👤 Получатель: Динмухаммед T.\n\n"
    "После перевода отправь скриншот в этот чат 📸\n"
    "Бот сам распознает сумму и добавит в список ✅")

@bot.message_handler(commands=['скинул'])
def handle_donation(message):
    try:
        parts = message.text.split()
        amount = int(parts[1])
        user = message.from_user.username or message.from_user.first_name

        if user in donations:
            donations[user] += amount
        else:
            donations[user] = amount

        total = sum(donations.values())
        remaining = goal - total

        reply = f"✅ Принято {amount}₸ от {user}!\nСобрано: {total}₸ / {goal}₸"
        if remaining <= 0:
            reply += "\n🎯 Сбор завершён! Можно брать GPT+ 🎉"
        else:
            reply += f"\nОсталось: {remaining}₸"

        bot.reply_to(message, reply)

    except (IndexError, ValueError):
        bot.reply_to(message, "⚠️ Напиши сумму вот так: /скинул 1000")

@bot.message_handler(commands=['статус'])
def handle_status(message):
    if not donations:
        bot.reply_to(message, "Пока никто не скидывал 😢")
        return

    lines = ["💰 Состояние сбора:"]
    for user, amount in donations.items():
        lines.append(f"@{user}: {amount}₸" if user.startswith('@') else f"{user}: {amount}₸")

    total = sum(donations.values())
    remaining = goal - total

    lines.append(f"Собрано: {total}₸ / {goal}₸")
    if remaining > 0:
        lines.append(f"Осталось: {remaining}₸")
    else:
        lines.append("🟢 Цель достигнута! 🎉")
        lines.append(f"🪙 Переплата: {abs(remaining)}₸")

    bot.reply_to(message, "\n".join(lines))



@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if user_id not in pending_check:
        return
    else:
        pending_check.remove(user_id) 
    print("🔍 Начинаю обработку чека от", message.from_user.username)
    print("📸 Получено фото:", message.photo[-1].file_id)
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        image = Image.open(io.BytesIO(downloaded_file)).convert('RGB')
        open_cv_image = np.array(image)
        open_cv_image = open_cv_image[:, :, ::-1].copy()

        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)

        text = pytesseract.image_to_string(thresh, lang='rus+eng')
        print("📄 Распознанный текст:\n", text)

        # --- Проверка что это чек
        if not any(word in text.lower() for word in ['каспи', 'перевод выполнен', 'квитанция', 'kaspi']):
            bot.reply_to(message,
            "❌ Это не похоже на чек Kaspi.\n\n"
            "📸 Пожалуйста, отправь скриншот **полного чека** ещё раз.\n"
            "Убедись, что видно:\n"
            "• сумму перевода\n"
            "• дату\n"
            "• номер квитанции\n\n"
            "Если что — можешь сделать новый скрин или переслать старый чек."
            )
            pending_check.add(user_id)
            return


        # --- Извлечение номера квитанции
        receipt_match = re.search(r'№[^\d]*(\d{6,})', text)
        if receipt_match:
            receipt_number = receipt_match.group(1)
            if receipt_number in used_receipts:
                bot.reply_to(message, "⚠️ Этот чек уже был учтён ранее.")
                return
            else:
                used_receipts.add(receipt_number)
        else:
            bot.reply_to(message, "❌ Не удалось найти номер квитанции. Убедись, что чек полный.")
            return

        # --- Извлечение даты
        import datetime
        today = datetime.datetime.now().date()
        date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4}|\d{2})', text)
        if date_match:
            day, month, year = date_match.groups()
            year = int(year)
            year += 2000 if year < 100 else 0
            check_date = datetime.date(year, int(month), int(day))
            delta_days = (today - check_date).days

            if delta_days > 4 or delta_days < 0:
                bot.reply_to(message, f"⚠️ Квитанция с недопустимой датой ({check_date.strftime('%d.%m.%Y')}). Принимаются только свежие чеки.")
                return

        else:
            bot.reply_to(message, "❌ Не удалось определить дату на чеке.")
            return

        # --- Извлечение суммы
        cleaned_text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
        sum_match = re.search(r'успешно совершен\s+(\d{3,6})\s*[₸тТT]', cleaned_text, re.IGNORECASE)
        if sum_match:
            amount_str = sum_match.group(1)
            amount = int(amount_str)
        else:
            bot.reply_to(message, "❌ Не удалось распознать сумму на чеке.")
            return

        # --- Извлечение имени отправителя
       
        sender_name = "Неизвестный"

        # Ищем кандидатов на имя в формате "Фамилия И.О."
        name_candidates = re.findall(r'([А-ЯЁ][а-яё]+ [А-ЯЁ]\.[А-ЯЁ]\.?)', text)

        if name_candidates:
            # Проверяем контекст перед именем на наличие слов "отправитель" или "ot"
            for name in name_candidates:
                before_name_index = text.lower().find(name.lower())
                if before_name_index != -1:
                    context = text.lower()[:before_name_index]
                    if any(keyword in context for keyword in ["отправитель", "ot"]):
                        sender_name = name
                        break

        # Если подходящее имя не найдено, берем первое из списка кандидатов
        if sender_name == "Неизвестный" and name_candidates:
            sender_name = name_candidates[0]

        print("🔍 Имя отправителя:", sender_name)

        # --- Сохраняем донат
        username = message.from_user.username or message.from_user.first_name
        donations[username] = donations.get(username, 0) + amount

        total = sum(donations.values())
        remaining = goal - total

        reply = f"✅ Зачислено: {amount}₸ от @{username}"
        if sender_name != "Неизвестный":
            reply += f" ({sender_name})"
        reply += f"\nКвитанция: {receipt_number}\n"

        reply += f"Собрано: {total}₸ / {goal}₸\n"
        reply += "🎯 Сбор завершён! Можно брать GPT+ 🎉" if remaining <= 0 else f"Осталось: {remaining}₸"

        bot.reply_to(message, reply)

    except Exception as e:
        print("Ошибка при обработке чека:", e)
        bot.reply_to(message, "⚠️ Ошибка при обработке изображения. Попробуй ещё раз.")


print("Бот запущен...")
bot.polling()
