from draftphase.bot import DISCORD_BOT
from draftphase.config import get_config
from draftphase.db import create_tables

def _get_logs_format(name: str | None = None):
    if name:
        fmt = '[%(asctime)s][{}][%(levelname)s][%(module)s.%(funcName)s:%(lineno)s] %(message)s'.format(name)
    else:
        fmt = '[%(asctime)s][%(levelname)s][%(module)s.%(funcName)s:%(lineno)s] %(message)s'
    return fmt

import logging
logging.basicConfig(
    level=logging.INFO,
    format=_get_logs_format(name='other'),
    handlers=[
        logging.FileHandler(filename="app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

if __name__ == '__main__':
    create_tables()
    config = get_config()
    DISCORD_BOT.run(config.bot.token)
