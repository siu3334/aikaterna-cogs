import discord
import pytz

from datetime import datetime
from typing import Literal

from redbot.core import Config, commands

from .converter import FuzzyMember, TimezoneConverter


class Timezone(commands.Cog):
    """Gets times across the world..."""

    __version__ = "2.1.0"

    async def red_delete_data_for_user(
        self, *, requester: Literal["discord", "owner", "user", "user_strict"], user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 278049241001, force_registration=True)
        default_user = {"usertime": None}
        self.config.register_user(**default_user)

    async def get_usertime(self, user: discord.User):
        tz = None
        usertime = await self.config.user(user).usertime()
        if usertime:
            tz = pytz.timezone(usertime)

        return usertime, tz

    @commands.group(invoke_without_command=True)
    async def time(self, ctx, *, user: FuzzyMember = None):
        """
        Returns your time and timezone or of a user, if specified.

        For the list of supported timezones, see here:
        https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        """
        user = user or ctx.author

        if user.bot:
            return await ctx.send("Bots technically do not have a timezone. LOL!")

        usertime, tz = await self.get_usertime(user)
        who = f"**{user}**" if user is not ctx.author else "You"
        if not usertime:
            return await ctx.send(f"{who} need to set a timezone first!")

        time = datetime.now(tz)
        fmt = "**%I:%M %p (%Z)** on **%a, %d %B, %Y**"
        time = time.strftime(fmt)
        to_send = f"The current time for **{user.name}** is {str(time)}."
        await ctx.send(to_send)

    @time.command()
    async def tz(self, ctx, *, tz: TimezoneConverter = None):
        """Gets the time in any timezone."""
        fmt = "**%I:%M %p (%Z)** on **%a, %d %B, %Y**"
        if tz is None:
            time = datetime.now()
            return await ctx.send(f"My current system time is {time.strftime(fmt)}")

        time = datetime.now(pytz.timezone(tz))
        return await ctx.send(time.strftime(fmt))

    @time.command()
    async def iso(self, ctx, code: str):
        """
        Looks up ISO3166 country code and gives you supported timezones.

        List of ISO3166 country codes:
        https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
        """
        exist = True if code in pytz.country_timezones else False
        if exist:
            tz = iter(pytz.country_timezones(code))
            xx = "\n‣ ".join(str(x) for x in sorted(tz))
            msg = (
                f"Supported timezones for **{code}:**\n\n‣ {xx}\n\n"
                + f"Use `{ctx.clean_prefix}time tz Continent/City` "
                + "to display the current time in that timezone."
            )
            return await ctx.send(msg)
        else:
            await ctx.maybe_send_embed(
                "You need to provide a valid [ISO 3166 country code]"
                + "(https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes)."
            )

    @time.command()
    async def me(self, ctx, *, tz: TimezoneConverter = None):
        """
        Sets or returns your timezone if already set.

        You can set your time/timezone with following:

        Usage: [p]time me Continent/City
        Pro Tip: Easily get your time(zone) from https://whatismyti.me to use with this command.
        """
        if tz is None:
            usertime, tz = await self.get_usertime(ctx.author)
            if not usertime:
                return await ctx.send(f"You haven't set your timezone! See command help on how to.")

            time = datetime.now(tz)
            time = time.strftime("**%I:%M %p (%Z)** on **%a, %d %B, %Y**")
            msg = f"**{ctx.author.name}**, your current time is {time}."
            return await ctx.send(msg)
        else:
            await self.config.user(ctx.author).usertime.set(tz.title())
            await ctx.send(f"Successfully set your timezone to **{tz}**.")

    @time.command()
    @commands.mod_or_permissions(manage_guild=True)
    async def set(self, ctx, user: FuzzyMember, *, tz: TimezoneConverter):
        """Allows the server mods/admins to set a member's timezone."""
        if user.bot:
            return await ctx.send("Nice try LOL, but bots technically do not have a timezone!")
        await self.config.user(user).usertime.set(tz.title())
        await ctx.send(f"Successfully set **{user.name}**'s timezone to **{tz.title()}**.")

    @time.command()
    async def compare(self, ctx, *, user: FuzzyMember):
        """Compare your saved timezone with another user's timezone."""
        usertime, user_tz = await self.get_usertime(ctx.author)
        if not usertime:
            return await ctx.send(f"**{ctx.author.name}**, you haven't set your timezone!")
        othertime, other_tz = await self.get_usertime(user)
        if not othertime:
            return await ctx.send(f"**{user.name}** haven't set their timezone!")

        user_now = datetime.now(user_tz)
        user_diff = user_now.utcoffset().total_seconds() / 60 / 60
        other_now = datetime.now(other_tz)
        other_diff = other_now.utcoffset().total_seconds() / 60 / 60
        time_diff = abs(user_diff - other_diff)
        fmt = "**%I:%M %p (%Z)** on **%a, %d %B, %Y**"
        other_time = other_now.strftime(fmt)
        plural = "" if time_diff == 1 else "s"
        time_amt = "the same timezone as you" if time_diff == 0 else f"**{time_diff} hour{plural}**"
        pos = "__ahead__ of" if user_diff < other_diff else "__behind__"
        pos_text = "" if time_diff == 0 else f" {pos} you"
        msg = f"The current time for **{user.name}** is {other_time}, which is {time_amt}{pos_text}."
        await ctx.send(msg)

    @time.command(hidden=True)
    async def version(self, ctx):
        """Show the cog version."""
        await ctx.send(f"Timezone Cog version: {self.__version__}.")
