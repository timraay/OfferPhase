from configparser import ConfigParser, MissingSectionHeaderError

_CONFIG: ConfigParser | None = None
def get_config() -> ConfigParser:
    global _CONFIG
    if not _CONFIG:
        parser = ConfigParser()
        try:
            parser.read('config.ini', encoding='utf-8')
        except MissingSectionHeaderError:
            # Most likely a BOM was added. This can happen automatically when
            # saving the file with Notepad. Let's open with UTF-8-BOM instead.
            parser.read('config.ini', encoding='utf-8-sig')
        _CONFIG = parser
    return _CONFIG
