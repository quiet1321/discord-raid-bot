import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import os
# ===== НАСТРОЙКИ - ЗАМЕНИТЕ НА ВАШИ ID =====
SETUP_CHANNEL_ID = 1503546309427331212   # ВСТАВЬТЕ ID КАНАЛА ДЛЯ КНОПКИ
SIGNUP_CHANNEL_ID = 1503547476135772231  # ВСТАВЬТЕ ID КАНАЛА ДЛЯ ЗАПИСИ
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
# ===========================================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

active_raids = {}

# Словарь эмодзи для разных типов ролей
ROLE_EMOJIS = {
    "танк": "🛡️",
    "хил": "💚",
    "хиллер": "💚",
    "хизл": "💚",
    "дд": "⚔️",
    "дамаг": "⚔️",
    "дпс": "⚔️",
    "ск": "🔪",
    "рдд": "🏹",
    "мдд": "🗡️",
    "хилпал": "💚",
    "протвар": "🛡️",
    "ретрик": "⚔️",
}

# Функция для получения эмодзи по названию роли
def get_role_emoji(role_name: str) -> str:
    role_lower = role_name.lower()
    for key, emoji in ROLE_EMOJIS.items():
        if key in role_lower:
            return emoji
    return "📌"  # эмодзи по умолчанию

# Функция для получения статуса рейда
def get_raid_status(filled: int, total: int) -> tuple[str, discord.Color]:
    if filled == 0:
        return "🔴 Набор открыт", discord.Color.red()
    elif filled == total:
        return "✅ Полный сбор", discord.Color.green()
    elif filled >= total - 2:
        return "🟡 Почти полон", discord.Color.gold()
    else:
        return "🟢 Идет набор", discord.Color.blue()

class CreateRaidModal(discord.ui.Modal, title="🛡️ Создание нового рейда"):
    raid_name = discord.ui.TextInput(
        label="Название рейда",
        placeholder="Пример: Очистка замка",
        required=True,
        max_length=100
    )
    conditions = discord.ui.TextInput(
        label="Условия",
        placeholder="Пример: 4.3, 470+ илвл, дискорд",
        required=True,
        max_length=200
    )
    roles = discord.ui.TextInput(
        label="Роли (через запятую)",
        placeholder="Танк, Хил, ДД1, ДД2, ДД3, СК, ДД4",
        required=False,
        max_length=500,
        default="Танк, Хил, ДД1, ДД2, ДД3, СК, ДД4"
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        role_list = [r.strip() for r in self.roles.value.split(",") if r.strip()]
        if not role_list:
            role_list = ["Танк", "Хил", "ДД1", "ДД2", "ДД3", "СК", "ДД4"]
        
        slots = {role: {"user": None} for role in role_list}
        
        signup_channel = bot.get_channel(SIGNUP_CHANNEL_ID)
        if not signup_channel:
            await interaction.followup.send("❌ Канал для записи не найден!", ephemeral=True)
            return
        
        raid_data = {
            "name": self.raid_name.value,
            "conditions": self.conditions.value,
            "creator_id": interaction.user.id,
            "creator_name": interaction.user.display_name,
            "creator_avatar": interaction.user.display_avatar.url,
            "slots": slots,
            "created_at": datetime.now(),
            "message_id": None
        }
        
        # Отправляем красивое сообщение
        embed = await self.create_embed(raid_data)
        view = RaidSignupView(raid_data)
        message = await signup_channel.send(embed=embed, view=view)
        raid_data["message_id"] = message.id
        active_raids[message.id] = raid_data
        
        await interaction.followup.send(
            f"✨ **Рейд «{self.raid_name.value}» успешно создан!**\n"
            f"📢 Объявление отправлено в {signup_channel.mention}",
            ephemeral=True
        )
    
    async def create_embed(self, raid_data):
        slots = raid_data['slots']
        filled = sum(1 for s in slots.values() if s['user'] is not None)
        total = len(slots)
        
        status_text, status_color = get_raid_status(filled, total)
        
        embed = discord.Embed(
            title=f"⚔️ РЕЙД: {raid_data['name'].upper()}",
            color=status_color,
            timestamp=raid_data['created_at']
        )
        
        # Информационная строка
        embed.add_field(
            name="📋 Информация",
            value=f"└ **Условия:** {raid_data['conditions']}\n"
                  f"└ **Статус:** {status_text}\n"
                  f"└ **Участников:** {filled}/{total}",
            inline=False
        )
        
        # Создатель
        embed.add_field(
            name="👑 Создатель",
            value=f"└ {raid_data['creator_name']}",
            inline=False
        )
        
        # Состав группы
        slots_text = ""
        for role, data in slots.items():
            emoji = get_role_emoji(role)
            if data['user']:
                member = interaction.guild.get_member(data['user']) if hasattr(self, 'interaction') else None
                name = member.display_name if member else f"<@{data['user']}>"
                slots_text += f"└ {emoji} **{role}** → {name}\n"
            else:
                slots_text += f"└ {emoji} **{role}** → *Свободно*\n"
        
        embed.add_field(name="🎯 Состав группы", value=slots_text, inline=False)
        
        embed.set_footer(text=f"ID: {raid_data['message_id'] or 'новый'} • Нажмите на кнопку для записи")
        embed.set_thumbnail(url=raid_data['creator_avatar'])
        
        return embed

class CreateRaidButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="➕ Создать рейд", style=discord.ButtonStyle.green, emoji="✨")
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateRaidModal())

