import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import telegram.error

TOKEN = "8130787520:AAHulnzqWno0OlDqvlpdt6fjLqno8VFnBoc"
ADMIN_ID = 8537120818
FARM_COOLDOWN = 4
COMPENSATION_AMOUNT = 15

# ⚡️ ВАЖНО! Используем ТВОЙ файл с 76 игроками
DB_FILENAME = "my_precious_data.json"

LEVELS = [
    {"level": 1, "name": "👶 Рекрут", "min_coins": 0, "max_coins": 100},
    {"level": 2, "name": "🛡️ Страж", "min_coins": 101, "max_coins": 200},
    {"level": 3, "name": "⚔️ Рыцарь", "min_coins": 201, "max_coins": 300},
    {"level": 4, "name": "👑 Титян", "min_coins": 301, "max_coins": 400},
    {"level": 5, "name": "🔥 Божество", "min_coins": 401, "max_coins": 1000000}
]

SHOP_ITEMS = {
    1: {"name": "🔔 Сигна от Kme_Dota", "price": 50, "description": "Сигна от Kme_Dota", "exchangeable": True},
    2: {"name": "👥 Сигна от Лсной братвы", "price": 100, "description": "Сигна от Лсной братвы", "exchangeable": True},
    3: {"name": "👑 Модер в чате", "price": 150, "description": "Стать модератором в чате", "exchangeable": True},
    4: {"name": "🎮 Модер на твиче", "price": 200, "description": "Стать модератором на твиче", "exchangeable": True},
    5: {"name": "🎵 Трек про тебя", "price": 300, "description": "Заказать трек про себя", "exchangeable": True},
    6: {"name": "⚔️ Dota+", "price": 400, "description": "Получить Dota+ на месяц", "exchangeable": True}
}

