import asyncio
import datetime
import logging
from dateutil import relativedelta
from typing import Union

import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import box, bold, escape, pagify
from redbot.core.utils.common_filters import filter_invites
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.xmenus import BaseMenu, ListPages
from tabulate import tabulate

from .converter import FuzzyMember, GuildConverter

log = logging.getLogger("red.aikaterna.tools")


class Tools(commands.Cog):
    """Mod and Admin tools."""

    def __init__(self, bot):
        self.bot = bot
        self.tick = "<:boldCheck:799274720159334430>"
        self.emojis = self.bot.loop.create_task(self.init())

    def cog_unload(self):
        if self.emojis:
            self.emojis.cancel()

    async def init(self):
        await self.bot.wait_until_ready()
        self.status_emojis = {
            "mobile": discord.utils.get(self.bot.emojis, id=749067110931759185),
            "mobile_dnd": discord.utils.get(self.bot.emojis, id=847028205818740747),
            "mobile_idle": discord.utils.get(self.bot.emojis, id=847028206060961802),
            "online": discord.utils.get(self.bot.emojis, id=749221433552404581),
            "idle": discord.utils.get(self.bot.emojis, id=749221433095356417),
            "dnd": discord.utils.get(self.bot.emojis, id=749221432772395140),
            "invisible": discord.utils.get(self.bot.emojis, id=749221433049088082),
            "streaming": discord.utils.get(self.bot.emojis, id=749221434039205909),
        }

    @commands.guild_only()
    @commands.group()
    async def access(self):
        """Check channel access"""
        pass

    @access.command()
    async def compare(self, ctx, user: discord.Member):
        """Compare channel access with another server member."""
        if user is None:
            return
        guild = ctx.guild

        try:
            tcs = guild.text_channels
            vcs = guild.voice_channels
        except AttributeError:
            return await ctx.send("User is not in that guild or I do not have access to that guild.")

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
    async def text(self, ctx, user: discord.Member):
        """Check text channel access."""
        guild = ctx.guild

        try:
            can_access = [c.name for c in guild.text_channels if c.permissions_for(user).read_messages is True]
            text_channels = [c.name for c in guild.text_channels]
        except AttributeError:
            return await ctx.send("User is not in that guild or I do not have access to that guild.")

        prefix = "You have" if user.id == ctx.author.id else user.name + " has"
        msg = "```ini\n[{} access to {} out of {} text channels]\n\n".format(
            prefix, len(can_access), len(text_channels)
        )

        msg += "[ACCESS]:\n{}\n\n".format(", ".join(can_access))
        msg += "[NO ACCESS]:\n{}\n```".format(", ".join(list(set(text_channels) - set(can_access))))
        for page in pagify(msg, delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @access.command()
    async def voice(self, ctx, user: discord.Member):
        """Check voice channel access."""
        guild = ctx.guild

        try:
            can_access = [c.name for c in guild.voice_channels if c.permissions_for(user).connect is True]
            voice_channels = [c.name for c in guild.voice_channels]
        except AttributeError:
            return await ctx.send("User is not in that guild or I do not have access to that guild.")

        prefix = "You have" if user.id == ctx.author.id else user.name + " has"
        msg = "```ini\n[{} access to {} out of {} voice channels]\n\n".format(
            prefix, len(can_access), len(voice_channels)
        )

        msg += "[ACCESS]:\n{}\n\n".format(", ".join(can_access))
        msg += "[NO ACCESS]:\n{}\n```".format(", ".join(list(set(voice_channels) - set(can_access))))
        for page in pagify(msg, delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @commands.guild_only()
    @commands.command()
    @commands.mod_or_permissions(manage_guild=True)
    async def banlist(self, ctx):
        """Displays the server's banlist."""
        try:
            banlist = await ctx.guild.bans()
        except discord.errors.Forbidden:
            await ctx.send("I do not have the `Ban Members` permission.")
            return
        bancount = len(banlist)
        if bancount == 0:
            msg = "No users are banned from this server."
        else:
            msg = ""
            for user_obj in banlist:
                user_name = f"{user_obj.user.name}#{user_obj.user.discriminator}"
                msg += f"`{user_obj.user.id}` - {user_name}\n"

        banlist = sorted(msg)
        embed_list = []
        for page in pagify(msg, delims=["\n"], page_length=2000):
            embed = discord.Embed(
                description=page,
                colour=await ctx.embed_colour(),
            )
            embed.set_footer(text=f"Total bans: {bancount}")
            embed_list.append(embed)
        await menu(ctx, embed_list, DEFAULT_CONTROLS)

    @commands.guild_only()
    @commands.command()
    async def chinfo(self, ctx, channel: int = None):
        """Shows channel information. Defaults to current text channel."""
        if channel is None:
            channel = ctx.channel
        else:
            channel = self.bot.get_channel(channel)

        if channel is None:
            return await ctx.send("Not a valid channel.")

        yesno = {True: "Yes", False: "No"}
        typemap = {
            discord.TextChannel: "Text Channel",
            discord.VoiceChannel: "Voice Channel",
            discord.CategoryChannel: "Category",
        }

        load = "Loading channel info..."
        waiting = await ctx.send(box(load))

        data = ""
        data += "[Name]         : {}\n".format(escape(str(channel)))
        data += "[ID]           : {}\n".format(channel.id)
        data += "[Private]      : {}\n".format(yesno[isinstance(channel, discord.abc.PrivateChannel)])
        if isinstance(channel, discord.TextChannel) and channel.topic != "":
            data += "[Topic]        : {}\n".format(channel.topic)
        data += "[Position]     : {}\n".format(channel.position)
        data += "[Created]      : {}\n".format(self._accurate_timedelta(channel.created_at))
        data += "[Type]         : {}\n".format(typemap[type(channel)])
        if isinstance(channel, discord.VoiceChannel):
            data += "[Users]        : {}\n".format(len(channel.members))
            data += "[User limit]   : {}\n".format(channel.user_limit)
            data += "[Bitrate]      : {} Kbps\n".format(int(channel.bitrate / 1000))
        await asyncio.sleep(1)
        await waiting.edit(content=box(data, lang="ini"))

    @commands.guild_only()
    @commands.command()
    async def eid(self, ctx, emoji: discord.Emoji):
        """Get an id for an emoji."""
        await ctx.send(f"{emoji}:{emoji.id}")

    @commands.guild_only()
    @commands.command()
    async def einfo(self, ctx, emoji: discord.Emoji):
        """Emoji information."""
        e = emoji
        m = (
            f"{str(e)}\n```ini\n"
            + f"[NAME]    :   {e.name}\n"
            + f"[GUILD]   :   {e.guild}\n"
            + f"[URL]     :   {e.url}\n"
            + f"[ANIMATED]:   {e.animated}```"
        )
        await ctx.send(m)

    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @commands.command(aliases=["hasrole"])
    async def inrole(self, ctx, *, rolename):
        """Check members in the role specified."""
        guild = ctx.guild
        if rolename.startswith("<@&"):
            role_id = rolename.lstrip("<@&").rstrip(">")
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
                    + f"Type the number of the role you wish to see.\n\n"
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
        users_in_role = "\n".join(sorted(m.name + "#" + m.discriminator for m in guild.members if role in m.roles))

        form = "{status}  {name_tag}"
        all_forms = [
            form.format(
                status=f"{self.status_emojis['mobile_idle']}"
                if (g.is_on_mobile() and g.status.name == "idle")
                else f"{self.status_emojis['mobile_dnd']}"
                if (g.is_on_mobile() and g.status.name == "dnd")
                else f"{self.status_emojis['mobile']}"
                if (g.is_on_mobile() and g.status.name == "online")
                else f"{self.status_emojis['streaming']}"
                if any(a.type is discord.ActivityType.streaming for a in g.activities)
                else f"{self.status_emojis['online']}"
                if g.status.name == "online"
                else f"{self.status_emojis['idle']}"
                if g.status.name == "idle"
                else f"{self.status_emojis['dnd']}"
                if g.status.name == "dnd"
                else f"{self.status_emojis['invisible']}",
                name_tag=str(g),
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
        embed_list = []
        sumif = len([m for m in guild.members if role in m.roles])
        for page in pagify(final, delims=["\n"], page_length=1000):
            embed = discord.Embed(
                description=f"**{sumif}** users found in {role.mention} role.\n\n{page}",
                colour=role.color,
            )
            # embed.add_field(name="Users", value=page)
            embed_list.append(embed)
        final_embed_list = []
        for i, embed in enumerate(embed_list):
            embed.set_footer(text=f"Page {i + 1} of {len(embed_list)} | Role ID: {role.id}")
            final_embed_list.append(embed)
        await BaseMenu(
            source=ListPages(pages=final_embed_list),
            delete_message_after=False,
            clear_reactions_after=True,
            timeout=60,
            page_start=0,
        ).start(ctx=ctx)

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def channelmembers(self, ctx, channel: Union[int, discord.TextChannel]):
        """Returns list of members who has access to said text channel."""
        target = self.bot.get_channel(channel) if isinstance(channel, int) else channel
        if target is None:
            return await ctx.send("Said channel not found.")

        members = target.members

        form = "{status}  {name_tag}{bot}"
        all_forms = [
            form.format(
                status=f"{self.status_emojis['mobile_idle']}"
                if (g.is_on_mobile() and g.status.name == "idle")
                else f"{self.status_emojis['mobile_dnd']}"
                if (g.is_on_mobile() and g.status.name == "dnd")
                else f"{self.status_emojis['mobile']}"
                if (g.is_on_mobile() and g.status.name == "online")
                else f"{self.status_emojis['streaming']}"
                if any(a.type is discord.ActivityType.streaming for a in g.activities)
                else f"{self.status_emojis['online']}"
                if g.status.name == "online"
                else f"{self.status_emojis['idle']}"
                if g.status.name == "idle"
                else f"{self.status_emojis['dnd']}"
                if g.status.name == "dnd"
                else f"{self.status_emojis['invisible']}",
                name_tag=str(g),
                bot=" <:bot:848557763172892722>" if g.bot else "",
            )
            for g in sorted(members, key=lambda x: x.joined_at)
        ]
        final = "\n".join(all_forms)

        embed_list = []
        for page in pagify(final, delims=["\n"], page_length=1000):
            embed = discord.Embed(
                description=f"Below **{len(members)}** user(s) have access to **#{target.name}**\n\n{page}",
                colour=await ctx.embed_colour(),
            )
            embed.set_author(name=str(target.guild.name), icon_url=target.guild.icon_url)
            embed.timestamp = discord.utils.snowflake_time(target.last_message_id)
            embed_list.append(embed)
        final_embed_list = []
        for i, embed in enumerate(embed_list):
            embed.set_footer(text=f"Page {i + 1} of {len(embed_list)} | Est. last message was on")
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

    @commands.guild_only()
    @commands.command()
    async def joined(self, ctx, user: FuzzyMember = None):
        """Show when you or a user joined this server."""
        user = user or ctx.author
        if user.joined_at:
            user_joined = user.joined_at.strftime("%d %b, %Y at %H:%M")
            joined_on = f"{self._accurate_timedelta(user.joined_at)} ago (on {user_joined} UTC)"
        else:
            joined_on = "a mysterious date not even Discord knows"

        user_index = sorted(ctx.guild.members, key=lambda m: m.joined_at).index(user) + 1
        # if ctx.channel.permissions_for(ctx.guild.me).embed_links:
        #     embed = discord.Embed(
        #         description=f"{user.mention} joined this server on:\n{joined_on}.\n\n"
        #         + f"Member position in this server: ",
        #         color=0x2F3136,
        #     )
        #     await ctx.send(embed=embed)
        # else:
        await ctx.send(
            f"**{user}** joined here {joined_on}.\n"
            + f"Member position in this server: **{user_index}{self._get_suffix(user_index)}**"
        )

    @commands.command()
    @commands.is_owner()
    async def listguilds(self, ctx):
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
                name=filter_invites(escape(g.name)) if len(g.name) < 45 else filter_invites(escape(f"{g.name[:40]} ...")),
                zpadding=max_zpadding
            )
            for g in guilds
        ]
        final = "\n".join(all_forms)

        await ctx.send(header)
        page_list = []
        for page in pagify(final, delims=["\n"], page_length=1950):
            page_list.append(asciidoc(page))

        if len(page_list) == 1:
            return await ctx.send(page_list)
        await menu(ctx, page_list, DEFAULT_CONTROLS)

    @commands.guild_only()
    @commands.mod_or_permissions(manage_channels=True)
    @commands.command(name="listchannel", aliases=["chlist"])
    async def listchannel(self, ctx):
        """
        List the channels of the current server
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
    async def newusers(self, ctx, count: int = 5, fm: str = "py"):
        """Lists the newest 5 members."""
        guild = ctx.guild
        count = max(min(count, 25), 5)
        members = sorted(guild.members, key=lambda m: m.joined_at, reverse=True)[:count]

        head1 = "{} newest members".format(count)
        header = "{:>33}\n{}\n\n".format(head1, "-" * 57)

        user_body = (
            " {mem} ({memid})\n"
            + " {spcs}Joined Guild    : {sp1}{join}\n"
            + " {spcs}Account Created : {sp2}{created}\n\n"
        )

        disp = header
        spcs = [" " * (len(m.name) // 2) for m in members]
        smspc = min(spcs, key=lambda it: len(it))

        def calculate_diff(date1, date2):
            date1str, date2str = self._accurate_timedelta(date1), self._accurate_timedelta(date2)
            date1sta, date2sta = date1str.split(" ")[0], date2str.split(" ")[0]

            if len(date1sta) == len(date2sta):
                return (0, 0)
            else:
                ret = len(date2sta) - len(date1sta)
                return (abs(ret), 0 if ret > 0 else 1)

        for member in members:
            req = calculate_diff(member.joined_at, member.created_at)
            sp1 = req[0] if req[1] == 0 else 0
            sp2 = req[0] if req[1] == 1 else 0

            disp += user_body.format(
                mem=member.display_name,
                memid=member.id,
                join=self._accurate_timedelta(member.joined_at),
                created=self._accurate_timedelta(member.created_at),
                spcs=smspc,
                sp1="0" * sp1,
                sp2="0" * sp2,
            )

        for page in pagify(disp, delims=["\n\n"]):
            await ctx.send(box(page, lang=fm))

    @commands.guild_only()
    @commands.command()
    @commands.mod_or_permissions(manage_guild=True)
    async def perms(self, ctx, user: FuzzyMember = None):
        """Fetch a specific user's permissions."""
        if user is None:
            user = ctx.author

        perms = iter(ctx.channel.permissions_for(user))
        perms_we_have = ""
        perms_we_dont = ""
        for x in sorted(perms):
            if "True" in str(x):
                perms_we_have += "+\t{0}\n".format(str(x).split("'")[1])
            else:
                perms_we_dont += "-\t{0}\n".format(str(x).split("'")[1])
        await ctx.send(box("{0}{1}".format(perms_we_have, perms_we_dont), lang="diff"))

    @commands.guild_only()
    @commands.command()
    async def rid(self, ctx, *, rolename: discord.Role):
        """Shows the id of a role."""
        if rolename is discord.Role:
            role = rolename
        else:
            role = self._role_from_string(ctx.guild, rolename)
        if role is None:
            embed = discord.Embed(
                description="`{rolename}` role not found.",
                colour=await ctx.embed_colour(),
            )
            await ctx.send(embed=embed)
            return
        await ctx.send(f"**({rolename})** Role ID: {role.id}")

    @commands.guild_only()
    @commands.command(aliases=["role"])
    @commands.bot_has_permissions(embed_links=True)
    async def rinfo(self, ctx, *, rolename: discord.Role):
        """Shows role info."""
        guild = ctx.guild

        if not isinstance(rolename, discord.Role):
            role = self._role_from_string(guild, rolename, guild.roles)
        else:
            role = rolename
        if role is not None:
            perms = iter(role.permissions)
            rolepos = len(guild.roles) - role.position
            has = len([m for m in guild.members if role in m.roles])
            plur = "user" if has == 1 else "users"
            perms_we_have = "\n".join("{}".format(str(x).split("'")[1]) for x in sorted(perms) if "True" in str(x))
            perms_we_dont = "\n".join("{}".format(str(x).split("'")[1]) for x in sorted(perms) if "False" in str(x))
            if perms_we_have == "":
                perms_we_have = "None"
            if perms_we_dont == "":
                perms_we_dont = "None"
            extra = f"\n{self.tick} Hoisted" if role.hoist is True else ""
            extra += f"\n{self.tick} Managed" if role.managed is True else ""
            extra += f"\n{self.tick} Mentionable" if role.mentionable is True else ""
            msg = discord.Embed(description="Gathering role stats...", colour=role.color)
            if role.color is None:
                role.color = discord.Colour(value=0x000000)
            loadingmsg = await ctx.send(embed=msg)
            em = discord.Embed(
                description=f"Role info for {role.mention}\n{extra}",
                colour=role.colour
            )
            # em.add_field(name="Role Name", value=role.name)
            em.add_field(name="Created", value=self._accurate_timedelta(role.created_at))
            # em.add_field(name="Users in Role", value=has)
            # em.add_field(name="ID", value=role.id)
            em.add_field(name="Color", value=role.color)
            em.add_field(name="Position", value=rolepos)
            em.add_field(
                name="Allowed Permissions",
                value=f"{perms_we_have.replace('_', ' ').title()}"
            )
            # em.add_field(name="Invalid Permissions", value="{}".format(perms_we_dont))
            em.set_footer(text=f"ID: {role.id} | {has} {plur} have this role")
            em.set_thumbnail(url=role.guild.icon_url)
            await loadingmsg.edit(embed=em)
        else:
            await ctx.send("That role cannot be found.")
            return

    @commands.guild_only()
    @commands.command(aliases=["listroles"])
    @commands.mod_or_permissions(manage_guild=True)
    async def rolelist(self, ctx):
        """Displays the server's roles."""
        form = "`{rpos:0{zpadding}}` - `{rid}` - `{rcolor}` - {rment} "
        max_zpadding = max([len(str(r.position)) for r in ctx.guild.roles])
        rolelist = [
            form.format(rpos=r.position, zpadding=max_zpadding, rid=r.id, rment=r.mention, rcolor=r.color)
            for r in ctx.guild.roles
        ]

        rolelist = sorted(rolelist, reverse=True)
        rolelist = "\n".join(rolelist)
        embed_list = []
        for page in pagify(rolelist, shorten_by=1400):
            embed = discord.Embed(
                description=f"**Total roles:** {len(ctx.guild.roles)}\n\n{page}", colour=await ctx.embed_colour(),
            )
            embed_list.append(embed)
        await menu(ctx, embed_list, DEFAULT_CONTROLS)

    @commands.command(hidden=True)
    async def sharedservers(self, ctx, *, user: FuzzyMember = None):
        """Shows shared servers one has with [botname]. Defaults to you, the author."""
        user = user or ctx.author
        if user.id == ctx.me.id:
            return await ctx.send("Nice try. I can't fetch shared servers with myself.")
        seen = len(set([m.guild.name for m in self.bot.get_all_members() if m.id == user.id]))
        shared = [m.guild.name for m in self.bot.get_all_members() if m.id == user.id]
        _share = [shared[0],] + [f'{r:>{len(r)+15}}' for r in shared[1:]]
        final = "\n".join(_share)

        data = f"[Guilds]    :  {seen} shared\n[In Guilds] :  {final}"

        for page in pagify(data, page_length=2000):
            await ctx.send(box(page, lang="ini"))

    @commands.guild_only()
    @commands.command(aliases=["ginfo"])
    async def sinfo(self, ctx, guild: GuildConverter = None):
        """Shows server information."""
        guild = guild or ctx.guild

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

        load = "Loading guild info..."
        waiting = await ctx.send(box(load))

        data = ""
        data += "[Guild ID]     :  {}\n".format(guild.id)
        data += "[Created]      :  {}\n".format(self._accurate_timedelta(guild.created_at))
        data += "[Region]       :  {}\n".format(guild.region)
        data += "[Owner]        :  {}\n".format(guild.owner)
        data += "[Users]        :  {} ( {} humans + {} bots )\n\n".format(total, humans, robots)
        data += "[Categories]   :  {}\n".format(categories)
        data += "[Channels]     :  {} text + {} voice\n\n".format(text_channels, voice_channels)
        # data += "[Voice]        :  {} channels\n".format(len(voice_channels))
        data += "[Roles]        :  {}\n".format(len(guild.roles))
        data += "[Emojis]       :  {} ({} static + {} animated)\n".format(len(guild.emojis), static, animated)
        data += "[2FA Admin]    :  {}\n".format(mfa)
        if guild.premium_tier >= 1:
            data += "[Boost Tier]   :  Tier {}\n".format(btier)
            data += "[Boosts count] :  {} boosts from {} {}\n".format(boosts, psubs, ppsub)
        data += "[Upload Limit] :  {} MiB\n".format(upcap)
        await asyncio.sleep(1)
        await waiting.delete()
        for page in pagify(data):
            await ctx.send(box(page, lang="ini"))

    @commands.guild_only()
    @commands.command()
    async def uinfo(self, ctx, user: FuzzyMember = None):
        """Shows user information. Defaults to author."""
        if user is None:
            user = ctx.author

        seen = str(len(set([member.guild.name for member in self.bot.get_all_members() if member.id == user.id])))
        spot = next((activity for activity in user.activities if isinstance(activity, discord.Spotify)), None)
        p_acts = [c for c in user.activities if c.type == discord.ActivityType.playing]
        s_acts = [c for c in user.activities if c.type == discord.ActivityType.streaming]
        w_acts = [c for c in user.activities if c.type == discord.ActivityType.watching]
        c_acts = [c for c in user.activities if c.type == discord.ActivityType.custom]

        load = "Loading user info..."
        waiting = await ctx.send(box(load))

        data = ""
        data += f"[Name]            : {escape(str(user))}\n"
        if user.nick:
            data += f"[Nickname]        : {escape(str(user.nick))}\n"
        data += f"[User ID]         : {user.id}\n"
        data += f"[Status]          : {user.status}\n"
        data += f"[Servers]         : {seen} shared\n"
        if p_acts:
            data += f"[Playing]         : {escape(str(p_acts[0].name))}\n"
        if spot:
            _form = f"{spot.title} by {spot.artist}"
            data += f"[Listening]       : {escape(_form)}\n"
        if w_acts:
            data += f"[Watching]        : {escape(str(w_acts[0].name))}\n"
        if s_acts:
            data += f"[Streaming]       : {escape(str(s_acts[0].name))}\n"
        if c_acts:
            data += f"[Custom status]   : {escape(str(c_acts[0].name))}\n"
        data += f"[Created]         : {self._accurate_timedelta(user.created_at)}\n"
        await asyncio.sleep(1)
        await waiting.delete()
        for page in pagify(data):
            await ctx.send(box(page, lang="ini"))

    @commands.guild_only()
    @commands.command()
    @commands.is_owner()
    async def whatis(self, ctx, id: int):
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
    def _accurate_timedelta(time):
        dt1 = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        dt2 = time

        diff = relativedelta.relativedelta(dt1, dt2)

        yrs, mths, days = (diff.years, diff.months, diff.days)
        hrs, mins, secs = (diff.hours, diff.minutes, diff.seconds)

        pretty = f"{yrs}y {mths}mth {days}d {hrs}h {mins}m {secs}s"
        to_join = ", ".join([x for x in pretty.split() if x[0] != '0'][:3])

        return to_join

    def _role_from_string(self, guild, rolename, roles=None):
        if roles is None:
            roles = guild.roles
        role = discord.utils.find(lambda r: r.name.lower() == str(rolename).lower(), roles)
        return role

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
