import base64
import binascii
import datetime
import os
import random
import string
from urllib.parse import quote, unquote, urlparse, parse_qs

import discord
import requests
from discord.ext import commands
from pytube import YouTube, Search, Playlist
from pytube.exceptions import LiveStreamError

DISCORD_API_KEY = os.environ.get("DISCORD_API_KEY")

events_url = "https://ctftime.org/api/v1/events/"
quote_url = "https://api.quotable.io/random"
joke_url = "https://meme-api.herokuapp.com/gimme/"
lofi_url = "https://lofi-api.herokuapp.com/v1/track"

headers = {"User-Agent": "Mozilla/5.0"}
poll_emojis = ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣"]

delete_seconds = 300

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
            return get_youtube_audio(url, index+1)
        except:
            if "youtube.com" not in url:
                s = get_youtube_audio(f"https://www.youtube.com/watch?v={url}")
            if not s:
                return



def download_audio(url):
    if isinstance(url, YouTube):
        s = url
        audios = s.streams.filter(mime_type="audio/mp4", only_audio=True).order_by("abr")
        song = audios[-1]
        return {"title": s.title, "thumbnail": s.thumbnail_url, "artist": s.author, "url": song.url}
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
    return {"title": s.title, "thumbnail": s.thumbnail_url, "artist": s.author, "url": song.url}


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
async def on_message(ctx):
    print(ctx)

class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command("upcoming-ctfs")
    async def cmd_upcoming_ctfs(self, ctx, num=2):
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
    async def cmd_quote(self, ctx):
        """
        Get random quote
        """
        quote = get_random_quote()
        content = quote.get("content")
        author = quote.get("author")
        embed = discord.Embed(
            title=content, description=f"**{author}**", color=discord.Colour.green()
        )
        await ctx.reply(embed=embed, delete_after=delete_seconds)


    @commands.command("joke")
    async def cmd_joke(self, ctx):
        """
        Gets a random joke from reddit.
        """
        joke = get_random_joke()
        title = joke.get("title")
        if title:
            await ctx.reply(title, delete_after=delete_seconds)
        await ctx.reply(joke.get("url"), delete_after=delete_seconds)


    @commands.command("unhex")
    async def cmd_unhex(self, ctx, *hex_str):
        """
        Unhex the hex passed as argument.
        """
        try:
            ascii_val = unhex(*hex_str)
            await ctx.reply(ascii_val, delete_after=delete_seconds)
        except UnicodeDecodeError:
            await ctx.reply("That isn't a valid hex", delete_after=delete_seconds)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=delete_seconds)


    @commands.command("rot")
    async def cmd_rot(self, ctx, *text):
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
            await ctx.reply(out, delete_after=delete_seconds)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=delete_seconds)


    @commands.command("rot13")
    async def cmd_rot13(self, ctx, *text):
        """
        Decrypt and encrypt message in rot13.
        """
        text = " ".join(text).replace("`", "")
        try:
            rot13 = Rot13.encrypt(text)
            await ctx.reply(f"```{rot13}```", delete_after=delete_seconds)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=delete_seconds)


    @commands.command("rot47")
    async def cmd_rot47(self, ctx, *text):
        """
        Decrypt and encrypt message in rot47.
        """
        text = " ".join(text).replace("`", "")
        try:
            rot47 = Rot47.encrypt(text)
            await ctx.reply(f"```{rot47}```", delete_after=delete_seconds)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=delete_seconds)


    @commands.command("hex")
    async def cmd_hex(self, ctx, *text):
        """
        Hex the strings passed as arguments.
        """
        text = " ".join(text).replace("`", "")
        try:
            hex_string = binascii.hexlify(text.encode()).decode()
            await ctx.reply(hex_string, delete_after=delete_seconds)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=delete_seconds)


    @commands.command("base64", aliases=["b64"])
    async def cmd_base64(self, ctx, method, *msg):
        """
        Encode or decode in base64.
        Usage: base64 [e|d] message.
        For method use "e" for encoding and "d" for decoding
        """
        msg = " ".join(msg).replace("`", "")
        if method[0] == "e":
            try:
                base64_encoded = base64.b64encode(msg.encode()).decode()
                await ctx.reply(f"```{base64_encoded}```", delete_after=delete_seconds)
            except:
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        elif method[0] == "d":
            try:
                base64_decoded = base64.b64decode(msg).decode()
                await ctx.reply(f"```{base64_decoded}```", delete_after=delete_seconds)
            except:
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        else:
            await ctx.reply(f"{method} is not a valid option", delete_after=delete_seconds)


    @commands.command("base32", aliases=["b32"])
    async def cmd_base32(self, ctx, method, *msg):
        """
        Encode or decode in base32.
        Usage: base32 [e|d] message.
        For method use "e" for encoding and "d" for decoding
        """
        msg = " ".join(msg).replace("`", "")
        if method[0] == "e":
            try:
                base32_encoded = base64.b32encode(msg.encode()).decode()
                await ctx.reply(f"```{base32_encoded}```", delete_after=delete_seconds)
            except:
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        elif method[0] == "d":
            try:
                base32_decoded = base64.b32decode(msg).decode()
                await ctx.reply(f"```{base32_decoded}```", delete_after=delete_seconds)
            except:
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        else:
            await ctx.reply(f"{method} is not a valid option", delete_after=delete_seconds)


    @commands.command("cointoss")
    async def cmd_cointoss(self, ctx):
        """
        Flips a coin for you.
        """
        coin_faces = ["heads", "tails"]
        await ctx.reply(random.choice(coin_faces), delete_after=delete_seconds)


    @commands.command("poll")
    async def cmd_poll(self, ctx, title, *options):
        """
        Create a poll. (maximum 9 options)
        Usage: /poll "question" "1st option" "2nd option"...
        """
        if len(options) > 9:
            await ctx.reply(
                "Sorry maximum 9 options are allowed in poll", delete_after=delete_seconds
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
                except:
                    pass


    @commands.command("url")
    async def cmd_url(self, ctx, method, *msg):
        """
        Encode or decode in URL format.
        Usage: url [e|d] message.
        For method use "e" for encoding and "d" for decoding
        """
        msg = " ".join(msg).replace("`", "")
        if method[0] == "e":
            try:
                url_encoded = quote(msg)
                await ctx.reply(f"```{url_encoded}```", delete_after=delete_seconds)
            except:
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        elif method[0] == "d":
            try:
                url_decoded = unquote(msg)
                await ctx.reply(f"```{url_decoded}```", delete_after=delete_seconds)
            except:
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        else:
            await ctx.reply(f"{method} is not a valid option", delete_after=delete_seconds)


    @commands.command("binary")
    async def cmd_binary(self, ctx, method, *msg):
        """
        Encode or decode in binary.
        Usage: binary [e|d] message.
        For method use "e" for encoding and "d" for decoding
        """
        msg = " ".join(msg).replace("`", "")
        if method[0] == "e":
            try:
                binary_encoded = "".join(format(ord(i), "08b") for i in msg)
                await ctx.reply(f"```{binary_encoded}```", delete_after=delete_seconds)
            except:
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
            except:
                await ctx.reply(
                    "Sorry something went wrong :(", delete_after=delete_seconds
                )
        else:
            await ctx.reply(f"{method} is not a valid option", delete_after=delete_seconds)


    @commands.command("reverse", aliases=["rev"])
    async def cmd_reverse(self, ctx, *text):
        """
        Reverses the message.
        """
        text = " ".join(text).replace("`", "")
        try:
            await ctx.reply(text[::-1], delete_after=delete_seconds)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=delete_seconds)


    @commands.command("length", aliases=["len"])
    async def cmd_length(self, ctx, *text):
        """
        Returns length of the message.
        """
        text = " ".join(text).replace("`", "")
        try:
            await ctx.reply(len(text), delete_after=delete_seconds)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=delete_seconds)


    @commands.command("counteach")
    async def cmd_counteach(self, ctx, *text):
        """
        Counts the amount of characters in a text.
        """
        text = " ".join(text).replace("`", "")
        try:
            count = {}
            for char in text:
                if char in count:
                    count[char] += 1
                else:
                    count[char] = 1

            await ctx.reply(str(count), delete_after=delete_seconds)
        except:
            await ctx.reply("Sorry something went wrong :(", delete_after=delete_seconds)



