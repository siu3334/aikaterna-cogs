# This converter is taken from TrustyJAID's serverstats cog
# All credits goes to TrustyJAID and not me
import re
from typing import List

import discord
from unidecode import unidecode

from rapidfuzz import fuzz, process
from discord.ext.commands.converter import IDConverter, _get_from_guilds
from discord.ext.commands.errors import BadArgument

from redbot.core import commands


class FuzzyMember(IDConverter):
    """
    This will accept partial names, user IDs, mentions,
    and perform a fuzzy search for members within the guild
    and return a list of member objects matching input argument.

    Guidance code on how to do this from:
    https://github.com/Rapptz/discord.py/blob/rewrite/discord/ext/commands/converter.py#L85
    https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/mod/mod.py#L24
    """

    async def convert(self, ctx: commands.Context, argument: str) -> List[discord.Member]:
        bot = ctx.bot
        match = self._get_id_match(argument) or re.match(r"<@!?([0-9]+)>$", argument)
        result = []
        if match:
            user_id = int(match.group(1))
            if ctx.guild:
                result.append(ctx.guild.get_member(user_id))
            else:
                result.append(_get_from_guilds(bot, "get_member", user_id))
        else:
            members = {m: unidecode(m.name) for m in ctx.guild.members}
            for m in process.extract(
                argument,
                members,
                scorer=fuzz.WRatio,
                limit=None,
                score_cutoff=75,
            ):
                result.append(m[2])

            nicknames = {m: unidecode(m.nick) for m in ctx.guild.members if m.nick and m not in result}
            for m in process.extract(
                argument,
                nicknames,
                scorer=fuzz.WRatio,
                limit=None,
                score_cutoff=75,
            ):
                result.append(m[2])

        if not result or result == [None]:
            raise BadArgument(f"Member `{argument}` not found.")

        return result


class GuildConverter(IDConverter):
    """
    This is a guild converter for fuzzy guild names which is used throughout
    this cog to search for guilds by part of their name and will also
    accept guild ID's

    Guidance code on how to do this from:
    https://github.com/Rapptz/discord.py/blob/rewrite/discord/ext/commands/converter.py#L85
    https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/mod/mod.py#L24
    """

    async def convert(self, ctx: commands.Context, argument: str) -> discord.Guild:
        bot = ctx.bot
        match = self._get_id_match(argument)
        result = None
        if not await bot.is_owner(ctx.author):
            # Don't need normies to be snooping other guilds unless bot owner.
            raise BadArgument("That option is only available for the bot owner.")
        if match:
            result = bot.get_guild(int(match.group(1)))
        else:
            guilds = {g: unidecode(g.name) for g in bot.guilds}
            match, score, guild = process.extractOne(argument, guilds, scorer=fuzz.WRatio, score_cutoff=75)
            result = guild

        if result is None:
            raise BadArgument(f"Guild `{argument}` not found.")

        return result
