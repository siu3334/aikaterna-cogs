import asyncio
import datetime
import inspect
import logging
import re
from contextlib import suppress as sps
from typing import Union

import discord
from dateutil import relativedelta
from redbot.core import commands
from redbot.core.utils.chat_formatting import bold, box, escape, pagify
from redbot.core.utils.common_filters import filter_invites
from redbot.core.utils.menus import DEFAULT_CONTROLS, close_menu, menu
from redbot.core.utils.xmenus import BaseMenu, ListPages
from tabulate import tabulate

from serverstats.converters import FuzzyMember, FuzzyRole, GuildConverter

log = logging.getLogger("red.aikaterna.tools")


class Tools(commands.Cog):
    """Mod and Admin utility tools."""

    def __init__(self, bot):
        self.bot = bot
        self.tick = "<:xcheck:847024581579505665>"

    @commands.guild_only()
    @commands.group()
    async def access(self, ctx: commands.Context):
        """Check channel access"""
        pass

    @access.command()
    async def compare(self, ctx: commands.Context, user: discord.Member):
        """Compare channel access with another server member."""
        tcs = ctx.guild.text_channels
        vcs = ctx.guild.voice_channels

        author_text_channels = [c for c in tcs if c.permissions_for(ctx.author).read_messages is True]
        author_voice_channels = [c for c in vcs if c.permissions_for(ctx.author).connect is True]

        user_text_channels = [c for c in tcs if c.permissions_for(user).read_messages is True]
        user_voice_channels = [c for c in vcs if c.permissions_for(user).connect is True]

        author_only_t = set(author_text_channels) - set(
            user_text_channels
        )  # text channels only the author has access to
        author_only_v = set(author_voice_channels) - set(
            user_voice_channels
        )  # voice channels only the author has access to

        user_only_t = set(user_text_channels) - set(author_text_channels)  # text channels only the user has access to
        user_only_v = set(user_voice_channels) - set(
            author_voice_channels
        )  # voice channels only the user has access to

        common_t = list(
            set([c for c in tcs]) - author_only_t - user_only_t
        )  # text channels that author and user have in common
        common_v = list(
            set([c for c in vcs]) - author_only_v - user_only_v
        )  # voice channels that author and user have in common

        msg = "```ini\n"
        msg += "{} [TEXT CHANNELS IN COMMON]:\n\n{}\n\n".format(len(common_t), ", ".join([c.name for c in common_t]))
        msg += "{} [TEXT CHANNELS {} HAS EXCLUSIVE ACCESS TO]:\n\n{}\n\n".format(
            len(user_only_t), user.name.upper(), ", ".join([c.name for c in user_only_t])
        )
        msg += "{} [TEXT CHANNELS YOU HAVE EXCLUSIVE ACCESS TO]:\n\n{}\n\n\n".format(
            len(author_only_t), ", ".join([c.name for c in author_only_t])
        )
        msg += "{} [VOICE CHANNELS IN COMMON]:\n\n{}\n\n".format(len(common_v), ", ".join([c.name for c in common_v]))
        msg += "{} [VOICE CHANNELS {} HAS EXCLUSIVE ACCESS TO]:\n\n{}\n\n".format(
            len(user_only_v), user.name.upper(), ", ".join([c.name for c in user_only_v])
        )
        msg += "{} [VOICE CHANNELS YOU HAVE EXCLUSIVE ACCESS TO]:\n\n{}\n\n".format(
            len(author_only_v), ", ".join([c.name for c in author_only_v])
        )
        msg += "```"
        for page in pagify(msg, delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @access.command()
    async def text(self, ctx: commands.Context, user: discord.Member):
        """Check text channel access."""
        can_access = [c.name for c in ctx.guild.text_channels if c.permissions_for(user).read_messages is True]
        text_channels = [c.name for c in ctx.guild.text_channels]

        prefix = "You have" if user.id == ctx.author.id else user.name + " has"
        msg = "```ini\n[{} access to {} out of {} text channels]\n\n".format(
            prefix, len(can_access), len(text_channels)
        )

        msg += "[ACCESS]:\n{}\n\n".format(", ".join(can_access))
        msg += "[NO ACCESS]:\n{}\n```".format(", ".join(list(set(text_channels) - set(can_access))))
        for page in pagify(msg, delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @access.command()
    async def voice(self, ctx: commands.Context, user: discord.Member):
        """Check voice channel access."""
        can_access = [c.name for c in ctx.guild.voice_channels if c.permissions_for(user).connect is True]
        voice_channels = [c.name for c in ctx.guild.voice_channels]

        prefix = "You have" if user.id == ctx.author.id else user.name + " has"
        msg = "```ini\n[{} access to {} out of {} voice channels]\n\n".format(
            prefix, len(can_access), len(voice_channels)
        )

        msg += "[ACCESS]:\n{}\n\n".format(", ".join(can_access))
        msg += "[NO ACCESS]:\n{}\n```".format(", ".join(list(set(voice_channels) - set(can_access))))
        for page in pagify(msg, delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @commands.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_guild=True)
    async def banlist(self, ctx: commands.Context):
        """Displays the server's banlist."""
        banlist = await ctx.guild.bans()
        bancount = len(banlist)
        ban_list = []
        if bancount == 0:
            return await ctx.send("No users are currently banned from this server.")
        else:
            msg = ""
            for user_obj in banlist:
                user_name = f"{user_obj.user.name}#{user_obj.user.discriminator}"
                msg += f"`{user_obj.user.id}` - {user_name}\n"

        banlist = sorted(msg)
        pages = []
        for page in pagify(msg, delims=["\n"], page_length=2000):
            embed = discord.Embed(
                description=page,
                colour=await ctx.embed_colour(),
            )
            embed.set_footer(text=f"Total bans: {bancount}")
            pages.append(embed)
        await menu(ctx, pages, DEFAULT_CONTROLS)

    @commands.command()
    @commands.guild_only()
    async def chinfo(self, ctx: commands.Context, channel: Union[int, discord.abc.GuildChannel] = None):
        """Shows channel information. Defaults to current text channel."""
        channel = self.bot.get_channel(channel) if isinstance(channel, int) else channel
        channel = channel or ctx.channel
        guild = channel.guild

        yesno = {True: "Yes", False: "No"}
        typemap = {
            discord.TextChannel: "Text Channel",
            discord.VoiceChannel: "Voice Channel",
            discord.CategoryChannel: "Category",
        }

        with sps(Exception):
            caller = inspect.currentframe().f_back.f_code.co_name.strip()

        data = ""
        if caller == "invoke" or channel.guild != ctx.guild:
            data += f"[Server]       : {channel.guild.name}\n"
        data += f"[Name]         : {escape(str(channel))}\n"
        data += f"[ID]           : {channel.id}\n"
        if isinstance(channel, discord.TextChannel) and channel.topic != "":
            data += f"[Topic]        : {channel.topic}\n"
        data += f"[Position]     : {channel.position}\n"
        data += f"[Created]      : {self._humanize_time(channel.created_at)} ago\n"
        data += f"[Type]         : {typemap[type(channel)]}\n"
        if isinstance(channel, discord.VoiceChannel):
            data += f"[Users]        : {len(channel.members)}\n"
            data += f"[User limit]   : {channel.user_limit}\n"
            data += f"[Bitrate]      : {channel.bitrate / 1000} Kbps\n"
        await ctx.send(box(data, lang="ini"))

    @commands.command()
    @commands.guild_only()
    async def eid(self, ctx: commands.Context, emoji: discord.Emoji):
        """Get an id for an emoji."""
        await ctx.send(f"{emoji}:{emoji.id}")

    @commands.command()
    @commands.guild_only()
    async def einfo(self, ctx: commands.Context, emoji: discord.Emoji):
        """Emoji information."""
        e = emoji
        m = (
            f"{str(e)}\n"
            f"```ini\n"
            f"[NAME]    :   {e.name}\n"
            f"[GUILD]   :   {e.guild}\n"
            f"[URL]     :   {e.url}\n"
            f"[ANIMATED]:   {e.animated}"
            "```"
        )
        await ctx.send(m)

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(add_reactions=True, embed_links=True)
    async def inrole(self, ctx: commands.Context, *, rolename):
        """Check members in the role specified."""
        guild = ctx.guild
        if rolename.startswith("<@&"):
            role_id = int(re.search(r"<@&(.{18})>$", rolename)[1])
            role = discord.utils.get(ctx.guild.roles, id=role_id)
        elif len(rolename) in [17, 18] and rolename.isdigit():
            role = discord.utils.get(ctx.guild.roles, id=int(rolename))
        else:
            role = discord.utils.find(lambda r: r.name.lower() == rolename.lower(), guild.roles)

        if role is None:
            roles = []
            for r in guild.roles:
                if rolename.lower() in r.name.lower():
                    roles.append(r)

            if len(roles) == 1:
                role = roles[0]
            elif len(roles) < 1:
                await ctx.send("No roles were found.")
                return
            else:
                msg = (
                    f"**{len(roles)} roles found with** `{rolename}` **in the name.**\n"
                    f"Type the number of the role you wish to see.\n\n"
                )
                tbul8 = []
                for num, role in enumerate(roles):
                    tbul8.append([num + 1, role.name])
                m1 = await ctx.send(msg + tabulate(tbul8, tablefmt="plain"))

                def check(m):
                    if (m.author == ctx.author) and (m.channel == ctx.channel):
                        return True

                try:
                    response = await self.bot.wait_for("message", check=check, timeout=25)
                except asyncio.TimeoutError:
                    await m1.delete()
                    return
                if not response.content.isdigit():
                    await m1.delete()
                    return
                else:
                    response = int(response.content)

                if response not in range(0, len(roles) + 1):
                    return await ctx.send("Cancelled.")
                elif response == 0:
                    return await ctx.send("Cancelled.")
                else:
                    role = roles[response - 1]

        embed = discord.Embed(
            description="Getting member names...",
            colour=await ctx.embed_colour(),
        )
        awaiter = await ctx.send(embed=embed)
        await asyncio.sleep(1)  # taking time to retrieve the names
        users_in_role = "\n".join(sorted(str(m) for m in guild.members if role in m.roles))
        cog = self.bot.get_cog("Userinfo")
        form = "{status}  {name_tag}{is_bot}"
        all_forms = [
            form.format(
                status=f"{cog.status_emojis['idle_mobile']}"
                if (g.is_on_mobile() and g.status.name == "idle")
                else f"{cog.status_emojis['dnd_mobile']}"
                if (g.is_on_mobile() and g.status.name == "dnd")
                else f"{cog.status_emojis['mobile']}"
                if (g.is_on_mobile() and g.status.name == "online")
                else f"{cog.status_emojis['streaming']}"
                if any(a.type is discord.ActivityType.streaming for a in g.activities)
                else f"{cog.status_emojis['online']}"
                if g.status.name == "online"
                else f"{cog.status_emojis['idle']}"
                if g.status.name == "idle"
                else f"{cog.status_emojis['dnd']}"
                if g.status.name == "dnd"
                else f"{cog.status_emojis['offline']}",
                name_tag=str(g),
                is_bot=" <:bot:848557763172892722>" if g.bot else "",
            )
            for g in sorted(guild.members, key=lambda x: x.joined_at) if role in g.roles
        ]
        final = "\n".join(all_forms)

        if len(users_in_role) == 0:
            embed = discord.Embed(
                description=bold(f"No one has {role.mention} role."),
                colour=role.color,
            )
            await awaiter.edit(embed=embed)
            return
        try:
            await awaiter.delete()
        except discord.NotFound:
            pass
        pages = []
        sumif = len([m for m in guild.members if role in m.roles])
        for page in pagify(final, delims=["\n"], page_length=1000):
            embed = discord.Embed(
                description=f"**{sumif}** users found in {role.mention} role.\n\n{page}",
                colour=role.color,
            )
            # embed.add_field(name="Users", value=page)
            pages.append(embed)
        final_embed_list = []
        for i, embed in enumerate(pages):
            embed.set_footer(text=f"Page {i + 1} of {len(pages)} | Role ID: {role.id}")
            final_embed_list.append(embed)
        await BaseMenu(
            source=ListPages(pages=final_embed_list),
            delete_message_after=False,
            clear_reactions_after=True,
            timeout=60,
            page_start=0,
        ).start(ctx=ctx)

    @commands.command()
    @commands.bot_has_permissions(add_reactions=True, embed_links=True)
    async def channelmembers(self, ctx: commands.Context, channel: Union[int, discord.TextChannel]):
        """Returns list of members who has access to said text channel."""
        target = self.bot.get_channel(channel) if isinstance(channel, int) else channel
        if target is None:
            return await ctx.send("Said channel not found.")

        members = target.members
        cog = self.bot.get_cog("Userinfo")
        form = "{status}  {name_tag}{bot}"
        all_forms = [
            form.format(
                status=f"{cog.status_emojis['idle_mobile']}"
                if (g.is_on_mobile() and g.status.name == "idle")
                else f"{cog.status_emojis['dnd_mobile']}"
                if (g.is_on_mobile() and g.status.name == "dnd")
                else f"{cog.status_emojis['mobile']}"
                if (g.is_on_mobile() and g.status.name == "online")
                else f"{cog.status_emojis['streaming']}"
                if any(a.type is discord.ActivityType.streaming for a in g.activities)
                else f"{cog.status_emojis['online']}"
                if g.status.name == "online"
                else f"{cog.status_emojis['idle']}"
                if g.status.name == "idle"
                else f"{cog.status_emojis['dnd']}"
                if g.status.name == "dnd"
                else f"{cog.status_emojis['offline']}",
                name_tag=str(g),
                bot=" <:bot:848557763172892722>" if g.bot else "",
            )
            for g in sorted(members, key=lambda x: x.joined_at)
        ]
        final = "\n".join(all_forms)

        pages = []
        for page in pagify(final, delims=["\n"], page_length=1000):
            embed = discord.Embed(
                description=f"Below **{len(members)}** user(s) have access to **#{target.name}**\n\n{page}",
                colour=await ctx.embed_colour(),
            )
            embed.set_author(name=str(target.guild.name), icon_url=target.guild.icon_url)
            embed.timestamp = discord.utils.snowflake_time(target.last_message_id)
            pages.append(embed)
        final_embed_list = []
        for i, embed in enumerate(pages):
            embed.set_footer(text=f"Page {i + 1} of {len(pages)} | Est. last message was on")
            final_embed_list.append(embed)
        await BaseMenu(
            source=ListPages(pages=final_embed_list),
            delete_message_after=False,
            clear_reactions_after=True,
            timeout=60,
            page_start=0,
        ).start(ctx=ctx)

    def _get_suffix(self, num: int):
        suffixes = {1: "st", 2: "nd", 3: "rd"}
        if 10 <= num % 100 <= 20:
            value = "th"
        else:
            value = suffixes.get(num % 10, "th")
        return value

    @commands.command()
    @commands.guild_only()
    async def joined(self, ctx: commands.Context, *, user: FuzzyMember = None):
        """Show when you or a user joined this server."""
        user = user or [ctx.author]
        user = user[0]
        if user.joined_at:
            user_joined = self.format_relative(user.joined_at, "D")
            joined_on = f"{self._humanize_time(user.joined_at)} ago ({user_joined})"
        else:
            joined_on = "a mysterious date not even Discord knows"

        user_index = sorted(ctx.guild.members, key=lambda m: m.joined_at).index(user) + 1
        await ctx.send(
            f"**{user}** joined here {joined_on}.\n"
            + f"Member position in this server: **{user_index}{self._get_suffix(user_index)}**"
        )

    @commands.command()
    @commands.is_owner()
    async def listguilds(self, ctx: commands.Context):
        """List the guilds [botname] is in."""
        asciidoc = lambda m: "{}".format(box(m, lang="asciidoc"))
        guilds = sorted(self.bot.guilds, key=lambda g: g.member_count, reverse=True)
        header = box(f"I am in following {len(guilds)} guild{'s' if len(guilds) > 1 else ''}:")

        max_zpadding = max([len(str(g.member_count)) for g in guilds])
        form = "{gid} :: {mems:0{zpadding}} :: {name}"
        all_forms = [
            form.format(
                gid=g.id,
                mems=g.member_count,
                name=filter_invites(escape(g.name))
                if len(g.name) < 45
                else filter_invites(escape(f"{g.name[:40]} ...")),
                zpadding=max_zpadding
            )
            for g in guilds
        ]
        final = "\n".join(all_forms)

        await ctx.send(header)
        pages = []
        for page in pagify(final, delims=["\n"], page_length=1950):
            pages.append(box(page, lang="asciidoc"))

        controls = {"\N{CROSS MARK}": close_menu} if len(pages) == 1 else DEFAULT_CONTROLS
        await menu(ctx, pages, controls)

    @commands.guild_only()
    @commands.mod_or_permissions(manage_channels=True)
    @commands.command(name="listchannel", aliases=["chlist"])
    async def listchannel(self, ctx: commands.Context):
        """
        List the channels of the current server.
        """
        asciidoc = lambda m: "{}".format(box(m, lang="asciidoc"))
        channels = ctx.guild.channels
        top_channels, category_channels = self.sort_channels(ctx.guild.channels)

        topChannels_formed = "\n".join(self.channels_format(top_channels))
        categories_formed = "\n\n".join([self.category_format(tup) for tup in category_channels])

        await ctx.send(f"{ctx.guild.name} has {len(channels)} channel{'s' if len(channels) > 1 else ''}.")

        for page in pagify(topChannels_formed, delims=["\n"], shorten_by=16):
            await ctx.send(asciidoc(page))

        for page in pagify(categories_formed, delims=["\n\n"], shorten_by=16):
            await ctx.send(asciidoc(page))

    @commands.guild_only()
    @commands.command()
    @commands.mod_or_permissions(manage_guild=True)
    async def newusers(self, ctx: commands.Context, count: int = 5):
        """Lists the newest 5 (max 25) members."""
        count = max(min(count, 25), 5)
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)[:count]

        e = discord.Embed(title='New Members', colour=discord.Colour.green())

        # Credits to Danny
        for member in members:
            body = (
                f"Joined {self.format_relative(member.joined_at, 'R')}\n"
                + f"Created {self.format_relative(member.created_at, 'R')}"
            )
            e.add_field(name=f'{member} (ID: {member.id})', value=body, inline=False)

        await ctx.send(embed=e)

    @staticmethod
    def format_relative(dt: datetime.datetime, style: str = None):
        if style is None:
            return f'<t:{int(dt.timestamp())}>'
        return f'<t:{int(dt.timestamp())}:{style}>'

    @commands.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_guild=True)
    async def perms(self, ctx: commands.Context, *, user: FuzzyMember = None):
        """Fetch a specific user's permissions."""
        user = user or [ctx.author]
        user = user[0]
        perms = iter(ctx.channel.permissions_for(user))
        allowed_perms = ""
        denied_perms = ""
        for x in sorted(perms):
            if "True" in str(x):
                allowed_perms += "+\t{0}\n".format(str(x).split("'")[1])
            else:
                denied_perms += "-\t{0}\n".format(str(x).split("'")[1])
        await ctx.send(box("{0}{1}".format(allowed_perms, denied_perms), lang="diff"))

    @commands.command()
    @commands.guild_only()
    async def rid(self, ctx: commands.Context, *, role: FuzzyRole):
        """Shows the ID of a server role."""
        await ctx.send(f"Role ID for **({role.name})**: `{role.id}`")

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def rinfo(self, ctx: commands.Context, *, role: FuzzyRole):
        """Shows some info about a server role."""
        await ctx.trigger_typing()
        embed = self._role_info(ctx, role)

        await ctx.send(embed=embed)

    def _role_info(self, ctx, role: discord.Role, i: int = 1, n: int = 1) -> discord.Embed:
        perms = iter(role.permissions)
        rolepos = len(ctx.guild.roles) - role.position
        has = len([m for m in ctx.guild.members if role in m.roles])
        plur = "user" if has == 1 else "users"
        allowed_perms = "\n".join(
            "{}".format(str(x).split("'")[1]) for x in sorted(perms) if "True" in str(x)
        )
        #  denied_perms = "\n".join(
            #  "{}".format(str(x).split("'")[1]) for x in sorted(perms) if "False" in str(x)
        #  )
        is_hoisted = f"\n{self.tick} Hoisted" if role.hoist is True else ""
        is_managed = f"\n{self.tick} Managed" if role.managed is True else ""
        is_pingable = f"\n{self.tick} Mentionable" if role.mentionable is True else ""
        extra = is_hoisted + is_managed + is_pingable
        rcolor = role.color or discord.Colour(value=0x000000)
        em = discord.Embed(colour=rcolor)
        em.description = f"Role info for {role.mention}\n{extra}"
        em.set_author(name=str(role.guild.name), icon_url=role.guild.icon_url)
        # em.add_field(name="Role Name", value=role.name)
        em.add_field(name="Created", value=f"{self._humanize_time(role.created_at)} ago")
        # em.add_field(name="Users in Role", value=has)
        # em.add_field(name="ID", value=role.id)
        em.add_field(name="Color", value=role.color)
        em.add_field(name="Position", value=rolepos)
        if allowed_perms:
            em.add_field(
                name="Allowed Permissions",
                value=f"{allowed_perms.replace('_', ' ').title()}"
            )
        # em.add_field(name="Denied Permissions", value="{}".format(denied_perms))
        em.set_footer(
            text=f"Role ID: {role.id} | {has} {plur} have this role!\nPage {i} of {n}"
        )
        #  em.set_thumbnail(url=role.guild.icon_url)
        return em

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(add_reactions=True, embed_links=True, read_message_history=True)
    @commands.mod_or_permissions(manage_guild=True)
    async def allroles(self, ctx: commands.Context):
        """Same as [p]rinfo but for all server roles."""
        roles = sorted(ctx.guild.roles, key=lambda x: x.position, reverse=True)
        if not roles:
            return await ctx.send("This server has no roles.")

        async with ctx.typing():
            pages = []
            for i, role in enumerate(roles, start=1):
                embed = self._role_info(ctx, role, i=i, n=len(roles))
                pages.append(embed)

        await BaseMenu(
            source=ListPages(pages=pages),
            delete_message_after=False,
            clear_reactions_after=True,
            timeout=90,
            page_start=0,
        ).start(ctx=ctx)

    @commands.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_guild=True)
    async def rolelist(self, ctx: commands.Context):
        """Displays the server's roles."""
        form = "`{rpos:0{zpadding}}` - `{rid}` - `{rcolor}` - {rment} "
        max_zpadding = max([len(str(r.position)) for r in ctx.guild.roles])
        rolelist = [
            form.format(rpos=r.position, zpadding=max_zpadding, rid=r.id, rment=r.mention, rcolor=r.color)
            for r in ctx.guild.roles
        ]

        rolelist = sorted(rolelist, reverse=True)
        rolelist = "\n".join(rolelist)
        pages = []
        for page in pagify(rolelist, shorten_by=1400):
            embed = discord.Embed(
                description=f"**Total roles:** {len(ctx.guild.roles)}\n\n{page}", colour=await ctx.embed_colour(),
            )
            pages.append(embed)
        await menu(ctx, pages, DEFAULT_CONTROLS)

    @commands.command()
    @commands.guild_only()
    async def sharedservers(self, ctx: commands.Context, *, user: FuzzyMember = None):
        """Shows shared servers a member has with [botname]."""
        user = user or [ctx.author]
        user = user[0]
        if user.id == ctx.me.id:
            return await ctx.send("Nice try, stalker.")

        seen = len(set([m.guild.name for m in self.bot.get_all_members() if m.id == user.id]))
        shared = [m.guild.name for m in self.bot.get_all_members() if m.id == user.id]
        _share = [shared[0],] + [f'{r:>{len(r)+15}}' for r in shared[1:]]
        final = "\n".join(_share)

        data = (
            f"[Guilds]    :  {seen} shared\n"
            f"[In Guilds] :  {final}"
        )

        for page in pagify(data, page_length=2000):
            await ctx.send(box(page, lang="ini"))

    @commands.command()
    @commands.guild_only()
    async def sinfo(self, ctx: commands.Context, *, guild: GuildConverter = None):
        """Shows server information."""
        guild = guild or ctx.guild
        await ctx.trigger_typing()
        online = str(len([m.status for m in guild.members if str(m.status) == "online" or str(m.status) == "idle"]))
        total = str(len(guild.members))
        humans = str(len([m for m in guild.members if not m.bot]))
        robots = str(len([m for m in guild.members if m.bot]))
        text_channels = len([x for x in guild.channels if isinstance(x, discord.TextChannel)])
        voice_channels = len([x for x in guild.channels if isinstance(x, discord.VoiceChannel)])
        categories = len([x for x in guild.channels if isinstance(x, discord.CategoryChannel)])
        mfa = "True" if guild.mfa_level == 1 else "False"
        btier = str(guild.premium_tier)
        psubs = str(len(guild.premium_subscribers))
        ppsub = "members" if len(guild.premium_subscribers) > 1 else "member"
        upcap = str(guild.filesize_limit / 1024 / 1024)
        boosts = str(guild.premium_subscription_count)
        static = len([e for e in guild.emojis if not e.animated])
        animated = len([e for e in guild.emojis if e.animated])

        data = f"[Name]         :  {guild.name}\n"
        data += f"[Guild ID]     :  {guild.id}\n"
        data += f"[Created]      :  {self._humanize_time(guild.created_at)} ago\n"
        data += f"[Region]       :  {guild.region}\n"
        data += f"[Owner]        :  {guild.owner}\n"
        data += f"[Users]        :  {total} ( {humans} humans + {robots} bots )\n\n"
        data += f"[Categories]   :  {categories}\n"
        data += f"[Channels]     :  {text_channels} text + {voice_channels} voice\n\n"
        # data += f"[Voice]        :  {len(voice_channels)} channels\n"
        data += f"[Roles]        :  {len(guild.roles)}\n"
        data += f"[Emojis]       :  {len(guild.emojis)} ({static} static + {animated} animated)\n"
        data += f"[2FA Admin]    :  {mfa}\n"
        if guild.premium_tier >= 1:
            data += f"[Boost Tier]   :  Tier {btier}\n"
            data += f"[Boosts count] :  {boosts} boosts from {psubs} {ppsub}\n"
        data += f"[Upload Limit] :  {upcap} MiB\n"
        for page in pagify(data):
            await ctx.send(box(page, lang="ini"))

    @commands.command()
    async def uid(self, ctx: commands.Context, *, partial_name_or_nick: FuzzyMember = None):
        """Get a member's id from a fuzzy name search."""
        partial_name_or_nick = partial_name_or_nick or [ctx.author]

        table = []
        headers = ["User ID", "Username", "Nickname"]
        for user_obj in partial_name_or_nick:
            nickname = user_obj.nick or ""
            table.append([user_obj.id, str(user_obj), nickname])
        msg = tabulate(table, headers, tablefmt="simple")

        pages = []
        for page in pagify(msg, delims=["\n"], page_length=1800):
            pages.append(box(page))

        controls = {"\N{CROSS MARK}": close_menu} if len(pages) == 1 else DEFAULT_CONTROLS
        await menu(ctx, pages, controls)

    @commands.command()
    @commands.guild_only()
    async def uinfo(self, ctx: commands.Context, *, users: FuzzyMember = None):
        """Shows user information. Defaults to author."""
        users = users or [ctx.author]

        await ctx.trigger_typing()
        pages = []
        for user in users:
            roles = [r.name for r in user.roles if r.name != "@everyone"]

            c_acts = [c for c in user.activities if c.type == discord.ActivityType.custom]
            l_acts = [l for l in user.activities if l.type == discord.ActivityType.listening]
            p_acts = [p for p in user.activities if p.type == discord.ActivityType.playing]
            s_acts = [s for s in user.activities if s.type == discord.ActivityType.streaming]
            w_acts = [w for w in user.activities if w.type == discord.ActivityType.watching]

            data = f"[Name]            : {escape(str(user))}\n"
            if user.nick:
                data += f"[Nickname]        : {escape(str(user.nick))}\n"
            data += f"[User ID]         : {user.id}\n"
            data += f"[Status]          : {user.status}\n"
            data += f"[Servers]         : {len(user.mutual_guilds)} shared\n"
            if p_acts:
                data += f"[Playing]         : {escape(str(p_acts[0].name))}\n"
            if l_acts and isinstance(l_acts[0], discord.Spotify):
                spot = l_acts[0]
                _form = f"{spot.title} by {spot.artist}"
                data += f"[Listening]       : {escape(_form)}\n"
            if w_acts:
                data += f"[Watching]        : {escape(str(w_acts[0].name))}\n"
            if s_acts:
                data += f"[Streaming]       : {escape(str(s_acts[0].name))}\n"
            if c_acts:
                data += f"[Custom status]   : {escape(str(c_acts[0].name))}\n"
            data += f"[Created]         : {self._humanize_time(user.created_at)} ago\n"
            if user.joined_at:
                data += f"[Joined]          : {self._humanize_time(user.joined_at)} ago\n"
                data += f"[Roles]           : {len(roles)}\n"
                data += f"[In Voice (VC)]   : {user.voice.channel if user.voice is not None else None}\n"
                data += f"[AFK]             : {user.voice.afk if user.voice is not None else False}\n"
        pages.append(box(data, lang="ini"))

        controls = {"\N{CROSS MARK}": close_menu} if len(pages) == 1 else DEFAULT_CONTROLS
        await menu(ctx, pages, controls)

    @commands.command()
    @commands.is_owner()
    async def whatis(self, ctx: commands.Context, id: int):
        """What is it?"""
        it_is = False
        roles = []
        rls = [s.roles for s in self.bot.guilds]
        for rl in rls:
            roles.extend(rl)

        look_at = (
            self.bot.guilds
            + self.bot.emojis
            + roles
            + [m for m in self.bot.get_all_members()]
            + [c for c in self.bot.get_all_channels()]
        )

        if ctx.guild.id == id:
            it_is = ctx.guild
        elif ctx.channel.id == id:
            it_is = ctx.channel
        elif ctx.author.id == id:
            it_is = ctx.author

        if not it_is:
            it_is = discord.utils.get(look_at, id=id)

        if isinstance(it_is, discord.Guild):
            await ctx.invoke(self.sinfo, it_is)
        elif isinstance(it_is, discord.abc.GuildChannel):
            await ctx.invoke(self.chinfo, id)
        elif isinstance(it_is, (discord.User, discord.Member)):
            await ctx.invoke(self.uinfo, it_is)
        elif isinstance(it_is, discord.Role):
            await ctx.invoke(self.rinfo, rolename=it_is)
        elif isinstance(it_is, discord.Emoji):
            await ctx.invoke(self.einfo, it_is)
        else:
            await ctx.send("I could not find anything for this ID.")

    @staticmethod
    def _humanize_time(time):
        dt1 = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        dt2 = time

        diff = relativedelta.relativedelta(dt1, dt2)

        yrs, mths, days = (diff.years, diff.months, diff.days)
        hrs, mins, secs = (diff.hours, diff.minutes, diff.seconds)

        pretty = f"{yrs}y {mths}mth {days}d {hrs}h {mins}m {secs}s"
        to_join = ", ".join([x for x in pretty.split() if x[0] != '0'][:3])

        return to_join

    def sort_channels(self, channels):
        temp = dict()

        channels = sorted(channels, key=lambda c: c.position)

        for c in channels[:]:
            if isinstance(c, discord.CategoryChannel):
                channels.pop(channels.index(c))
                temp[c] = list()

        for c in channels[:]:
            if c.category:
                channels.pop(channels.index(c))
                temp[c.category].append(c)

        category_channels = sorted(
            [(cat, sorted(chans, key=lambda c: c.position)) for cat, chans in temp.items()],
            key=lambda t: t[0].position,
        )
        return channels, category_channels

    def channels_format(self, channels: list):
        if channels == []:
            return []

        channel_form = "{name} :: {ctype} :: {cid}"

        def type_name(channel):
            return channel.__class__.__name__[:-7]

        name_justify = max([len(c.name[:24]) for c in channels])
        type_justify = max([len(type_name(c)) for c in channels])

        return [
            channel_form.format(name=c.name[:24].ljust(name_justify), ctype=type_name(c).ljust(type_justify), cid=c.id,)
            for c in channels
        ]

    def category_format(self, cat_chan_tuple: tuple):

        cat = cat_chan_tuple[0]
        chs = cat_chan_tuple[1]

        chfs = self.channels_format(chs)
        if chfs != []:
            ch_forms = ["\t" + f for f in chfs]
            return "\n".join([f"{cat.name} :: {cat.id}"] + ch_forms)
        else:
            return "\n".join([f"{cat.name} :: {cat.id}"] + ["\tNo Channels"])