class Database:
    def __init__(self, filename):
        self.filename = filename
        print(f"📁 Загружаем базу: {self.filename}")
        self.data = self.load_data()
        print(f"👥 Загружено игроков: {len(self.data)}")
    
    def load_data(self):
        if not os.path.exists(self.filename):
            print(f"❌ ФАЙЛ {self.filename} НЕ НАЙДЕН!")
            print("📁 Переименуй свой файл в my_precious_data.json через файловый менеджер")
            return {}
        
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
            if not content:
                print("⚠️ Файл базы пустой")
                return {}
            
            data = json.loads(content)
            
            if not isinstance(data, dict):
                print("❌ Неверный формат базы данных")
                return {}
            
            # Конвертируем старые данные
            for user_id, user_data in data.items():
                if 'last_active' not in user_data:
                    user_data['last_active'] = datetime.now().isoformat()
                if 'admin_gifted' not in user_data:
                    user_data['admin_gifted'] = 0
            
            print(f"✅ Успешно загружено {len(data)} пользователей")
            return data
            
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка JSON: {e}")
            return {}
        except Exception as e:
            print(f"❌ Ошибка загрузки: {e}")
            return {}
    
    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            print(f"💾 База сохранена ({len(self.data)} игроков)")
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.data:
            # СОЗДАЕМ НОВОГО ПОЛЬЗОВАТЕЛЯ
            self.data[user_id] = {
                'coins': 0,
                'last_farm': None,
                'username': '',
                'display_name': '',
                'inventory': [],
                'total_farmed': 0,
                'farm_count': 0,
                'admin_gifted': 0,
                'last_active': datetime.now().isoformat()
            }
            print(f"👤 Новый пользователь {user_id} добавлен в БД")
            self.save_data()
        return self.data[user_id]
    
    def update_user(self, user_id, username="", display_name=""):
        user = self.get_user(user_id)
        if username:
            user['username'] = username
        if display_name:
            user['display_name'] = display_name
        user['last_active'] = datetime.now().isoformat()
        self.save_data()
    
    def can_farm(self, user_id):
        user = self.get_user(user_id)
        user['last_active'] = datetime.now().isoformat()
        
        if not user['last_farm']:
            return True, "✅ Можно фармить!"
        
        last = datetime.fromisoformat(user['last_farm'])
        now = datetime.now()
        
        if now - last >= timedelta(hours=FARM_COOLDOWN):
            return True, "✅ Можно фармить!"
        else:
            wait = (last + timedelta(hours=FARM_COOLDOWN)) - now
            hours = wait.seconds // 3600
            minutes = (wait.seconds % 3600) // 60
            return False, f"⏳ Ждите {hours:02d}:{minutes:02d}"
    
    def add_coins(self, user_id, amount, from_farm=True, from_admin=False):
        user = self.get_user(user_id)
        user['coins'] += amount
        if from_farm:
            user['total_farmed'] += amount
            user['farm_count'] += 1
            user['last_farm'] = datetime.now().isoformat()
        if from_admin:
            user['admin_gifted'] += amount
        user['last_active'] = datetime.now().isoformat()
        self.save_data()
        return user['coins']
    
    def buy_item(self, user_id, item_id):
        user = self.get_user(user_id)
        user['last_active'] = datetime.now().isoformat()
        
        if item_id not in SHOP_ITEMS:
            return False, "❌ Такого товара нет!"
        
        item = SHOP_ITEMS[item_id]
        if user['coins'] < item['price']:
            return False, f"❌ Недостаточно коинов! Нужно {item['price']}, есть {user['coins']}"
        
        user['coins'] -= item['price']
        user['inventory'].append({
            'id': item_id,
            'name': item['name'],
            'price': item['price'],
            'bought_at': datetime.now().isoformat(),
            'exchanged': False
        })
        self.save_data()
        return True, f"✅ Куплено: {item['name']}"
    
    def exchange_item(self, user_id, item_index):
        user = self.get_user(user_id)
        user['last_active'] = datetime.now().isoformat()
        
        if item_index >= len(user['inventory']):
            return False, "❌ Такого предмета нет!"
        
        item = user['inventory'][item_index]
        if item.get('exchanged', False):
            return False, "❌ Уже обменян!"
        
        user['inventory'][item_index]['exchanged'] = True
        user['inventory'][item_index]['exchanged_at'] = datetime.now().isoformat()
        self.save_data()
        return True, item
    
    def remove_item(self, user_id, item_index):
        user = self.get_user(user_id)
        if item_index >= len(user['inventory']):
            return False, "❌ Такого предмета нет!"
        
        removed_item = user['inventory'].pop(item_index)
        self.save_data()
        return True, removed_item
    
    def add_compensation_to_all(self, amount):
        for user_id in self.data:
            user = self.get_user(user_id)
            user['coins'] += amount
            user['last_active'] = datetime.now().isoformat()
        self.save_data()
        return len(self.data)
    
    def get_user_level(self, total_coins):
        for level in LEVELS:
            if level["min_coins"] <= total_coins <= level["max_coins"]:
                return level
        return LEVELS[-1]
    
    def search_users(self, search_term):
        results = []
        search_term = search_term.lower()
        
        for user_id, user_data in self.data.items():
            username = user_data.get('username', '').lower()
            display_name = user_data.get('display_name', '').lower()
            
            if search_term in username or search_term in display_name:
                results.append((user_id, user_data))
        
        return results

# ========== СОЗДАЕМ БАЗУ ==========
print("=" * 50)
print("🤖 KMEbot запускается...")

# Проверяем наличие ТВОЕГО файла с 76 игроками
if os.path.exists(DB_FILENAME):
    print(f"✅ Найден файл: {DB_FILENAME}")
    db = Database(DB_FILENAME)
    print(f"👥 Всего игроков в базе: {len(db.data)}")
else:
    print(f"❌ ФАЙЛ {DB_FILENAME} НЕ НАЙДЕН!")
    print("📁 В файловом менеджере BotHost переименуй свой файл в my_precious_data.json")
    print("🚫 Бот не может работать без базы данных!")
    exit(1)

print("=" * 50)

# ========== ФУНКЦИИ БОТА ==========
async def send_exchange_notification(context, user_id, item):
    user_data = db.get_user(user_id)
    
    user_name = f"@{user_data.get('username', '')}" if user_data.get('username') else f"ID:{user_id}"
    display_name = user_data.get('display_name', 'Неизвестно')
    
    message = (
        f"🔔 НОВЫЙ ОБМЕН!\n\n"
        f"🎁 {item['name']}\n"
        f"💰 {item['price']} коинов\n"
        f"👤 {user_name} ({display_name})\n"
        f"🆔 {user_id}\n\n"
        f"✅ После выполнения:\n"
        f"/removeitem {user_id} {len(user_data['inventory'])-1}"
    )
    
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=message)
    except Exception as e:
        print(f"❌ Ошибка уведомления: {e}")

