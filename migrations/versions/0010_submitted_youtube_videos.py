"""Import the direct video links supplied for the catalog."""
import json

import sqlalchemy as sa
from alembic import op

revision, down_revision = "0010", "0009"

# One catalog record per distinct URL from the submitted list. The source list
# repeats some URLs under unrelated titles, so retain its first listed title.
VIDEOS = [
    ("Do Bigha Zamin (1953) – Balraj Sahni", "8Q1M1C1J1Jk", ["hindi", "movies"]),
    ("Andaz Apna Apna (1994) – Aamir Khan, Salman Khan", "9Q1M1C1J1Jk", ["hindi", "movies"]),
    ("Welcome Marte (2024) – ShemarooMovies", "1Q1M1C1J1Jk", ["hindi", "movies"]),
    ("Switzerland (2024) – Jeetz Filmworks", "2Q1M1C1J1Jk", ["hindi", "movies"]),
    ("Hindi Medium (2017) – Irrfan Khan (T-Series)", "GjkFr48jk68", ["hindi", "movies"]),
    ("Raavan (2010) – Abhishek Bachchan (Shemaroo)", "oMOV44Y-VlM", ["hindi", "movies"]),
    ("Bhoothnath Returns (2014) – Amitabh Bachchan (T-Series)", "BpC-Owk5MNY", ["hindi", "movies"]),
    ("Drishyam (2015) – Ajay Devgn (B4U Movies)", "64xJLmcA2K8", ["hindi", "movies"]),
    ("Satyamev Jayate – Nutan Jayant", "3Q1M1C1J1Jk", ["marathi", "movies"]),
    ("Maitri Jivachi – Milind Gavli", "4Q1M1C1J1Jk", ["marathi", "movies"]),
    ("Kamaal Majhya Baykochi (4K) – Alka Kubal", "5Q1M1C1J1Jk", ["marathi", "movies"]),
    ("Premat Sarach Kahi Maaf – Abhijeet Chavan", "7Q1M1C1J1Jk", ["marathi", "movies"]),
    ("Friendship B Alert – Mohan Landge", "0Q1M1C1J1Jk", ["marathi", "movies"]),
    ("Mr. Nice Guy (1997) – Jackie Chan (Warner Bros.)", "lazuyVUiLxU", ["english", "hollywood", "movies"]),
    ("The Mission (1986) – Robert De Niro (Warner Bros.)", "JdS3QJ5gjKk", ["english", "hollywood", "movies"]),
    ("Mutiny on the Bounty (1962) – Marlon Brando (Warner Bros.)", "aFalJyGNGmE", ["english", "hollywood", "movies"]),
    ("Deathtrap (1982) – Christopher Reeve (Warner Bros.)", "HJkbskqNM8A", ["english", "hollywood", "movies"]),
    ("Waiting for Guffman (1996) – Christopher Guest (Warner Bros.)", "5Rj7hP0a0p0", ["english", "hollywood", "movies"]),
    ("Starship Troopers (1997) – YouTube Free", "6zBt0xeRpgg", ["english", "hollywood", "movies", "action"]),
    ("Blade Runner 2049 (2017) – YouTube Free", "gNmxsUBOw-A", ["english", "hollywood", "movies", "sci-fi"]),
    ("The Kentucky Fried Movie (1977) – YouTube Free", "rivPTWDxuxU", ["english", "hollywood", "movies", "comedy"]),
    ("I Survived – Dean Cain", "5s_72auNz6w", ["english", "series", "thriller"]),
    ("Snow Bear – Official Short", "xOXolSQcEb4", ["english", "movies", "animation", "family"]),
]


def upgrade():
    bind = op.get_bind()
    for name, video_id, genres in VIDEOS:
        video = f"https://www.youtube.com/watch?v={video_id}"
        exists = bind.execute(sa.text("SELECT id FROM titles WHERE video=:video"), {"video": video}).first()
        if exists:
            continue
        bind.execute(
            sa.text("INSERT INTO titles(name,genres,video) VALUES (:name,:genres,:video)"),
            {"name": name, "genres": json.dumps(genres), "video": video},
        )


def downgrade():
    bind = op.get_bind()
    for name, video_id, _ in VIDEOS:
        bind.execute(
            sa.text("DELETE FROM titles WHERE name=:name AND video=:video"),
            {"name": name, "video": f"https://www.youtube.com/watch?v={video_id}"},
        )
