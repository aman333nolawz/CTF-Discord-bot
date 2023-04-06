import asyncio
import base64
import binascii
import datetime
import html
import logging
import os
import random
import string
from urllib.parse import parse_qs, quote, unquote, urlparse

import discord
import mysql.connector
import requests
import wikipedia
from discord.ext import commands
from pytube import Playlist, Search, YouTube
from pytube.exceptions import LiveStreamError

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

DISCORD_API_KEY = os.environ.get("DISCORD_API_KEY")

events_url = "https://ctftime.org/api/v1/events/"
quote_url = "https://api.quotable.io/random"
joke_url = "https://www.reddit.com/r/memes/.json"
lofi_url = "https://lofi-api.herokuapp.com/v1/track"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246"
}
poll_emojis = ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣"]

delete_seconds = 300


mydb = mysql.connector.connect(
    host="cloud.mindsdb.com",
    user=os.environ.get("MINDSDB_USER"),
    password=os.environ.get("MINDSDB_PASSW"),
    port=3306,
)
cursor = mydb.cursor()

bot = commands.Bot(command_prefix="/", strip_after_prefix=True)


def get_upcoming_ctfs(limit=2):
    res = requests.get(events_url, params={"limit": limit}, headers=headers)
    return res.json()


def get_random_quote():
    res = requests.get(quote_url)
    return res.json()


def get_random_joke():
    res = requests.get(joke_url, headers=headers)
    joke = res.json()
    joke = random.choice(joke["data"]["children"])["data"]
    is_nsfw = joke.get("over_18")
    if is_nsfw:
        return get_random_joke()
    return joke.get("url", ""), joke.get("title", "**Joke**"), joke.get("permalink", "")


def get_lofi_music():
    r = requests.get(lofi_url)
    items = r.json().get("items")
    return random.choice(items)


def get_youtube_audio(url, index=0):
    parsed_url = urlparse(url)
    playlist = parse_qs(parsed_url.query).get("list")

    if playlist:
        try:
            s = Playlist(f"https://www.youtube.com/playlist?list={playlist[-1]}")
            return s
        except:
            pass

    try:
        s = YouTube(url)
        return s.watch_url
    except:
        try:
            s = Search(url).results[index]
            return s.watch_url
        except LiveStreamError:
            return get_youtube_audio(url, index + 1)
        except:
            if "youtube.com" not in url:
                s = get_youtube_audio(f"https://www.youtube.com/watch?v={url}")
            if not s:
                return


def get_wikipedia_summary(topic):
    search = wikipedia.search(topic, results=1)
    if not search:
        return False
    page = wikipedia.page(search[0], auto_suggest=False)
    return page.title, page.summary, page.url


def download_audio(url):
    if isinstance(url, YouTube):
        s = url
        audios = s.streams.filter(mime_type="audio/mp4", only_audio=True).order_by(
            "abr"
        )
        song = audios[-1]
        return {
            "title": s.title,
            "thumbnail": s.thumbnail_url,
            "artist": s.author,
            "url": song.url,
        }
    try:
        s = YouTube(url)
    except:
        try:
            s = Search(url).results[0]
        except:
            if "youtube.com" not in url:
                s = download_audio(f"https://www.youtube.com/watch?v={url}")
            if not s:
                return

    audios = s.streams.filter(mime_type="audio/mp4", only_audio=True).order_by("abr")
    song = audios[-1]
    return {
        "title": s.title,
        "thumbnail": s.thumbnail_url,
        "artist": s.author,
        "url": song.url,
    }


def unhex(*hex_str):
    hex_str = "".join(hex_str)
    if hex_str.startswith("0x"):
        hex_str = hex_str[2:]

    encoded_string = bytes.fromhex(hex_str)
    return encoded_string.decode()


def chatbot(username, prompt):
    cursor.execute(
        """SELECT response from mindsdb.snowlon_model
WHERE 
author_username = %s 
AND text=%s;""",
        (username, prompt),
    )
    out = ""
    for response in cursor:
        out = response[0]
    return out


