import discord
import psycopg2
import os

from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from enum import Enum

_token = os.getenv("CONVERT_TOKEN")
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
CREATE TABLE IF NOT EXISTS rates (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

db.commit()

# ENUM DATATYPES
class RobuxType(Enum):
    gf  = ("Group Fund", "gf_rate")
    gp  = ("Gamepass", "gp_rate")
    igg = ("In-Game Gifting","igg_rate")

# PERMISSION LEVEL CHECK
def ownerOnly():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.id == _ownerId

    return app_commands.check(predicate)

def adminOnly():
    return app_commands.checks.has_permissions(administrator = True)

def moderatorOnly():
    return app_commands.checks.has_permissions(manage_messages = True)

#CURRENCY PARSING
def parseAmount(amount: str):

    amount = amount.lower()

    if amount.endswith("k"):
        return int(float(amount[:-1]) * 1000)

    if amount.endswith("m"):
        return int(float(amount[:-1]) * 1000000)
    
    if amount.endswith("b"):
        return int(float(amount[:-1]) * 1000000000)

    return int(amount)

#RATE HANDLING LOGIC
def getRate(rateType: str):

    cursor.execute("""
    SELECT value
    FROM rates
    WHERE key = %s
    """, (rateType,))

    result = cursor.fetchone()

    if not result:
        return None

    return float(result[0])

def convert(amount: str, rateType: str):

    value = parseAmount(amount)
    rate = getRate(rateType)

    if rate is None:
        return None, None

    return value, value * rate / 1000

def convertResult(robux: int, value: float, type: RobuxType):

    embed = discord.Embed(title = "$ Miffy Price Check $", 
                          colour = discord.Colour.white(), 
                          timestamp = datetime.now())
    embed.add_field(name = "𑣲.Order Type", value = type.value[0], inline = True)
    embed.add_field(name = "𑣲.Rate", value = f"RM {getRate(type.value[1]):,.2f}/1k rbx", inline = True)
    embed.add_field(name = "𑣲.Quantity", value = f"{robux:,} rbx", inline = False)
    embed.add_field(name = "𑣲.Total", value = f"RM {value:.2f}", inline = False)
    embed.set_footer(text = "𓏵‧₊ mifforia hubb")
    return embed

#COMMANDS
@client.tree.command(name = "editrate", description = "Set conversion rate", guild = GUILD_ID)
@ownerOnly()
async def editRate(interaction: discord.Interaction, type: RobuxType, rate: float):

    key = type.value[1]

    cursor.execute("""
    INSERT INTO rates (key, value)
    VALUES (%s, %s)
    ON CONFLICT (key)
    DO UPDATE SET value = EXCLUDED.value
    """, (key, str(rate)))

    db.commit()

    embed = discord.Embed(
        title = "Conversion Rate Updated",
        colour = discord.Colour.blue(),
        timestamp = datetime.now()
    )
    embed.add_field(name = "Type", value = type.value[0])
    embed.add_field(name = "New Rate", value = rate)

    embed.set_footer(
        text = f"Edited by {interaction.user.name}", 
        icon_url = interaction.user.display_avatar.url
    )

    await interaction.response.send_message(embed = embed)

@client.tree.command(name = "gf", description = "Group Fund Conversion", guild = GUILD_ID)
async def gf(interaction: discord.Interaction, amount: str):

    type = RobuxType.gf
    value, myr = convert(amount, type.value[1])

    if value is None:
        await interaction.response.send_message("❌ Rate not set.", ephemeral = True)
        return
    
    await interaction.response.send_message(embed = convertResult(value, myr, type))

@client.tree.command(name="gp", description = "Gamepass Conversion", guild = GUILD_ID)
async def gp(interaction: discord.Interaction, amount: str):

    type = RobuxType.gp
    value, myr = convert(amount, type.value[1])

    if value is None:
        await interaction.response.send_message("❌ Rate not set.", ephemeral = True)
        return

    await interaction.response.send_message(embed = convertResult(value, myr, type))

@client.tree.command(name="igg", description = "In-Game Gifting Conversion", guild = GUILD_ID)
async def igg(interaction: discord.Interaction, amount: str):

    type = RobuxType.igg
    value, myr = convert(amount, type.value[1])

    if value is None:
        await interaction.response.send_message("❌ Rate not set.", ephemeral = True)
        return

    await interaction.response.send_message(embed = convertResult(value, myr, type))
    
#PERMISSION ERROR HANDLING
@client.tree.error
async def on_app_command_error(interaction: discord.Interaction,err: app_commands.AppCommandError):
    if isinstance(err, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral = True
        )
    
client.run(_token)
