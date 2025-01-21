from enum import Enum
from typing import Optional
import discord
from discord import CategoryChannel, TextChannel, app_commands, Interaction
from discord.ext import commands, tasks
import traceback

from draftphase.calendar import CalendarCategory, games_to_calendar_embed
from draftphase.discord_utils import CustomException, get_success_embed
from draftphase.game import Game

class ChannelEmojis(Enum):
    PLANNED = '📆'
    OFFERING = '🔨'
    ONGOING = '👀'
    FINISHED = '✅'

@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class CalendarCog(commands.GroupCog, group_name="calendar"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.calendar_updater.start()
        self.channel_emoji_updater.start()

    @app_commands.command(name="list", description="Show a list of all categories listed on the calendar")
    async def list_calendar(self, interaction: Interaction):
        assert interaction.guild is not None

        embed = discord.Embed()
        calendars = CalendarCategory.load_all_in_guild(interaction.guild.id)
        
        if calendars:
            embed.title = f"There are {str(len(calendars))} listed categories."

            channel_groups: dict[TextChannel, list[CalendarCategory]] = {}
            for calendar in calendars:
                channel = await calendar.get_channel()
                category = await calendar.get_category()
                if not (channel and category):
                    continue
                channel_groups.setdefault(channel, []).append(calendar)
            
            for channel, calendars in channel_groups.items():
                field_value = f"-# *{channel.mention}*"
                for calendar in calendars:
                    category = await calendar.get_category()
                    if category:
                        field_value += f"\n{category.name}"
                embed.add_field(
                    name=channel.name,
                    value=field_value,
                )
        else:
            embed.title = "There are no listed categories."
            embed.description = f"You can add one with the following command:\n`/calendar add <category> <channel>`"

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="add", description="Add a channel category to the calendar")
    @app_commands.describe(
        category_id_str="The ID of the category to add",
        channel="The channel to send the calendar to"
    )
    @app_commands.rename(
        category_id_str="category_id",
    )
    async def add_to_calendar(self, interaction: Interaction, category_id_str: str, channel: Optional[TextChannel] = None):
        assert interaction.guild is not None
        assert interaction.channel is not None

        try:
            category_id = int(category_id_str)
        except ValueError:
            raise CustomException(
                "Invalid category",
                "Not a valid ID"
            )

        category = interaction.guild.get_channel(category_id)
        if not category or not isinstance(category, CategoryChannel):
            raise CustomException(
                "Invalid category",
                "ID does not belong to a channel category"
            )
        
        if not channel:
            if not isinstance(interaction.channel, TextChannel):
                raise CustomException(
                    "Invalid channel",
                    "You must be in a normal text channel or specify one using the optional `channel` parameter."
                )
            channel = interaction.channel

        try:
            CalendarCategory.load(category.id, channel.id)
        except ValueError:
            pass
        else:
            raise CustomException(
                "Invalid category"
                "Category is already added"
            )

        await CalendarCategory.create(category, channel)

        await interaction.response.send_message(embed=get_success_embed(
            "Category added",
            f"**{category.name}** is now part of {channel.mention}."
        ), ephemeral=True)

    @tasks.loop(minutes=10)
    async def calendar_updater(self):
        try:
            for calendar in CalendarCategory.load_all():
                message = await calendar.get_message()
                category = await calendar.get_category()

                if not (message and category):
                    calendar.delete()
                    continue
                
                try:
                    games = await calendar.get_games()
                    embed = games_to_calendar_embed(category, games)
                    await message.edit(embed=embed)
                except:
                    print("Failed to update calendar in channel", message.channel.id, "for category", category.id)
                    traceback.print_exc()
        except:
            print(f'Explosions! Calendar failed to update...')
            traceback.print_exc()
    @calendar_updater.before_loop
    async def calendar_updater_before_loop(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(minutes=10)
    async def channel_emoji_updater(self):
        try:
            games = Game.load_all()
            for game in games:
                channel = self.bot.get_channel(game.channel_id)
                if channel:
                    assert isinstance(channel, TextChannel)
                    new_name = channel.name
                    if any(
                        new_name.startswith(emoji.value)
                        for emoji in ChannelEmojis
                    ):
                        new_name = new_name[1:]
                    
                    if game.score:
                        emoji = ChannelEmojis.FINISHED
                    elif game.has_started():
                        emoji = ChannelEmojis.ONGOING
                    elif game.is_done():
                        emoji = ChannelEmojis.PLANNED
                    else:
                        emoji = ChannelEmojis.OFFERING
                    
                    new_name = emoji.value + new_name
                    await channel.edit(name=new_name)
        except:
            print(f'Explosions! Channel names failed to update...')
            traceback.print_exc()
    @channel_emoji_updater.before_loop
    async def channel_emoji_updater_before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(CalendarCog(bot))