class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playing = False
        self.queue = []
        self.paused = False

    async def check_queue(self,ctx):
        if self.paused:
            return

        if self.queue:
            voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
            voice_client.stop()
            self.queue.pop(0)
            if self.queue:
                await ctx.invoke(self.bot.get_command('play'), url=self.queue[0][1])

    def _play(self, url, *args):
        if url:
            out = False
            url = url.strip() + " " + " ".join(args)
            url = url.strip()
            url = get_youtube_audio(url)
            if isinstance(url, Playlist):
                for i in list(url.video_urls):
                    self.queue.append(("y", i))
                out = f"Playlist \"{url.title}\""
            elif isinstance(url, str):
                self.queue.append(("y", url))
                out = f"The Song \"{url}\""

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

            embed = discord.Embed(title="Now playing", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
            embed.set_author(name=f"Requested by {ctx.author.display_name}")
            embed.set_footer(text="Playback Information")

            can_play = self._play(url, *args)

            if voice_client.is_playing():
                await ctx.reply(f"{can_play} was added to the queue", delete_after=delete_seconds)
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

                voice_client.play(discord.FFmpegPCMAudio(song), after=lambda error: self.bot.loop.create_task(self.check_queue(ctx)))
                self.playing = True
            else:
                await ctx.reply("Please input a valid youtube URL for playing audio", delete_after=delete_seconds)
                return

            await ctx.send(embed=embed, delete_after=delete_seconds)
        except Exception as e:
            print(e)
            raise e
            await ctx.reply("Sorry something went wrong :(", delete_after=delete_seconds)


    @commands.command("leave")
    async def leave(self, ctx):
        """
        Stops currently playing music and leave from the Music channel.
        """
        self.queue = None
        try:
            voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
            try:
                await voice.disconnect()
            except:
                pass
        except:
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
                await ctx.reply("Currently no audio is playing.", delete_after=delete_seconds)
        except:
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
        except:
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
        except:
            await ctx.reply("Sorry something wen wrong :(", delete_after=delete_seconds)


bot.add_cog(CTF(bot))
bot.add_cog(Miscellaneous(bot))
bot.add_cog(Music(bot))

bot.run(DISCORD_API_KEY)
