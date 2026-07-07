import discord
import psycopg2
import os

from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from enum import Enum

_token = os.getenv("CREDIT_TOKEN")
_serverId = int(os.getenv("SERVER_ID"))
_ownerId = int(os.getenv("OWNER_ID"))

GUILD_ID = discord.Object(id = _serverId)

class Client(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix = "!",
            intents = intents
        )

    async def on_ready(self):
        print(f"[main.py] {self.user} is online!")

        try:

            guild = discord.Object(id = _serverId)
            synced = await self.tree.sync(guild = guild)
            print(f"[main.py] Synced {len(synced)} commands to guild {guild.id}!")

        except Exception as err:

            print(f"[main.py] Error syncing commands : {err}")


intents = discord.Intents.default()
intents.message_content = True
client = Client()

#DATABASE CREATION
db = psycopg2.connect(
    os.getenv("DATABASE_URL"),
    sslmode="require"
)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    total_spending REAL DEFAULT 0,
    wallet REAL DEFAULT 0
)
""")

db.commit()

# PERMISSION LEVEL CHECK
def ownerOnly():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.id == _ownerId

    return app_commands.check(predicate)

def adminOnly():
    return app_commands.checks.has_permissions(administrator = True)

def moderatorOnly():
    return app_commands.checks.has_permissions(manage_messages = True)

# ENUM DATATYPES
class ActionType(Enum):
    add    = "add"
    remove = "remove"

# USER VALIDATION
def validateUser(user: discord.Member):

    cursor.execute("""
    INSERT INTO users (user_id, username)
    VALUES (%s, %s)
    ON CONFLICT(user_id)
    DO UPDATE SET username = excluded.username
    """, (str(user.id), user.name))

    db.commit()

#COMMANDS
@client.tree.command(name = "log", description = "Log customer spending", guild = GUILD_ID)
@adminOnly()
async def logSpending(interaction: discord.Interaction, user: discord.Member, amount: str):

    try:
        amount = float(amount)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount.",ephemeral=True)
        return

    validateUser(user)

    cursor.execute("""
    UPDATE users
    SET total_spending = total_spending + %s
    WHERE user_id = %s
    """, (amount, str(user.id)))

    db.commit()

    cursor.execute("""
    SELECT total_spending
    FROM users
    WHERE user_id = %s
    """, (str(user.id),))

    total = cursor.fetchone()[0]

    embed = discord.Embed(title = "🐰 Purchase Successful !", colour = discord.Colour.from_rgb(255,255,255))
    embed.add_field(name = "୨୧ User", value = user.mention, inline = False)
    embed.add_field(name = "꒰୨୧꒱ Amount Added", value = f"RM {amount:,.2f}", inline = False)
    embed.add_field(name = "𑣲. Total Spending", value = f"RM {total:,.2f}", inline = False)

    await interaction.response.send_message(embed = embed)

@client.tree.command(name = "editlog", description = "Edit customer total spending", guild = GUILD_ID)
@adminOnly()
async def editSpending(interaction: discord.Interaction, user: discord.Member, amount: str):

    try:
        amount = float(amount)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount.",ephemeral=True)
        return

    validateUser(user)

    cursor.execute("""
    UPDATE users
    SET total_spending = %s
    WHERE user_id = %s
    """, (amount, str(user.id)))

    db.commit()

    embed = discord.Embed(title = "🐰 Log Edit Successful", colour = discord.Colour.from_rgb(255,255,255))
    embed.add_field(name = "୨୧ User", value = user.mention, inline = False)
    embed.add_field(name = "𑣲. New Total Spending", value = f"RM {amount:,.2f}", inline = False)

    await interaction.response.send_message(embed = embed)

@client.tree.command(name = "credit", description = "Add/Remove customer credits", guild = GUILD_ID)
@adminOnly()
async def manageCredits(interaction: discord.Interaction, action: ActionType, user: discord.Member, amount: str):

    try:
        amount = float(amount)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount.",ephemeral=True)
        return

    validateUser(user)

    if action == ActionType.add:

        cursor.execute("""
        UPDATE users
        SET wallet = wallet + %s
        WHERE user_id = %s
        """, (amount, str(user.id)))

    else:

        cursor.execute("""
        SELECT wallet
        FROM users
        WHERE user_id = %s
        """, (str(user.id),))

        current = cursor.fetchone()[0]

        if current < amount:

            await interaction.response.send_message("❌ Insufficient balance.")

            return

        cursor.execute("""
        UPDATE users
        SET wallet = wallet - %s
        WHERE user_id = %s
        """, (amount, str(user.id)))

    db.commit()

    cursor.execute("""
    SELECT wallet
    FROM users
    WHERE user_id = %s
    """, (str(user.id),))

    wallet = cursor.fetchone()[0]

    embed = discord.Embed(title = "🍓 MifCreds Updated", 
                          colour = discord.Colour.from_rgb(255,255,255) if action == ActionType.add else discord.Colour.red(),
                          timestamp = datetime.now())
    embed.add_field(name = "୨୧ User", value = user.mention, inline = False)
    embed.add_field(name = f"꒰୨୧꒱ MifCreds {'Added' if action == ActionType.add else 'Deducted'}",
                    value = f"RM {amount:,.2f}", inline = True)
    embed.add_field(name = "𑣲.New Balance", value = f"RM {wallet:,.2f}", inline = True)
    embed.set_footer(text = f"{'𓏵‧₊ Added' if action == ActionType.add else '𓏵‧₊ Deducted'} by {interaction.user.name}",
                     icon_url = interaction.user.display_avatar.url)

    await interaction.response.send_message(embed = embed)

@client.tree.command(name = "cbalance", description = "Check a user's balance", guild = GUILD_ID)
async def balance(interaction: discord.Interaction, user: discord.Member = None):

    user = user or interaction.user

    validateUser(user)

    db.commit()

    cursor.execute("""
    SELECT wallet
    FROM users
    WHERE user_id = %s
    """, (str(user.id),))

    wallet = cursor.fetchone()[0]

    embed = discord.Embed(title = "♡ Mif Wallet", colour = discord.Colour.from_rgb(255,255,255))
    embed.set_thumbnail(url = user.display_avatar.url)
    embed.add_field(name = "୨୧ Username", value = user.mention, inline = True)
    embed.add_field(name = "꒰୨୧꒱ MifCred Balance", value = f"RM {wallet:,.2f} ", inline = True)
    embed.set_footer(text = f"𓏵‧₊ Requested by {interaction.user.name}",
                     icon_url = interaction.user.display_avatar.url)

    await interaction.response.send_message(embed = embed)

#PERMISSION ERROR HANDLING
@client.tree.error
async def on_app_command_error(interaction: discord.Interaction,err: app_commands.AppCommandError):
    if isinstance(err, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral = True
        )

client.run(_token)
