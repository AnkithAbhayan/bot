from datetime import datetime, timedelta
import json
import os

import discord
from discord.ext import commands, tasks

from bot.constants import Channels
from bot.constants import DURATION_DICT

from bot.utilities import get_yaml_val

GUILD_ID = get_yaml_val("config.yml", "guild.id")

UNMUTE_FILE = os.path.join(
    "bot",
    "exts",
    "moderation",
    "unmute_times.txt",
)


class Moderation(commands.Cog):
    """Cog for moderation commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.unmute_check.start()

    @commands.command(aliases=["exile"])
    @commands.has_role("Cat Devs")
    async def pban(
        self,
        ctx: commands.Context,
        user: discord.User = None,
        *,
        reason: str = "Badly behaved",
    ):
        """Permanently bans a user."""
        if user == self.bot.user:
            await ctx.send("You can't ban me!")
            return

        if user == ctx.author:
            await ctx.send("You can't ban yourself!")
            return

        await ctx.guild.ban(user)
        await ctx.send(f"Successfully banned {user.name}")

        channel = self.bot.get_channel(Channels.modlog)
        await channel.send(
            f"{ctx.author.mention} banned {user.mention} for reason `{reason}`."
        )

    @commands.command(aliases=(["s" + "h" * i for i in range(1, 10)] + ["shut"]))
    @commands.has_role("Cat Devs")
    async def mute(
        self,
        ctx: commands.Context,
        user: discord.Member = None,
        time: str = "5m",
        *,
        reason: str = "Because of naughtiness",
    ):
        """Mutes a user for a set amount of time."""
        if user == self.bot.user:
            await ctx.send("You can't mute me!")
            return

        if user == ctx.author:
            await ctx.send("You can't mute yourself!")
            return

        muted_role = discord.utils.get(ctx.guild.roles, name="Suppressed")

        if not muted_role:
            try:
                muted_role = await ctx.guild.create_role(
                    name="Suppressed", reason="To use for muting"
                )

                for channel in ctx.guild.channels:
                    await channel.set_permissions(
                        muted_role,
                        send_messages=False,
                        speak=False,
                        add_reactions=False,
                    )

                await ctx.guild.edit_role_positions(
                    positions={muted_role: 21}, reason="To override cat dev permissions"
                )

            except discord.Forbidden:
                return await ctx.send("I have no permissions to make a muted role")

        channel = self.bot.get_channel(Channels.modlog)
        await channel.send(
            f"{ctx.author.mention} muted {user.mention} for `{time}` for reason `{reason}`."
        )

        unmute_time = datetime.now() + timedelta(
            seconds=int(time[0:-1]) * DURATION_DICT[time[-1]]
        )

        await user.add_roles(muted_role)

        json_input = {user.id: unmute_time.timestamp()}
        try:
            with open(UNMUTE_FILE, "r+") as f:
                data = json.load(f)
                f.seek(0)
                json.dump({**data, **json_input}, f)
        except FileNotFoundError:
            with open(UNMUTE_FILE, "w") as new_f:
                json.dump(json_input, new_f)

    @commands.command(aliases=["yeetmsg"])
    @commands.has_role("Cat Devs")
    async def purge(
        self, ctx: commands.Context, limit: int, *, reason: str = None
    ) -> None:
        """Deletes a set amount of messages."""

        if not 0 < int(limit) < 200:
            await ctx.send("Please purge between 0 and 200 messages.")
            return

        await ctx.channel.purge(limit=limit)

        channel = self.bot.get_channel(Channels.modlog)
        await channel.send(
            f"{ctx.message.author.mention} purged at most `{limit}` messages for reason `{reason}`."
        )

    @tasks.loop(seconds=0.5)
    async def unmute_check(self):
        guild = self.bot.get_guild(GUILD_ID["id"])
        muted_role = discord.utils.get(guild.roles, name="Suppressed")

        with open(UNMUTE_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.decoder.JSONDecodeError:
                return

        keys_to_del = []

        for user_id, unmute_time in data.items():
            if datetime.now().timestamp() > unmute_time:
                user = guild.get_member(int(user_id))
                try:
                    await user.remove_roles(muted_role)
                except AttributeError:
                    return

                keys_to_del.append(user_id)

        for key in keys_to_del:
            del data[key]

        with open(UNMUTE_FILE, "w") as f:
            f.seek(0)
            json.dump(data, f)

    @commands.command(aliases=["pardon"])
    @commands.has_role("Cat Devs")
    async def unmute(self, ctx: commands.Context, user: discord.Member):
        """Unmutes mentioned user."""
        muted_role = discord.utils.get(ctx.guild.roles, name="Suppressed")

        if muted_role not in user.roles:
            ctx.send("This user is already unmuted!")
            return

        with open(UNMUTE_FILE, "r+") as f:
            data = json.load(f)
            del data[str(user.id)]
            f.truncate(0)
            f.seek(0)
            json.dump(data, f)

        await user.remove_roles(muted_role)

        channel = self.bot.get_channel(Channels.modlog)
        await channel.send(f"{ctx.author.mention} unmuted {user.mention}.")
        await ctx.send(f"Successfully unmuted {user.mention}.")

    @commands.command(aliases=["devify"])
    @commands.has_role("Cat Devs")
    async def knight(self, ctx: commands.Context, user: discord.Member):
        """Makes specified user a Cat Dev."""
        role = discord.utils.get(ctx.guild.roles, name="Cat Devs")
        try:
            await user.add_roles(role)
            await ctx.send(f"Knighted {user.mention}.")
            channel = self.bot.get_channel(Channels.modlog)
            await channel.send(f"{ctx.author.mention} made {user.mention} a cat dev.")
        except discord.Forbidden:
            await ctx.send(f"Could not make {user.mention} a Cat Dev!")


def setup(bot: commands.Bot):
    """Loads cog."""
    bot.add_cog(Moderation(bot))