class Caesar:
    caesar_charset = string.ascii_lowercase

    @staticmethod
    def encrypt(msg: str, key: int):
        out = ""
        for char in msg:
            try:
                shift = (Caesar.caesar_charset.index(char.lower()) + key) % 26
                out += (
                    Caesar.caesar_charset[shift]
                    if char.islower()
                    else Caesar.caesar_charset[shift].upper()
                )
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
    rot47_charset = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~"

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


@bot.event
async def on_raw_reaction_add(payload):
    channel = await bot.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name)

    if payload.user_id != bot.user.id and payload.emoji.name not in poll_emojis:
        await reaction.remove(payload.member)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.after_invoke
async def common(message):
    try:
        await asyncio.sleep(delete_seconds)
        await message.message.delete()
    except Exception as e:
        logging.exception("Exception occurred")


class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command("upcoming-ctfs")
    async def upcoming_ctfs(self, ctx, num=2):
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
                    start = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
                    start = start.strftime("%Y-%m-%d %H:%M %Z")

                    finish = finish[:-3] + finish[-2:]
                    finish = datetime.datetime.strptime(finish, "%Y-%m-%dT%H:%M:%S%z")
                    finish = finish.strftime("%Y-%m-%d %H:%M %Z")

                    embed.add_field(name="Timeframe", value=f"{start}->{finish}")
                await ctx.reply(embed=embed, delete_after=delete_seconds)