async def send_party_announcement(context, user_id, mmr):
    try:
        user = await context.bot.get_chat(user_id)
    except:
        user = None
    
    user_data = db.get_user(user_id)
    level = db.get_user_level(user_data['total_farmed'])
    
    message = (
        f"🔍 <b>НОВЫЙ ИГРОК ИЩЕТ ТИМУ!</b>\n\n"
        f"👤 <b>Игрок:</b> {user.first_name if user else 'Неизвестно'}\n"
    )
    
    if user and user.username:
        message += f"📱 <b>Telegram:</b> @{user.username}\n"
    
    message += (
        f"📊 <b>MMR:</b> <code>{mmr}</code>\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
    )
    
    if user_data.get('display_name'):
        message += f"📝 <b>Имя в боте:</b> {user_data['display_name']}\n"
    
    message += (
        f"💰 <b>Баланс:</b> {user_data['coins']} коинов\n"
        f"🏆 <b>Уровень:</b> {level['name']}\n\n"
    )
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"❌ Ошибка объявления: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id, user.username, user.full_name)
    user_data = db.get_user(user.id)
    level = db.get_user_level(user_data['total_farmed'])
    
    message = (
        f"🎮 <b>Добро пожаловать, {user.first_name}!</b>\n\n"
        f"💰 <b>Баланс:</b> {user_data['coins']} коинов\n"
        f"🏆 <b>Уровень:</b> {level['name']}\n\n"
        "📋 <b>Основные команды:</b>\n"
        "/farm - Фармить коины\n"
        "/balance - Баланс\n"
        "/level - Уровень\n"
        "/shop - Магазин (только в ЛС)\n"
        "/inventory - Инвентарь\n"
        "/party [MMR] - Найти тиму\n"
        "/profile - Профиль\n"
        "/users - Поиск игроков\n"
        "/help - Помощь"
    )
    
    try:
        await update.message.reply_text(message, parse_mode='HTML')
    except telegram.error.TimedOut:
        print(f"⚠️ Таймаут start для {user.id}")

