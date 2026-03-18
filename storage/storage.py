from dotenv import load_dotenv
import os
import json
from pathlib import Path

import genshin
from cryptography.fernet import Fernet

### Located here are:
###     load/save subscriptions
###     encrypt/decrypt helpers

# load .env file
load_dotenv()
ltuid_v2 = os.getenv('LTUID_V2')
ltoken_v2 = os.getenv('LTOKEN_V2')
encryption_key = os.getenv("ENCRYPTION_KEY", "")

DATA_PATH = Path("data/subscriptions.json")

### --- encrypt/decrypt helpers --- ###
# get fernet key
def get_fernet() -> Fernet:
    if not encryption_key:
        raise RuntimeError("ENCRYPTION_KEY is not set in .env")
    return Fernet(encryption_key.encode())

# encrypt
def encrypt_value(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()

# decrypt
def decrypt_value(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()

# load subscriptions -> dict (also create {} if file missing/bad)
def load_subscriptions() -> dict:
    # create if missing
    if not DATA_PATH.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text("{}", encoding='utf-8')
        return {}

    try:
        raw = DATA_PATH.read_text(encoding='utf-8')
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # reset bad file contents
    DATA_PATH.write_text("{}", encoding="utf-8")
    return {}

# write pretty JSON
def save_subscriptions(data: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(data, indent=2), encoding='utf-8')

# bot-server handshake
def build_genshin_client(user_ltuid: str | None = None, user_ltoken: str | None = None) -> genshin.Client:
    ltuid_v2 = user_ltuid or os.getenv("LTUID_V2", "")
    ltoken_v2 = user_ltoken or os.getenv("LTOKEN_V2", "")
    
    if not ltuid_v2 or not ltoken_v2:
        raise RuntimeError("No valid HoYoLab cookies available.")
    return genshin.Client({"ltuid_v2": ltuid_v2, "ltoken_v2": ltoken_v2})


def build_hsr_client(user_ltuid: str | None = None, user_ltoken: str | None = None) -> genshin.Client:
    # HSR and Genshin chronicle endpoints both use HoYoLab cookie auth.
    return build_genshin_client(user_ltuid, user_ltoken)