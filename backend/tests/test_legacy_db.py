"""The live Railway database was created by the first version of the site. The new app must adopt it."""
import json

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app import catalog
from app.database import Base
from app.migrate import add_missing_columns
from app.models import Album, Counter, Message, Subscriber, Track

OLD_SCHEMA = [
    "CREATE TABLE counters (name VARCHAR(50) PRIMARY KEY, value BIGINT NOT NULL)",
    "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at DATETIME NOT NULL, name VARCHAR(120) NOT NULL, email VARCHAR(254) NOT NULL, message TEXT NOT NULL, emailed BOOLEAN NOT NULL)",
    "CREATE TABLE catalog (id INTEGER PRIMARY KEY, data TEXT NOT NULL, source_hash VARCHAR(64) NOT NULL, updated_at DATETIME NOT NULL)",
    "CREATE TABLE subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, email VARCHAR(254) NOT NULL UNIQUE, token VARCHAR(64) NOT NULL UNIQUE, created_at DATETIME NOT NULL, unsubscribed_at DATETIME)",
]
BLOB = {"albums": [{"id": "legacy-album", "title": "Legacy Album", "number": "Album 01", "cover": "/c.jpg", "chips": ["a"],
                    "tracks": [{"title": "Synced Later", "url": "https://suno.com/song/11111111-1111-1111-1111-111111111111", "lyrics": "la"}]}]}


def test_new_app_adopts_the_old_database(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with eng.begin() as c:
        for stmt in OLD_SCHEMA:
            c.execute(text(stmt))
        c.execute(text("INSERT INTO counters VALUES ('views', 4321)"))
        c.execute(text("INSERT INTO messages (created_at, name, email, message, emailed) VALUES ('2026-10-01 10:00:00', 'Promoter', 'p@x.co', 'Book me a show', 1)"))
        c.execute(text("INSERT INTO subscribers (email, token, created_at, unsubscribed_at) VALUES ('stay@x.co', 'tok1', '2026-10-01 10:00:00', NULL), ('gone@x.co', 'tok2', '2026-10-01 10:00:00', '2026-10-05 10:00:00')"))
        c.execute(text("INSERT INTO catalog VALUES (1, :d, 'h', '2026-10-01 10:00:00')"), {"d": json.dumps(BLOB)})

    Base.metadata.create_all(eng)       # creates only the tables that do not exist yet
    add_missing_columns(eng)            # adds messages.is_read and the new track/album columns
    S = sessionmaker(bind=eng, expire_on_commit=False)

    with S() as db:
        assert catalog.seed_catalog(db) == 1                       # from the old catalog table, not music.json
        assert db.scalar(select(Album.title)) == "Legacy Album"
        assert db.scalar(select(Track.title)) == "Synced Later"
        assert db.get(Counter, "views").value == 4321              # view count carried over
        old = db.scalar(select(Message))
        assert old.body == "Book me a show" and old.is_read is False
        assert db.scalar(select(func.count(Subscriber.id)).where(Subscriber.active)) == 1  # only 'stay@x.co'
        gone = db.scalar(select(Subscriber).where(Subscriber.email == "gone@x.co"))
        assert gone.active is False and gone.token == "tok2"      # old unsubscribe links keep working

        db.add(Message(name="New", email="n@x.co", body="hello"))  # old NOT NULL columns are satisfied
        db.add(Subscriber(email="new@x.co"))
        db.commit()
        assert db.scalar(select(func.count(Message.id))) == 2
        assert db.scalar(select(func.count(Subscriber.id)).where(Subscriber.active)) == 2
