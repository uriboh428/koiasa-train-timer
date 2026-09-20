"""
恋朝トレインタイマー - セキュリティ認証マネージャー (Auth Manager)
Cybersecurity CoE 基準: ソルト付き暗号化ハッシュ、タイミング攻撃耐性、ブルートフォース防御
"""
import os
import json
import time
import hmac
import hashlib
import secrets
from typing import Optional, Tuple, Dict, Any

AUTH_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "auth_config.json")
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 60
MIN_PASSWORD_LENGTH = 4


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    ソルト付きSHA-256ハッシュを生成（レインボーテーブル攻撃を防止）
    :param password: 平文パスワード
    :param salt: 16進数ソルト（省略時は暗号学的に安全な32文字のランダムソルトを生成）
    :return: (hash_hex, salt_hex)
    """
    if not salt:
        salt = secrets.token_hex(16)
    salted_data = (salt + password).encode("utf-8")
    hash_hex = hashlib.sha256(salted_data).hexdigest()
    return hash_hex, salt


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    """
    パスワードを検証（タイミング攻撃を防止するため hmac.compare_digest を使用）
    """
    if not password or not stored_hash or not stored_salt:
        return False
    calculated_hash, _ = hash_password(password, stored_salt)
    return hmac.compare_digest(calculated_hash, stored_hash)


def load_auth_credentials() -> Optional[Dict[str, str]]:
    """
    設定された認証情報を取得（優先度: Streamlit Secrets > 環境変数 > auth_config.json）
    :return: {"hash": ..., "salt": ...} または 未設定時 None
    """
    # 1. Streamlit Secrets の確認
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "APP_PASSWORD_HASH" in st.secrets and "APP_PASSWORD_SALT" in st.secrets:
                return {
                    "hash": str(st.secrets["APP_PASSWORD_HASH"]),
                    "salt": str(st.secrets["APP_PASSWORD_SALT"]),
                    "source": "secrets"
                }
            if "APP_PASSWORD" in st.secrets:
                h, s = hash_password(str(st.secrets["APP_PASSWORD"]), "koiasa_static_salt_v1")
                return {"hash": h, "salt": s, "source": "secrets"}
            if "APP_PIN" in st.secrets:
                h, s = hash_password(str(st.secrets["APP_PIN"]), "koiasa_static_salt_v1")
                return {"hash": h, "salt": s, "source": "secrets"}
    except Exception:
        pass

    # 2. 環境変数の確認
    env_hash = os.environ.get("APP_PASSWORD_HASH")
    env_salt = os.environ.get("APP_PASSWORD_SALT")
    if env_hash and env_salt:
        return {"hash": env_hash, "salt": env_salt, "source": "env"}

    env_pass = os.environ.get("APP_PASSWORD") or os.environ.get("APP_PIN")
    if env_pass:
        h, s = hash_password(str(env_pass), "koiasa_static_salt_v1")
        return {"hash": h, "salt": s, "source": "env"}

    # 3. auth_config.json の確認
    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "hash" in data and "salt" in data:
                    return {"hash": data["hash"], "salt": data["salt"], "source": "file"}
        except Exception:
            pass

    return None


def save_auth_credentials(password: str) -> bool:
    """
    新しいパスワードを暗号化ハッシュとして auth_config.json に保存
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False
    try:
        h, s = hash_password(password)
        data = {
            "hash": h,
            "salt": s,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "version": "1.0"
        }
        with open(AUTH_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def is_auth_configured() -> bool:
    """認証パスワードが設定済みかどうか"""
    return load_auth_credentials() is not None


import math


def check_lockout_status(attempts: int, lock_until: float) -> Tuple[bool, int]:
    """
    ブルートフォース攻撃防御のロック状態を判定
    :return: (is_locked, remaining_seconds)
    """
    current_time = time.time()
    if attempts >= MAX_FAILED_ATTEMPTS:
        if current_time < lock_until:
            remaining = max(1, math.ceil(lock_until - current_time))
            return True, remaining
        else:
            # ロック解除時刻を経過
            return False, 0
    return False, 0
