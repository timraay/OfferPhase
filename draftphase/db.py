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
            score TEXT(32),
            max_num_offers INTEGER NOT NULL,
            flip_coin BOOL,
            flip_advantage BOOL,
            flip_sides BOOL,
            stream_delay INTEGER
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL REFERENCES games(channel_id) ON DELETE CASCADE,
            offer_no INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            map TEXT(20),
            environment TEXT(20),
            layout TEXT(5),
            accepted BOOL
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS casters (
            user_id INTEGER PRIMARY KEY,
            name TEXT(32) NOT NULL,
            channel_url TEXT(100) NOT NULL
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS streams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL REFERENCES games(channel_id) ON DELETE CASCADE,
            caster_id INTEGER NOT NULL REFERENCES casters(user_id) ON DELETE CASCADE,
            lang TEXT(4) NOT NULL
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL REFERENCES games(channel_id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES casters(user_id) ON DELETE CASCADE,
            team1_score INTEGER NOT NULL
        )
        """)
        cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_game_id_user_id ON predictions (game_id, user_id)
        """)

        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS calendar (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            PRIMARY KEY(channel_id, category_id)
        )
        """)