class RaidSignupView(discord.ui.View):
    def __init__(self, raid_data):
        super().__init__(timeout=None)
        self.raid_data = raid_data
        self._add_buttons()
    
    def _add_buttons(self):
        # Кнопки для каждой роли с эмодзи
        for role_name in self.raid_data['slots'].keys():
            emoji = get_role_emoji(role_name)
            btn = discord.ui.Button(
                label=role_name,
                style=discord.ButtonStyle.primary,
                emoji=emoji
            )
            btn.callback = self._make_callback(role_name)
            self.add_item(btn)
        
        # Кнопка отмены
        cancel = discord.ui.Button(
            label="Отменить запись",
            style=discord.ButtonStyle.secondary,
            emoji="❌"
        )
        cancel.callback = self._cancel_callback
        self.add_item(cancel)
        
        # Кнопка закрытия
        close = discord.ui.Button(
            label="Закрыть рейд",
            style=discord.ButtonStyle.danger,
            emoji="🗑️"
        )
        close.callback = self._close_callback
        self.add_item(close)
    
    def _make_callback(self, role_name):
        async def callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            
            # Проверка на двойную запись
            for r, d in self.raid_data['slots'].items():
                if d['user'] == user_id:
                    await interaction.response.send_message(
                        f"❌ Вы уже записаны на роль **{r}**!\n"
                        f"Сначала отмените запись.",
                        ephemeral=True
                    )
                    return
            
            # Проверка свободна ли роль
            if self.raid_data['slots'][role_name]['user'] is None:
                self.raid_data['slots'][role_name]['user'] = user_id
                await interaction.response.send_message(
                    f"✅ **Вы успешно записались!**\n"
                    f"└ Роль: **{role_name}**\n"
                    f"└ Рейд: **{self.raid_data['name']}**",
                    ephemeral=True
                )
                await self._update(interaction)
            else:
                await interaction.response.send_message(
                    f"❌ Роль **{role_name}** уже занята!\n"
                    f"└ Попробуйте выбрать другую роль.",
                    ephemeral=True
                )
        return callback
    
    async def _cancel_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        for r, d in self.raid_data['slots'].items():
            if d['user'] == user_id:
                d['user'] = None
                await interaction.response.send_message(
                    f"🚫 **Вы отменили запись!**\n"
                    f"└ Роль: **{r}**\n"
                    f"└ Рейд: **{self.raid_data['name']}**",
                    ephemeral=True
                )
                await self._update(interaction)
                return
        await interaction.response.send_message(
            "❌ Вы не записаны ни на одну роль в этом рейде!",
            ephemeral=True
        )
    
    async def _close_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.raid_data['creator_id'] and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ **Доступ запрещен!**\n"
                "└ Только создатель рейда может его закрыть.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            f"✅ **Рейд закрыт!**\n"
            f"└ Рейд: **{self.raid_data['name']}**\n"
            f"└ Создатель: {interaction.user.mention}",
            ephemeral=True
        )
        await interaction.message.delete()
        if self.raid_data.get('message_id') in active_raids:
            del active_raids[self.raid_data['message_id']]
    
    async def _update(self, interaction):
        slots = self.raid_data['slots']
        filled = sum(1 for s in slots.values() if s['user'] is not None)
        total = len(slots)
        
        status_text, status_color = get_raid_status(filled, total)
        
        embed = discord.Embed(
            title=f"⚔️ РЕЙД: {self.raid_data['name'].upper()}",
            color=status_color,
            timestamp=self.raid_data['created_at']
        )
        
        embed.add_field(
            name="📋 Информация",
            value=f"└ **Условия:** {self.raid_data['conditions']}\n"
                  f"└ **Статус:** {status_text}\n"
                  f"└ **Участников:** {filled}/{total}",
            inline=False
        )
        
        embed.add_field(
            name="👑 Создатель",
            value=f"└ {self.raid_data['creator_name']}",
            inline=False
        )
        
        slots_text = ""
        for role, data in slots.items():
            emoji = get_role_emoji(role)
            if data['user']:
                slots_text += f"└ {emoji} **{role}** → <@{data['user']}>\n"
            else:
                slots_text += f"└ {emoji} **{role}** → *Свободно*\n"
        
        embed.add_field(name="🎯 Состав группы", value=slots_text, inline=False)
        embed.set_footer(text=f"ID: {self.raid_data['message_id']} • Нажмите на кнопку для записи")
        embed.set_thumbnail(url=self.raid_data['creator_avatar'])
        
        await interaction.message.edit(embed=embed, view=self)