async def farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    can_farm, msg = db.can_farm(user.id)
    
    if not can_farm:
        await update.message.reply_text(f"❌ {msg}")
        return
    
    coins = random.randint(1, 2)
    new_balance = db.add_coins(user.id, coins)
    
    farm_messages = [
        f"💰 Нашли {coins} коинов!",
        f"🎰 +{coins} коинов",
        f"⚡ Фарм: {coins} коинов",
        f"💎 Добыто: {coins} коинов",
        f"🎯 Точно! {coins} коинов"
    ]
    
    message = (
        f"✅ {random.choice(farm_messages)}\n\n"
        f"💰 <b>Получено:</b> {coins} коинов\n"
        f"🏦 <b>Баланс:</b> {new_balance} коинов\n"
        f"⏰ <b>Следующий:</b> через {FARM_COOLDOWN}ч"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    level = db.get_user_level(user_data['total_farmed'])
    
    message = (
        f"👤 <b>{user.first_name}</b>\n\n"
        f"💳 <b>Коинсы:</b> {user_data['coins']}\n"
        f"🏆 <b>Заработано:</b> {user_data['total_farmed']}\n"
        f"📈 <b>Уровень:</b> {level['name']}\n"
        f"🔄 <b>Фармов:</b> {user_data['farm_count']}\n"
        f"🎁 <b>Подарков:</b> {user_data['admin_gifted']}"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    current_level = db.get_user_level(user_data['total_farmed'])
    
    next_level = None
    for i, level in enumerate(LEVELS):
        if level["min_coins"] <= user_data['total_farmed'] <= level["max_coins"]:
            if i + 1 < len(LEVELS):
                next_level = LEVELS[i + 1]
            break
    
    message = (
        f"👤 <b>{user.first_name}</b>\n"
        f"🎯 <b>Уровень:</b> {current_level['name']}\n"
        f"💰 <b>Заработано:</b> {user_data['total_farmed']} коинов\n"
    )
    
    if next_level:
        need = next_level['min_coins'] - user_data['total_farmed']
        message += f"📈 <b>До след.:</b> {need} коинов"
    
    await update.message.reply_text(message, parse_mode='HTML')

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        await update.message.reply_text(
            "🛍️ <b>Магазин доступен только в личных сообщениях с ботом!</b>\n\n"
            "👉 Напишите мне в ЛС",
            parse_mode='HTML'
        )
        return
    
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    
    message = f"🏪 <b>МАГАЗИН ПРЕДМЕТОВ</b>\n\n"
    
    for item_id, item in SHOP_ITEMS.items():
        message += (
            f"{item_id}. <b>{item['name']}</b>\n"
            f"💰 {item['price']} коинов\n"
            f"📝 {item['description']}\n"
            f"🛒 <code>/buy_{item_id}</code>\n\n"
        )
    
    message += f"💵 <b>Ваш баланс:</b> {user_data['coins']} коинов"
    
    await update.message.reply_text(message, parse_mode='HTML')

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int):
    user = update.effective_user
    db.update_user(user.id)
    success, result = db.buy_item(user.id, item_id)
    user_data = db.get_user(user.id)
    
    if success:
        message = (
            f"✅ <b>ПОКУПКА УСПЕШНА!</b>\n\n"
            f"🎁 <b>Предмет:</b> {result}\n"
            f"💳 <b>Новый баланс:</b> {user_data['coins']} коинов\n\n"
            f"📦 Предмет в инвентаре\n"
            f"🔧 /inventory для обмена"
        )
        await update.message.reply_text(message, parse_mode='HTML')
    else:
        await update.message.reply_text(f"❌ {result}")

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    
    if not user_data['inventory']:
        await update.message.reply_text(
            f"📦 <b>ИНВЕНТАРЬ ПУСТ</b>\n\n🛍️ /shop",
            parse_mode='HTML'
        )
        return
    
    keyboard = []
    for i, item in enumerate(user_data['inventory']):
        btn_text = f"{i+1}. {item['name']}"
        if item.get('exchanged', False):
            btn_text += " ✅"
            callback = f"view_{i}"
        else:
            btn_text += " 🔄"
            callback = f"exchange_{i}"
        
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback)])
    
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="close")])
    
    message = (
        f"🎒 <b>ВАШ ИНВЕНТАРЬ</b>\n\n"
        f"👤 <b>Игрок:</b> {user.first_name}\n"
        f"📊 <b>Предметов:</b> {len(user_data['inventory'])}\n\n"
        f"💡 Нажмите на предмет для обмена"
    )
    
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def party(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    
    if not context.args:
        await update.message.reply_text(
            f"🎯 <b>ПОИСК ТИМЫ ДЛЯ DOTA 2</b>\n\n"
            f"📝 <b>Использование:</b>\n"
            f"<code>/party [ваш MMR]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/party 4500</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        mmr = int(context.args[0])
        await send_party_announcement(context, user.id, mmr)
        
        await update.message.reply_text(
            f"✅ <b>ЗАЯВКА ПРИНЯТА!</b>\n\n"
            f"👤 <b>Игрок:</b> {user.first_name}\n"
            f"📊 <b>MMR:</b> {mmr}\n\n"
            f"📨 Админ получил вашу заявку\n"
            f"👥 Скоро поможем найти тиму!",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Укажите число MMR")

async def write(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    
    if len(context.args) < 2:
        await update.message.reply_text(
            f"📨 <b>НАПИСАТЬ ИГРОКУ</b>\n\n"
            f"📝 <b>Использование:</b>\n"
            f"<code>/write [ID_игрока] [сообщение]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/write 6443845944 Привет!</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        target_id = int(context.args[0])
        message_text = " ".join(context.args[1:])
        
        receiver_message = (
            f"💌 <b>ВАМ ПРИШЛО СООБЩЕНИЕ!</b>\n\n"
            f"👤 <b>От:</b> {user.first_name}\n"
        )
        
        if user.username:
            receiver_message += f"📱 <b>Telegram:</b> @{user.username}\n"
        
        receiver_message += f"🆔 <b>ID:</b> {user.id}\n\n"
        receiver_message += f"💬 <b>Сообщение:</b>\n<code>{message_text}</code>"
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=receiver_message,
                parse_mode='HTML'
            )
            
            await update.message.reply_text(
                f"✅ <b>СООБЩЕНИЕ ОТПРАВЛЕНО!</b>\n\n"
                f"👤 <b>Игроку с ID:</b> {target_id}\n"
                f"💬 <b>Ваше сообщение:</b>\n<code>{message_text}</code>",
                parse_mode='HTML'
            )
            
        except Exception as e:
            await update.message.reply_text("❌ Не удалось отправить сообщение. Игрок может заблокировать бота.")
            
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    level = db.get_user_level(user_data['total_farmed'])
    
    last_active = datetime.fromisoformat(user_data['last_active'])
    hours_ago = (datetime.now() - last_active).seconds // 3600
    
    message = (
        f"📋 <b>ПРОФИЛЬ ИГРОКА</b>\n\n"
        f"👤 <b>Имя:</b> {user.first_name}\n"
    )
    
    if user.username:
        message += f"📱 <b>Telegram:</b> @{user.username}\n"
    
    if user_data.get('display_name'):
        message += f"📝 <b>Имя в боте:</b> {user_data['display_name']}\n"
    
    message += (
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"⏰ <b>Был активен:</b> {hours_ago} ч. назад\n\n"
        f"💰 <b>Баланс:</b> {user_data['coins']} коинов\n"
        f"🏆 <b>Уровень:</b> {level['name']}\n"
        f"📈 <b>Заработано:</b> {user_data['total_farmed']} коинов\n"
        f"🔄 <b>Фармов:</b> {user_data['farm_count']}\n"
        f"📦 <b>Предметов:</b> {len(user_data['inventory'])}"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    
    if not context.args:
        total_users = len(db.data)
        active_today = 0
        
        for user_data in db.data.values():
            last_active = datetime.fromisoformat(user_data['last_active'])
            if (datetime.now() - last_active).days == 0:
                active_today += 1
        
        await update.message.reply_text(
            f"📊 <b>СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
            f"👥 <b>Всего игроков:</b> {total_users}\n"
            f"🟢 <b>Активных сегодня:</b> {active_today}\n\n"
            f"🔍 <b>Поиск игроков:</b>\n"
            f"<code>/users [имя или username]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/users matvei</code>",
            parse_mode='HTML'
        )
        return
    
    search_term = " ".join(context.args)
    results = db.search_users(search_term)
    
    if not results:
        await update.message.reply_text(
            f"🔍 <b>НИЧЕГО НЕ НАЙДЕНО</b>\n\n🔍 <b>Поиск:</b> {search_term}",
            parse_mode='HTML'
        )
        return
    
    message = f"✅ <b>НАЙДЕНО {len(results)} ИГРОКОВ</b>\n\n"
    
    for i, (user_id, user_data) in enumerate(results[:10], 1):
        if user_data.get('username'):
            name = f"@{user_data['username']}"
        elif user_data.get('display_name'):
            name = user_data['display_name'][:15]
            if len(user_data['display_name']) > 15:
                name += "..."
        else:
            name = f"ID:{user_id[:6]}"
        
        level = db.get_user_level(user_data['total_farmed'])
        
        message += (
            f"{i}. <b>{name}</b>\n"
            f"🆔 <code>{user_id}</code>\n"
            f"💰 {user_data['coins']} коинов | {level['name']}\n"
        )
    
    if len(results) > 10:
        message += f"\n📄 ... и еще {len(results) - 10} игроков"
    
    await update.message.reply_text(message, parse_mode='HTML')

def is_admin(user_id):
    return user_id == ADMIN_ID

async def give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text(
            f"💰 <b>ВЫДАЧА КОИНОВ</b>\n\n"
            f"📝 <b>Использование:</b>\n"
            f"1. Ответьте на сообщение игрока\n"
            f"2. Напишите: <code>/give [сумма]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/give 100</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        amount = int(context.args[0])
        target_user = update.message.reply_to_message.from_user
        new_balance = db.add_coins(target_user.id, amount, from_farm=False, from_admin=True)
        
        await update.message.reply_text(
            f"✅ <b>КОИНЫ ВЫДАНЫ!</b>\n\n"
            f"👤 <b>Игроку:</b> {target_user.first_name}\n"
            f"💰 <b>Сумма:</b> {amount} коинов\n"
            f"💳 <b>Новый баланс:</b> {new_balance} коинов",
            parse_mode='HTML'
        )
        
    except:
        await update.message.reply_text("❌ Ошибка! Укажите число")

async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Формат: /announce [текст]")
        return
    
    text = " ".join(context.args)
    await update.message.reply_text(
        f"📣 <b>ОБЪЯВЛЕНИЕ ОТ АДМИНА</b>\n\n{text}",
        parse_mode='HTML'
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Формат: /broadcast [текст]")
        return
    
    text = " ".join(context.args)
    message = f"📨 <b>СООБЩЕНИЕ ОТ АДМИНА</b>\n\n{text}"
    
    sent = 0
    failed = 0
    
    for user_id in db.data:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML'
            )
            sent += 1
        except:
            failed += 1
    
    await update.message.reply_text(
        f"📨 <b>РАССЫЛКА ЗАВЕРШЕНА</b>\n\n"
        f"✅ <b>Отправлено:</b> {sent} игрокам\n"
        f"❌ <b>Не отправлено:</b> {failed} игрокам",
        parse_mode='HTML'
    )

async def compensation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    total = db.add_compensation_to_all(COMPENSATION_AMOUNT)
    
    await update.message.reply_text(
        f"💰 <b>КОМПЕНСАЦИЯ ВЫДАНА!</b>\n\n"
        f"👥 <b>Игроков:</b> {total}\n"
        f"🎁 <b>Каждому:</b> {COMPENSATION_AMOUNT} коинов\n"
        f"💰 <b>Всего:</b> {total * COMPENSATION_AMOUNT} коинов",
        parse_mode='HTML'
    )

async def removeitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            f"🗑️ <b>УДАЛЕНИЕ ПРЕДМЕТА</b>\n\n"
            f"📝 <b>Использование:</b>\n"
            f"<code>/removeitem [ID_игрока] [номер_предмета]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/removeitem 6443845944 0</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        user_id = int(context.args[0])
        item_index = int(context.args[1])
        
        success, item = db.remove_item(user_id, item_index)
        
        if success:
            user_data = db.get_user(user_id)
            user_name = f"@{user_data.get('username', '')}" if user_data.get('username') else f"ID:{user_id}"
            
            await update.message.reply_text(
                f"✅ <b>ПРЕДМЕТ УДАЛЕН!</b>\n\n"
                f"🎁 <b>Предмет:</b> {item['name']}\n"
                f"👤 <b>От игрока:</b> {user_name}\n"
                f"💰 <b>Стоимость:</b> {item['price']} коинов",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Не удалось удалить предмет")
            
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Ошибка! Проверьте ID и номер предмета")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    total_players = len(db.data)
    total_coins = sum(user['coins'] for user in db.data.values())
    total_items = sum(len(user['inventory']) for user in db.data.values())
    
    message = (
        f"⚙️ <b>АДМИН ПАНЕЛЬ</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Игроков: {total_players}\n"
        f"💰 Коинов: {total_coins}\n"
        f"📦 Предметов: {total_items}"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("💰 Компенсация", callback_data="comp")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close")]
    ]
    
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def restore_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not update.message.document:
        await update.message.reply_text(
            f"🔄 <b>ВОССТАНОВЛЕНИЕ БАЗЫ</b>\n\n"
            f"📝 <b>Инструкция:</b>\n"
            f"1. Отправьте файл старой базы (kme_data.json)\n"
            f"2. Напишите команду: /restore_db\n\n"
            f"⚠️ <b>ТЕКУЩАЯ БАЗА БУДЕТ ПОЛНОСТЬЮ ЗАМЕНЕНА!</b>\n"
            f"💾 Но сначала будет создана её копия",
            parse_mode='HTML'
        )
        return
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_current = f"{DB_FILENAME}.backup_{timestamp}"
        
        if os.path.exists(DB_FILENAME):
            with open(DB_FILENAME, 'r', encoding='utf-8') as src:
                with open(backup_current, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
        
        file = await update.message.document.get_file()
        await file.download_to_drive(DB_FILENAME)
        
        global db
        db = Database(DB_FILENAME)
        
        await update.message.reply_text(
            f"✅ <b>БАЗА УСПЕШНО ЗАМЕНЕНА!</b>\n\n"
            f"📊 <b>Новая база:</b> {len(db.data)} игроков\n"
            f"💾 <b>Сохранена копия старой:</b> {backup_current}",
            parse_mode='HTML'
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка восстановления: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "close":
        await query.delete_message()
        return
    
    if query.data.startswith("view_"):
        await query.edit_message_text("✅ Предмет уже обменян")
        return
    
    elif query.data.startswith("exchange_"):
        item_index = int(query.data.split("_")[1])
        user = query.from_user
        db.update_user(user.id)
        success, item = db.exchange_item(user.id, item_index)
        
        if success:
            await query.edit_message_text(
                f"✅ <b>ПРЕДМЕТ ОТПРАВЛЕН НА ОБМЕН!</b>\n\n"
                f"🎁 <b>Предмет:</b> {item['name']}\n"
                f"💰 <b>Стоимость:</b> {item['price']} коинов\n\n"
                f"📨 Админ получил уведомление\n"
                f"⏳ Скоро свяжемся для выполнения",
                parse_mode='HTML'
            )
            await send_exchange_notification(context, user.id, item)
        else:
            await query.edit_message_text("❌ Ошибка обмена")
        return
    
    elif query.data == "stats":
        total_players = len(db.data)
        total_coins = sum(user['coins'] for user in db.data.values())
        total_items = sum(len(user['inventory']) for user in db.data.values())
        total_farmed = sum(user['total_farmed'] for user in db.data.values())
        
        await query.edit_message_text(
            f"📈 <b>ПОДРОБНАЯ СТАТИСТИКА</b>\n\n"
            f"👥 <b>Игроков:</b> {total_players}\n"
            f"💰 <b>Коинов:</b> {total_coins}\n"
            f"🎯 <b>Заработано:</b> {total_farmed}\n"
            f"📦 <b>Предметов:</b> {total_items}",
            parse_mode='HTML'
        )
        
    elif query.data == "comp":
        await query.edit_message_text(
            "💰 Используйте:\n<code>/compensation</code>",
            parse_mode='HTML'
        )
    elif query.data == "broadcast":
        await query.edit_message_text(
            "📢 Используйте:\n<code>/broadcast [текст]</code>",
            parse_mode='HTML'
        )

def main():
    print("=" * 50)
    print("🤖 KMEbot запускается...")
    print(f"👥 Игроков в базе: {len(db.data)}")
    print(f"🎮 Уровней: {len(LEVELS)}")
    print(f"💰 Фарм: 1-2 коинов, {FARM_COOLDOWN}ч КД")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"📁 Файл базы: {DB_FILENAME}")
    print("=" * 50)
    
    application = Application.builder().token(TOKEN).build()
    
    commands = [
        ("start", start),
        ("farm", farm),
        ("balance", balance),
        ("level", level),
        ("shop", shop),
        ("inventory", inventory),
        ("party", party),
        ("write", write),
        ("profile", profile),
        ("users", users),
        ("help", start),
        ("announce", announce),
        ("broadcast", broadcast),
        ("compensation", compensation),
        ("removeitem", removeitem),
        ("admin", admin),
        ("give", give),
        ("restore_db", restore_db),
    ]
    
    for cmd, handler in commands:
        application.add_handler(CommandHandler(cmd, handler))
    
    def create_buy_handler(item_id):
        async def handler(update, context):
            return await buy_item(update, context, item_id)
        return handler
    
    for item_id in SHOP_ITEMS.keys():
        application.add_handler(CommandHandler(f"buy_{item_id}", create_buy_handler(item_id)))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Бот запущен!")
    print(f"📁 Файл базы: {DB_FILENAME}")
    print("🔄 Для восстановления БД: отправьте файл и /restore_db")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
