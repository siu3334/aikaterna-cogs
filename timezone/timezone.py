from datetime import datetime, timedelta

import discord
from pytz import all_timezones, country_timezones, timezone
from rapidfuzz import process
from redbot.core import Config, commands
from redbot.core.commands import BadArgument, Converter

from serverstats.converters import FuzzyMember


class TimezoneConverter(Converter):
    """Timezone Converter helper class."""

    async def convert(self, ctx: commands.Context, argument: str) -> str:
        fuzzy = process.extractOne(argument, all_timezones, score_cutoff=90)
        if not fuzzy:
            raise BadArgument(
                "That doesn't look like a valid timezone or a major city name. If you're having"
                " difficulty, got to https://whatismyti.me to quickly get your timezone."
            )

        return fuzzy[0]


class Timezone(commands.Cog):
    """Gets times of other users or across the world..."""

    __version__ = "2.1.0"

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Thanks Sinbad!"""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 278049241001, force_registration=True)
        default_user = {"usertime": None}
        self.config.register_user(**default_user)

    async def get_usertime(self, user: discord.abc.User):
        tz = None
        usertime = await self.config.user(user).usertime()
        if usertime:
            tz = timezone(usertime)

        return usertime, tz

    @commands.group(invoke_without_command=True)
    async def time(self, ctx, *, user: FuzzyMember = None):
        """
        Returns your time and timezone or of a user, if specified.

        For the list of supported timezones, see here:
        https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        """
        member: discord.Member = user[0] if user else ctx.author

        if member.bot:
            return await ctx.send("Bots technically do not have a timezone. LOL!")

        usertime, user_tz = await self.get_usertime(member)
        who = f"**{member}**" if member.id != ctx.author.id else "You"
        if not usertime:
            return await ctx.send(
                f"{who} need to set a timezone first with `;mytime continent/city` command!"
            )

        time = datetime.now(user_tz)
        strf_time = time.strftime("**%I:%M %p** (%Z) on `%d/%m/%Y`")
        to_send = f"**{member.name}**'s current time is {strf_time}"

        cmduser_time, cmduser_tz = await self.get_usertime(ctx.author)
        if cmduser_time and cmduser_tz and member.id != ctx.author.id:
            cmduser_now = datetime.now(cmduser_tz).utcoffset()
            assert isinstance(cmduser_now, timedelta)
            cmduser_diff = cmduser_now.total_seconds() / 60 / 60
            user_diff = time.utcoffset().total_seconds() / 60 / 60
            time_diff = abs(cmduser_diff - user_diff)
            time_amt = "same timezone as" if time_diff == 0 else f"**{time_diff}h"
            pos = "ahead** of" if cmduser_diff < user_diff else "behind**"
            pos_text = " you" if time_diff == 0 else f" {pos} you"
            to_send += f" ({time_amt}{pos_text})"

        mentions = discord.AllowedMentions.none()
        await ctx.send(to_send, allowed_mentions=mentions)

    @time.command()
    async def tz(self, ctx, *, tz: TimezoneConverter = None):
        """Gets the time in any timezone."""
        fmt = "**%I:%M %p (%Z)** on **%a, %d %B, %Y**"
        if tz is None:
            time = datetime.now()
            return await ctx.send(f"My current system time is {time.strftime(fmt)}")

        time = datetime.now(timezone(tz))
        return await ctx.send(time.strftime(fmt))

    @time.command()
    async def iso(self, ctx, code: str):
        """Looks up ISO3166 country code and gives you supported timezones.

        List of ISO3166 country codes:
        https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
        """
        exist = True if code in country_timezones else False
        if exist:
            tz = iter(country_timezones(code))
            xx = "\n‣ ".join(str(x) for x in sorted(tz))
            msg = (
                f"Supported timezones for **{code}:**\n\n‣ {xx}\n\n"
                f"Use `{ctx.clean_prefix}time tz Continent/City` to show time in that timezone."
            )
            await ctx.send(msg)
        else:
            await ctx.maybe_send_embed(
                "You need to provide a valid [ISO 3166 country code]"
                "(https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes)."
            )

    @commands.command()
    async def mytime(self, ctx, *, tz: TimezoneConverter = None):
        """
        Sets or returns your timezone if already set.

        You can set your time/timezone with following:

        Usage: `[p]mytime Continent/City`
        Pro Tip: Easily get your time(zone) from https://whatismyti.me to use with this command.
        """
        if tz is None:
            usertime, tz = await self.get_usertime(ctx.author)
            if not usertime:
                return await ctx.send_help()

            time = datetime.now(tz)
            strf_time = time.strftime("**%I:%M %p (%Z)** on **%a, %d %B, %Y**")
            msg = f"**{ctx.author.name}**, your current time is {strf_time}."
            return await ctx.send(msg)
        else:
            await self.config.user(ctx.author).usertime.set(tz.title())
            await ctx.send(f"Successfully set your timezone to **{tz}**.")

    @commands.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_guild=True)
    async def timeset(self, ctx, user: discord.Member, *, tz: TimezoneConverter):
        """Allows the server mods/admins to set a member's timezone."""
        if user.bot:
            return await ctx.send("Nice try, bots technically do not have a timezone!")
        await self.config.user(user).usertime.set(tz.title())
        await ctx.send(f"Successfully set **{user.name}**'s timezone to **{tz.title()}**.")