@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    print(f"✅ На серверах: {len(bot.guilds)}")
    
    channel = bot.get_channel(SETUP_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🛡️ Панель управления рейдами",
            description="✨ **Добро пожаловать!**\n\n"
                       "Нажмите на кнопку ниже, чтобы создать новый рейд.\n"
                       "Вы сможете настроить название, условия и роли.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Все рейды автоматически сохраняются")
        await channel.send(embed=embed, view=CreateRaidButton())
        print(f"✅ Кнопка отправлена в канал {channel.name}")
    else:
        print(f"❌ Канал с ID {SETUP_CHANNEL_ID} не найден!")
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Команды синхронизированы: {len(synced)}")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")

@bot.tree.command(name="list_raids", description="Показать активные рейды")
async def list_raids(interaction: discord.Interaction):
    if not active_raids:
        embed = discord.Embed(
            title="📭 Активные рейды",
            description="На данный момент нет активных рейдов.\n"
                       "Создайте новый рейд, нажав на кнопку **«➕ Создать рейд»** в канале управления.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📋 Активные рейды",
        description=f"Всего активных рейдов: **{len(active_raids)}**",
        color=discord.Color.green()
    )
    
    for msg_id, raid in active_raids.items():
        filled = sum(1 for s in raid['slots'].values() if s['user'] is not None)
        total = len(raid['slots'])
        status, _ = get_raid_status(filled, total)
        
        embed.add_field(
            name=f"⚔️ {raid['name']}",
            value=f"└ **Условия:** {raid['conditions']}\n"
                  f"└ **Статус:** {status}\n"
                  f"└ **Участников:** {filled}/{total}\n"
                  f"└ **Создал:** {raid['creator_name']}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
