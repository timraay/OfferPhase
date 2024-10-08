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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id INTEGER NOT NULL,
            player2_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            flip_sides BOOL,
            max_offer_limit INTEGER NOT NULL
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
            offer_no INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            map TEXT(20),
            environment TEXT(10),
            layout TEXT(5),
            accepted INTEGER
        );
        """)