class Miscellaneous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command("quote")
    async def quote(self, ctx):
        """
        Get random quote
        """
        try:
            quote = get_random_quote()
            content = quote.get("content")
            author = quote.get("author")
            embed = discord.Embed(
                title=content, description=f"**{author}**", color=discord.Colour.green()
            )
            await ctx.reply(embed=embed, delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")

    @commands.command("joke")
    async def joke(self, ctx):
        """
        Gets a random joke from reddit.
        """
        try:
            url, title, link = get_random_joke()
            embed = discord.Embed(
                title=title,
                color=discord.Colour.orange(),
                timestamp=datetime.datetime.utcnow(),
                description=f"Post: https://reddit.com{link}",
            )
            embed.set_author(name=ctx.message.author)
            embed.set_image(url=url)
            await ctx.reply(embed=embed, delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")

    @commands.command("summary")
    async def summary(self, ctx, *, topic):
        """
        Gets summary of a topic from wikipedia.
        """
        try:
            data = get_wikipedia_summary(topic)
            if not data:
                await ctx.reply(
                    "Sorry we can't find summary about that topic.",
                    delete_after=delete_seconds,
                )

            title, summary, url = data
            embed = discord.Embed(
                title=title,
                description=f"{summary.strip()}\nMore Info: {url}",
                color=discord.Colour.teal(),
                timestamp=datetime.datetime.utcnow(),
            )
            embed.set_author(name=ctx.message.author)
            await ctx.reply(embed=embed, delete_after=delete_seconds)
        except wikipedia.DisambiguationError as e:
            try:
                topic = e.options
                data = get_wikipedia_summary(str(topic[0]))
                if not data:
                    await ctx.reply(
                        "Sorry we can't find summary about that topic.",
                        delete_after=delete_seconds,
                    )

                title, summary, url = data
                embed = discord.Embed(
                    title=title,
                    description=f"{summary.strip()}\nMore Info: {url}",
                    color=discord.Colour.teal(),
                    timestamp=datetime.datetime.utcnow(),
                )
                embed.set_author(name=ctx.message.author)
                await ctx.reply(embed=embed, delete_after=delete_seconds)
            except Exception as e:
                logging.exception("Exception occurred")
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("unhex")
    async def unhex(self, ctx, *, hex_str):
        """
        Unhex the hex passed as argument.
        """
        try:
            ascii_val = unhex(hex_str)
            await ctx.reply(ascii_val, delete_after=delete_seconds)
        except UnicodeDecodeError:
            await ctx.reply("That isn't a valid hex", delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("rot")
    async def rot(self, ctx, *, text):
        """
        /rot "a message" Returns all 25 possible rotations for a message.
        """
        try:
            out = "```"
            for i in range(1, 26):
                rot = Caesar.decrypt(text, i)
                out += rot + "\n"
            out += "```"
            await ctx.reply(out, delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("rot13")
    async def rot13(self, ctx, *, text):
        """
        Decrypt and encrypt message in rot13.
        """
        try:
            rot13 = Rot13.encrypt(text)
            await ctx.reply(f"```{rot13}```", delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("rot47")
    async def rot47(self, ctx, *, text):
        """
        Decrypt and encrypt message in rot47.
        """
        try:
            rot47 = Rot47.encrypt(text)
            await ctx.reply(f"```{rot47}```", delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("hex")
    async def hex(self, ctx, *, text):
        """
        Hex the strings passed as arguments.
        """
        try:
            hex_string = binascii.hexlify(text.encode()).decode()
            await ctx.reply(hex_string, delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("base64", aliases=["b64"])
    async def base64(self, ctx, method, *, msg):
        """
        Encode or decode in base64.
        Usage: base64 [e|d] message.
        For method use "e" for encoding and "d" for decoding
        """
        if method[0] == "e":
            try:
                base64_encoded = base64.b64encode(msg.encode()).decode()
                await ctx.reply(f"```{base64_encoded}```", delete_after=delete_seconds)
            except Exception as e:
                logging.exception("Exception occurred")
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        elif method[0] == "d":
            try:
                base64_decoded = base64.b64decode(msg).decode()
                await ctx.reply(f"```{base64_decoded}```", delete_after=delete_seconds)
            except Exception as e:
                logging.exception("Exception occurred")
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        else:
            await ctx.reply(
                f"{method} is not a valid option", delete_after=delete_seconds
            )

    @commands.command("base32", aliases=["b32"])
    async def base32(self, ctx, method, *, msg):
        """
        Encode or decode in base32.
        Usage: base32 [e|d] message.
        For method use "e" for encoding and "d" for decoding
        """
        if method[0] == "e":
            try:
                base32_encoded = base64.b32encode(msg.encode()).decode()
                await ctx.reply(f"```{base32_encoded}```", delete_after=delete_seconds)
            except Exception as e:
                logging.exception("Exception occurred")
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        elif method[0] == "d":
            try:
                base32_decoded = base64.b32decode(msg).decode()
                await ctx.reply(f"```{base32_decoded}```", delete_after=delete_seconds)
            except Exception as e:
                logging.exception("Exception occurred")
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        else:
            await ctx.reply(
                f"{method} is not a valid option", delete_after=delete_seconds
            )

    @commands.command("cointoss")
    async def cointoss(self, ctx):
        """
        Flips a coin for you.
        """
        coin_faces = ["heads", "tails"]
        await ctx.reply(random.choice(coin_faces), delete_after=delete_seconds)

    @commands.command("poll")
    async def poll(self, ctx, title, *, options):
        """
        Create a poll. (maximum 9 options)
        Usage: /poll "question" "1st option" "2nd option"...
        """
        if len(options) > 9:
            await ctx.reply(
                "Sorry maximum 9 options are allowed in poll",
                delete_after=delete_seconds,
            )
        else:
            reactions = []
            description = ""

            for i, option in enumerate(options):
                description += f"{poll_emojis[i]} - {option}\n"
                reactions.append(poll_emojis[i])

            embed = discord.Embed(
                title=title,
                description=description,
                color=discord.Colour.blue(),
                timestamp=datetime.datetime.utcnow(),
            )
            embed.set_footer(text=f"Poll by {ctx.author.name}")
            embed.set_thumbnail(url=ctx.author.avatar_url)
            msg = await ctx.send(embed=embed)
            for reaction in reactions:
                try:
                    await msg.add_reaction(reaction)
                except Exception as e:
                    logging.exception("Exception occurred")

    @commands.command("url")
    async def url(self, ctx, method, *, msg):
        """
        Encode or decode in URL format.
        Usage: url [e|d] message.
        For method use "e" for encoding and "d" for decoding
        """
        if method[0] == "e":
            try:
                url_encoded = quote(msg)
                await ctx.reply(f"```{url_encoded}```", delete_after=delete_seconds)
            except Exception as e:
                logging.exception("Exception occurred")
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        elif method[0] == "d":
            try:
                url_decoded = unquote(msg)
                await ctx.reply(f"```{url_decoded}```", delete_after=delete_seconds)
            except Exception as e:
                logging.exception("Exception occurred")
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        else:
            await ctx.reply(
                f"{method} is not a valid option", delete_after=delete_seconds
            )

    @commands.command("binary")
    async def binary(self, ctx, method, *, msg):
        """
        Encode or decode in binary.
        Usage: binary [e|d] message.
        For method use "e" for encoding and "d" for decoding
        """
        if method[0] == "e":
            try:
                binary_encoded = "".join(format(ord(i), "08b") for i in msg)
                await ctx.reply(f"```{binary_encoded}```", delete_after=delete_seconds)
            except Exception as e:
                logging.exception("Exception occurred")
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        elif method[0] == "d":
            try:
                binary_int = int(msg, 2)
                byte_number = binary_int.bit_length() + 7 // 8
                binary_decoded = binary_int.to_bytes(byte_number, "big").decode()
                await ctx.reply(f"```{binary_decoded}```", delete_after=delete_seconds)
            except ValueError:
                await ctx.reply(
                    "Please supply a valid binary value to decode.",
                    delete_after=delete_seconds,
                )
            except Exception as e:
                logging.exception("Exception occurred")
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        else:
            await ctx.reply(
                f"{method} is not a valid option", delete_after=delete_seconds
            )

    @commands.command("reverse", aliases=["rev"])
    async def reverse(self, ctx, *, text):
        """
        Reverses the message.
        """
        try:
            await ctx.reply(text[::-1], delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("length", aliases=["len"])
    async def length(self, ctx, *, text):
        """
        Returns length of the message.
        """
        try:
            await ctx.reply(len(text), delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("counteach")
    async def counteach(self, ctx, *, text):
        """
        Counts the amount of characters in a text.
        """
        try:
            count = {}
            for char in text:
                if char in count:
                    count[char] += 1
                else:
                    count[char] = 1

            await ctx.reply(str(count), delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("chat")
    async def chat(self, ctx, *, text):
        try:
            response = chatbot(ctx.author.name, text)
            await ctx.reply(response, delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playing = False
        self.queue = []
        self.paused = False

    async def check_queue(self, ctx):
        if self.paused:
            return

        if self.queue:
            voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
            voice_client.stop()
            self.queue.pop(0)
            if self.queue:
                await ctx.invoke(self.bot.get_command("play"), url=self.queue[0][1])

    def _play(self, url, *args):
        if url:
            out = False
            url = url.strip() + " " + " ".join(args)
            url = url.strip()
            url = get_youtube_audio(url)
            if isinstance(url, Playlist):
                for i in list(url.video_urls):
                    self.queue.append(("y", i))
                out = f'Playlist "{url.title}"'
            elif isinstance(url, str):
                self.queue.append(("y", url))
                out = f'The Song "{url}"'

            return out

        else:
            lofi = get_lofi_music()
            self.queue.append(("l", lofi))
            return f'The song {lofi.get("title")}'

    @commands.command("play")
    async def play(self, ctx, url=None, *args):
        """
        Plays music in the Music channel.
        """
        try:
            voice = discord.utils.get(ctx.guild.voice_channels, name="Music")
            voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

            if voice_client == None:
                await voice.connect()
                voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

            embed = discord.Embed(
                title="Now playing",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow(),
            )
            embed.set_author(name=f"Requested by {ctx.author.display_name}")
            embed.set_footer(text="Playback Information")

            can_play = self._play(url, *args)

            if voice_client.is_playing():
                await ctx.reply(
                    f"{can_play} was added to the queue", delete_after=delete_seconds
                )
                return

            if can_play:
                song_info = self.queue[0]
                if song_info[0] == "y":
                    song_info = download_audio(song_info[1])
                    song = song_info["url"]
                    embed.add_field(name="Title", value=song_info["title"])
                    embed.add_field(name="Artist", value=song_info["artist"])
                    embed.set_image(url=song_info["thumbnail"])
                elif song_info[0] == "l":
                    song_info = song_info[1]
                    song = song_info["path"]
                    title = song_info.get("title")
                    image = song_info.get("image").get("path")
                    if title:
                        embed.add_field(name="Title", value=title)
                    if image:
                        embed.set_image(url=image)

                voice_client.play(
                    discord.FFmpegPCMAudio(song),
                    after=lambda error: self.bot.loop.create_task(
                        self.check_queue(ctx)
                    ),
                )
                self.playing = True
            else:
                await ctx.reply(
                    "Please input a valid youtube URL for playing audio",
                    delete_after=delete_seconds,
                )
                return

            await ctx.send(embed=embed, delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply(
                "Sorry something went wrong :(", delete_after=delete_seconds
            )

    @commands.command("leave")
    async def leave(self, ctx):
        """
        Stops currently playing music and leave from the Music channel.
        """
        self.queue = []
        try:
            voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
            try:
                await voice.disconnect()
            except:
                pass
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply("Sorry something wen wrong :(", delete_after=delete_seconds)

    @commands.command("pause")
    async def pause(self, ctx):
        """
        Pauses currently playing music in the Music channel.
        """
        try:
            voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
            if voice.is_playing():
                voice.pause()
                self.paused = True
            else:
                await ctx.reply(
                    "Currently no audio is playing.", delete_after=delete_seconds
                )
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply("Sorry something wen wrong :(", delete_after=delete_seconds)

    @commands.command("resume")
    async def resume(self, ctx):
        """
        Resumes currently paused music in the Music channel.
        """
        try:
            voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
            if voice.is_paused():
                voice.resume()
                self.paused = False
            else:
                await ctx.reply("The audio is not paused.", delete_after=delete_seconds)
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply("Sorry something wen wrong :(", delete_after=delete_seconds)

    @commands.command("stop")
    async def stop(self, ctx):
        """
        Stops currently playing music in the Music channel.
        """
        try:
            voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
            voice.stop()
            self.queue = []
        except Exception as e:
            logging.exception("Exception occurred")
            await ctx.reply("Sorry something wen wrong :(", delete_after=delete_seconds)


class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quiz_api = "https://opentdb.com/api.php"
        self.difficulty_colors = {
            "easy": discord.Color.green(),
            "medium": discord.Color.gold(),
            "hard": discord.Color.red(),
        }
        self.have_a_quiz = False

    def get_random_quiz(self):
        data = requests.get(
            self.quiz_api, params={"amount": 1, "type": "multiple"}
        ).json()
        result = data.get("results")[0]
        category = result.get("category")
        difficulty = result.get("difficulty")
        question = html.unescape(result.get("question"))
        answer = html.unescape(result.get("correct_answer"))
        incorrect_answers = result.get("incorrect_answers")
        options = [html.unescape(option) for option in [answer] + incorrect_answers]
        random.shuffle(options)
        answer_num = options.index(answer) + 1
        qs = question + "\n"
        for i, option in enumerate(options):
            qs += f"{i+1}) {option}\n"
        qs = qs.strip()
        return category, difficulty, qs, answer_num, answer

    @commands.command("quiz")
    async def quiz(self, ctx):
        """
        Asks you a random question. You can answer with the number corresponding to the answer.
        """
        if self.have_a_quiz:
            return await ctx.reply("You can't have 2 quizes at a time.")

        message = ctx.message
        category, difficulty, qs, ans_num, ans = self.get_random_quiz()
        color = self.difficulty_colors.get(difficulty.lower(), discord.Color.blue())

        embed = discord.Embed(
            title=f"Quiz about {category}",
            description=qs,
            color=color,
            timestamp=datetime.datetime.utcnow(),
        )

        await message.channel.send(embed=embed, delete_after=delete_seconds)
        self.have_a_quiz = True

        def check(m):
            return m.author == message.author and m.content.isdigit()

        try:
            guess = await self.bot.wait_for(
                "message", check=check, timeout=delete_seconds
            )
        except asyncio.TimeoutError:
            return await ctx.reply(
                "Sorry you took a long time to respond", delete_after=delete_seconds
            )

        if int(guess.content) == ans_num:
            await ctx.send("You are right!", delete_after=delete_seconds)
        else:
            await ctx.send(
                f'That\'s incorrect! The correct answer was "{ans}"',
                delete_after=delete_seconds,
            )
        self.have_a_quiz = False


bot.add_cog(CTF(bot))
bot.add_cog(Miscellaneous(bot))
bot.add_cog(Music(bot))
bot.add_cog(Quiz(bot))


def main():
    bot.run(DISCORD_API_KEY)


if __name__ == "__main__":
    main()

