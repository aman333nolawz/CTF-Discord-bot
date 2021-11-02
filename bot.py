from discord.ext import commands
import discord
import requests
import datetime
import os
from inspect import getmembers, isfunction
import string
import sys
import binascii
import base64
import random

DISCORD_API_KEY = os.environ.get("DISCORD_API_KEY")

events_url = "https://ctftime.org/api/v1/events/"
quote_url = "https://api.quotable.io/random"
joke_url = "https://meme-api.herokuapp.com/gimme/"

headers = {"User-Agent": "Mozilla/5.0"}

bot = commands.Bot(command_prefix="/", strip_after_prefix=True)

def get_upcoming_ctfs(limit=2):
    res = requests.get(events_url, params={"limit": limit}, headers=headers)
    return res.json()

def get_random_quote():
    res = requests.get(quote_url)
    return res.json()

def get_random_joke():
    res = requests.get(joke_url, params={"nsfw": False})
    return res.json()

def unhex(*hex_str):
    hex_str = "".join(hex_str)
    if hex_str.startswith("0x"):
        hex_str = hex_str[2:]

    encoded_string = bytes.fromhex(hex_str)
    return encoded_string.decode()

class Caesar:
    caesar_charset = string.ascii_lowercase
    @staticmethod
    def encrypt(msg: str, key: int):
        out = ""
        for char in msg:
            try:
                shift = (Caesar.caesar_charset.index(char.lower()) + key) % 26
                out += Caesar.caesar_charset[shift] if char.islower() else Caesar.caesar_charset[shift].upper()
            except ValueError:
                out += char
        return out

    @staticmethod
    def decrypt(msg: str, key: int):
        return Caesar.encrypt(msg, -key)

class Rot13:
    @staticmethod
    def encrypt(msg):
        return Caesar.encrypt(msg, 13)

class Rot47:
    rot47_charset = '!"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~'
    @staticmethod
    def encrypt(msg: str):
        out = ""
        for char in msg:
            try:
                shift = (Rot47.rot47_charset.index(char) + 47) % 94
                out += Rot47.rot47_charset[shift]
            except ValueError:
                out += char
        return out

    @staticmethod
    def decrypt(msg: str):
        out = ""
        for char in msg:
            try:
                shift = (Rot47.rot47_charset.index(char) - 47) % 94
                out += Rot47.rot47_charset[shift]
            except ValueError:
                out += char
        return out


@bot.command("upcoming-ctfs")
async def cmd_upcoming_ctfs(ctx, num=2):
    """
    List upcoming CTFs on ctftime.org
    """
    num = min(15, num)
    for ctf in get_upcoming_ctfs(num):
        if ctf.get("restrictions").lower() == "open":
            title = ctf.get("title")
            url = ctf.get("url")
            format_ = ctf.get("format")
            start = ctf.get("start")
            finish = ctf.get("finish")
        
            embed = discord.Embed(
                title=title, description=str(url), color=discord.Colour.green()
            )
            embed.add_field(name="Format", value=str(format_))
            if start and finish:
                start = start[:-3] + start[-2:]
                start = datetime.datetime.strptime(start,"%Y-%m-%dT%H:%M:%S%z")
                start = start.strftime("%Y-%m-%d %H:%M %Z")

                finish = finish[:-3] + finish[-2:]
                finish = datetime.datetime.strptime(finish,"%Y-%m-%dT%H:%M:%S%z")
                finish = finish.strftime("%Y-%m-%d %H:%M %Z")

                embed.add_field(name="Timeframe", value=f"{start}->{finish}")
            await ctx.reply(embed=embed, delete_after=300)


@bot.command("quote")
async def cmd_quote(ctx):
    """
    Get random quote
    """
    quote = get_random_quote()
    content = quote.get("content")
    author = quote.get("author")
    embed = discord.Embed(
        title=content, description=f"**{author}**", color=discord.Colour.green()
    )
    await ctx.reply(embed=embed, delete_after=300)

