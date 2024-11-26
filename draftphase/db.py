from contextlib import contextmanager
import sqlite3

DB_CONN = sqlite3.connect("app.db")

@contextmanager
def get_cursor():
    cur = DB_CONN.cursor()
    try:
        yield cur
    except:
        raise
    else:
        DB_CONN.commit()
    finally:
        cur.close()


def create_tables():
    with get_cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            message_id INTEGER,
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            team1_id INTEGER NOT NULL,
            team2_id INTEGER NOT NULL,
            subtitle TEXT(100),
            start_time INTEGER,
            max_num_offers INTEGER NOT NULL,
            flip_sides BOOL,
            stream_delay INTEGER
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL REFERENCES games(channel_id) ON DELETE CASCADE,
            offer_no INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            map TEXT(20),
            environment TEXT(20),
            layout TEXT(5),
            accepted BOOL
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS streamers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL REFERENCES games(channel_id) ON DELETE CASCADE,
            lang TEXT(4) NOT NULL,
            name TEXT(64) NOT NULL,
            url TEXT(100) NOT NULL
        )
        """)
