import asyncio
import logging
import os
from pathlib import Path
from discord import Intents
from discord.ext import commands

DISCORD_COGS_PATH = Path("draftphase/cogs")

class Bot(commands.Bot):
    async def setup_hook(self):
        await load_all_cogs()
        await sync_commands()

        from draftphase.views.open_controls import (
            AcceptOfferButton, GetControlsButton, DeclineOfferButton, CreateOfferConfirmButton,
            SelectOfferSelect, CreateOfferSelect, TakeAdvantageButton, GiveAdvantageButton,
        )
        from draftphase.views.cast_prediction import CastPredictionSelect
        from draftphase.views.poll import PollCastVoteButton
        self.add_dynamic_items(
            AcceptOfferButton, GetControlsButton, DeclineOfferButton, CreateOfferConfirmButton,
            SelectOfferSelect, CreateOfferSelect, TakeAdvantageButton, GiveAdvantageButton,
            CastPredictionSelect,
            PollCastVoteButton,
        )

INTENTS = Intents.default()
INTENTS.members = True

DISCORD_BOT = Bot(
    intents=INTENTS,
    command_prefix=commands.when_mentioned,
    case_insensitive=True
)

async def load_all_cogs():
    cog_path_template = DISCORD_COGS_PATH.as_posix().replace("/", ".") + ".{}"
    for cog_name in os.listdir(DISCORD_COGS_PATH):
        if cog_name.endswith(".py"):
            try:
                cog_path = cog_path_template.format(os.path.splitext(cog_name)[0])
                await DISCORD_BOT.load_extension(cog_path)
            except:
                logging.exception(f"Cog {cog_name} cannot be loaded")
                pass
    logging.info('Loaded all cogs. Successfully initialized %s', DISCORD_BOT.user)

async def sync_commands():
    try:
        await asyncio.wait_for(DISCORD_BOT.tree.sync(), timeout=5)
        logging.info('Synced app commands')
    except asyncio.TimeoutError:
        logging.warning("Didn't sync app commands. This was likely last done recently, resulting in rate limits.")
