from discord.ext import commands
import discord
import requests
import datetime
import os

DISCORD_API_KEY = os.environ.get("DISCORD_API_KEY")
events_url = "https://ctftime.org/api/v1/events/"
headers = {"User-Agent": "Mozilla/5.0"}

bot = commands.Bot(command_prefix="/")

def get_upcoming_ctfs(limit=2):
    res = requests.get(events_url, params={"limit": limit}, headers=headers)
    return res.json()


@bot.command("upcoming-ctfs")
async def upcoming_ctfs(ctx, num=2):
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
            await ctx.send(embed=embed)


bot.run(DISCORD_API_KEY)