@bot.command("joke")
async def cmd_joke(ctx):
    """
    Gets a random joke from reddit.
    """
    joke = get_random_joke()
    title = joke.get("title")
    if title:
        await ctx.reply(title, delete_after=300)
    await ctx.reply(joke.get("url"), delete_after=300)


@bot.command("unhex")
async def cmd_unhex(ctx, *hex_str):
    """
    Unhex the hex passed as argument.
    """
    try:
        ascii_val = unhex(*hex_str)
        await ctx.reply(ascii_val, delete_after=300)
    except UnicodeDecodeError:
        await ctx.reply("That isn't a valid hex", delete_after=300)
    except:
        await ctx.reply("Sorry something went wrong :(", delete_after=300)

@bot.command("rot")
async def cmd_rot(ctx, *text):
    """
    /rot "a message" Returns all 25 possible rotations for a message.
    """
    text = " ".join(text).replace("`", "")
    try:
        out = "```"
        for i in range(1, 26):
            rot = Caesar.decrypt(text, i)
            out += rot + "\n"
        out += "```"
        await ctx.reply(out, delete_after=300)
    except:
        await ctx.reply("Sorry something went wrong :(", delete_after=300)

@bot.command("rot13")
async def cmd_rot13(ctx, *text):
    """
    Decrypt and encrypt message in rot13.
    """
    text = " ".join(text).replace("`", "")
    try:
        rot13 = Rot13.encrypt(text)
        await ctx.reply(f"```{rot13}```", delete_after=300)
    except:
        await ctx.reply("Sorry something went wrong :(", delete_after=300)

@bot.command("rot47")
async def cmd_rot47(ctx, *text):
    """
    Decrypt and encrypt message in rot47.
    """
    text = " ".join(text).replace("`", "")
    try:
        rot47 = Rot47.encrypt(text)
        await ctx.reply(f"```{rot47}```", delete_after=300)
    except:
        await ctx.reply("Sorry something went wrong :(", delete_after=300)

@bot.command("hex")
async def cmd_hex(ctx, *text):
    """
    Hex the strings passed as arguments.
    """
    text = " ".join(text).replace("`", "")
    try:
        hex_string = binascii.hexlify(text.encode()).decode()
        await ctx.reply(hex_string, delete_after=300)
    except:
        await ctx.reply("Sorry something went wrong :(", delete_after=300)

@bot.command("base64", aliases=["b64"])
async def cmd_base64(ctx, method, *msg):
    """
    Encode or decode in base64.
    Usage: base64 [e|d] message.
    For method use "e" for encoding and "d" for decoding
    """
    msg = " ".join(msg).replace("`", "")
    if method[0] == "e":
        try:
            base64_encoded = base64.b64encode(msg.encode()).decode()
            await ctx.reply(f"```{base64_encoded}```", delete_after=300)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=300)
    elif method[0] == "d":
        try:
            base64_decoded = base64.b64decode(msg).decode()
            await ctx.reply(f"```{base64_decoded}```", delete_after=300)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=300)
    else:
        await ctx.reply(f"{method} is not a valid option", delete_after=300)

@bot.command("base32", aliases=["b32"])
async def cmd_base32(ctx, method, *msg):
    """
    Encode or decode in base32.
    Usage: base32 [e|d] message.
    For method use "e" for encoding and "d" for decoding
    """
    msg = " ".join(msg).replace("`", "")
    if method[0] == "e":
        try:
            base32_encoded = base64.b32encode(msg.encode()).decode()
            await ctx.reply(f"```{base32_encoded}```", delete_after=300)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=300)
    elif method[0] == "d":
        try:
            base32_decoded = base64.b32decode(msg).decode()
            await ctx.reply(f"```{base32_decoded}```", delete_after=300)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=300)
    else:
        await ctx.reply(f"{method} is not a valid option", delete_after=300)


@bot.command("cointoss")
async def cmd_cointoss(ctx):
    """
    Flips a coin for you.
    """
    coin_faces = ["heads", "tails"]
    await ctx.reply(random.choice(coin_faces), delete_after=300)


bot.run(DISCORD_API_KEY)
