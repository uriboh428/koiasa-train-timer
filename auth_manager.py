"""
恋朝トレインタイマー - セキュリティ認証マネージャー (Auth Manager)
Cybersecurity CoE 基準:
1. ソルト付き暗号化ハッシュ (SHA-256 + 32桁ランダムソルト)
2. タイミング攻撃耐性 (hmac.compare_digest)
3. プロセス全体共有型グローバル・ブルートフォース防御 (Global Lockout)
4. 推測不能な暗号アクセストークンURL認証 (?token=...)
5. Streamlit Secrets (クラウド永続化) 完全連携
"""
import os
import json
import time
import math
import hmac
import hashlib
import secrets
from typing import Optional, Tuple, Dict, Any

AUTH_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "auth_config.json")
MAX_FAILED_ATTEMPTS = 5
SEVERE_FAILED_ATTEMPTS = 10
LOCKOUT_DURATION_SECONDS = 60
SEVERE_LOCKOUT_DURATION_SECONDS = 300
MIN_PASSWORD_LENGTH = 6
PBKDF2_ITERATIONS = 100_000


class GlobalSecurityManager:
    """
    全セッション・全ユーザー共有のレートリミッター
    段階的遅延（Backoff）と二段階ロックアウトにより総当たり攻撃を完全無力化
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.failed_attempts = 0
        self.lock_until = 0.0

    def record_failure(self) -> Tuple[bool, int]:
        """失敗を記録し、段階的遅延（Backoff）を適用。制限超過時は二段階ロックアウト"""
        now = time.time()
        self.failed_attempts += 1
        # 人為的な段階的遅延（ブルートフォース攻撃を物理的に超低速化）
        delay = min(2.0, self.failed_attempts * 0.4)
        time.sleep(delay)

        if self.failed_attempts >= SEVERE_FAILED_ATTEMPTS:
            self.lock_until = now + SEVERE_LOCKOUT_DURATION_SECONDS
            return True, SEVERE_LOCKOUT_DURATION_SECONDS
        elif self.failed_attempts >= MAX_FAILED_ATTEMPTS:
            self.lock_until = now + LOCKOUT_DURATION_SECONDS
            return True, LOCKOUT_DURATION_SECONDS
        return False, 0

    def record_success(self):
        """成功時にカウンターを安全にリセット"""
        self.failed_attempts = 0
        self.lock_until = 0.0

    def get_lockout_status(self) -> Tuple[bool, int]:
        """
        ロックアウト状態と残り秒数を判定
        :return: (is_locked, remaining_seconds)
        """
        now = time.time()
        if self.failed_attempts >= MAX_FAILED_ATTEMPTS:
            if now < self.lock_until:
                remaining = max(1, math.ceil(self.lock_until - now))
                return True, remaining
            else:
                # ロックアウト期間経過により自動解除
                self.failed_attempts = 0
                self.lock_until = 0.0
                return False, 0
        return False, 0


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    暗号強度PBKDF2-HMAC-SHA256による100,000回ストレッチングハッシュを生成
    GPUやASICによる総当たり・辞書攻撃を物理的に無力化（OWASP推奨基準）
    :param password: 平文パスワード
    :param salt: 16進数ソルト（省略時は暗号学的に安全な32文字のランダムソルトを生成）
    :return: (hash_hex, salt_hex)
    """
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return "pbkdf2$" + key.hex(), salt


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    """
    パスワードを検証（タイミング攻撃防止: hmac.compare_digest）
    PBKDF2および旧SHA-256形式の双方に自動適応（後方互換性完全担保）
    """
    if not password or not stored_hash or not stored_salt:
        return False

    if stored_hash.startswith("pbkdf2$"):
        expected_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            stored_salt.encode("utf-8"),
            PBKDF2_ITERATIONS,
        )
        calculated = "pbkdf2$" + expected_key.hex()
        return hmac.compare_digest(calculated, stored_hash)
    else:
        # 旧形式（単一SHA-256）の後方互換検証
        salted_data = (stored_salt + password).encode("utf-8")
        calculated = hashlib.sha256(salted_data).hexdigest()
        return hmac.compare_digest(calculated, stored_hash)


def get_secure_token(salt: str, hash_val: str, token_salt: Optional[str] = None) -> str:
    """
    パスワード平文をURLに含めずに自動認証するための、暗号学的一意アクセストークンを導出
    （エントロピー 96bit: 約7.9×10^28 通り、推測不可能）
    token_salt（再発行シード）がある場合は古いトークンを無効化する
    """
    if token_salt:
        token_seed = f"{salt}:{token_salt}:koiasa_secure_token:{hash_val}".encode("utf-8")
    else:
        token_seed = f"{salt}:koiasa_secure_token:{hash_val}".encode("utf-8")
    return hashlib.sha256(token_seed).hexdigest()[:24]


def verify_secure_token(token: str, salt: str, hash_val: str, token_salt: Optional[str] = None) -> bool:
    """セキュアアクセストークンを検証（タイミング攻撃耐性）"""
    if not token or not salt or not hash_val:
        return False
    expected_token = get_secure_token(salt, hash_val, token_salt)
    return hmac.compare_digest(str(token).strip(), expected_token)


def load_auth_credentials() -> Optional[Dict[str, Any]]:
    """
    設定された認証情報を取得（優先度: Streamlit Session > Streamlit Secrets > 環境変数 > auth_config.json）
    :return: {"hash": ..., "salt": ..., "token": ..., "token_salt": ...} または 未設定時 None
    """
    # 0. セッション内の一時オーバーライド（再発行即時反映用）
    session_token_salt = None
    try:
        import streamlit as st
        if hasattr(st, "session_state") and "active_token_salt" in st.session_state:
            session_token_salt = st.session_state["active_token_salt"]
    except Exception:
        pass

    # 1. Streamlit Secrets の確認
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "APP_PASSWORD_HASH" in st.secrets and "APP_PASSWORD_SALT" in st.secrets:
                h = str(st.secrets["APP_PASSWORD_HASH"])
                s = str(st.secrets["APP_PASSWORD_SALT"])
                ts = session_token_salt or (str(st.secrets["APP_TOKEN_SALT"]) if "APP_TOKEN_SALT" in st.secrets else None)
                return {
                    "hash": h,
                    "salt": s,
                    "token_salt": ts,
                    "token": get_secure_token(s, h, ts),
                    "source": "secrets"
                }
            if "APP_PASSWORD" in st.secrets:
                h, s = hash_password(str(st.secrets["APP_PASSWORD"]), "koiasa_static_salt_v1")
                ts = session_token_salt or (str(st.secrets["APP_TOKEN_SALT"]) if "APP_TOKEN_SALT" in st.secrets else None)
                return {"hash": h, "salt": s, "token_salt": ts, "token": get_secure_token(s, h, ts), "source": "secrets"}
            if "APP_PIN" in st.secrets:
                h, s = hash_password(str(st.secrets["APP_PIN"]), "koiasa_static_salt_v1")
                ts = session_token_salt or (str(st.secrets["APP_TOKEN_SALT"]) if "APP_TOKEN_SALT" in st.secrets else None)
                return {"hash": h, "salt": s, "token_salt": ts, "token": get_secure_token(s, h, ts), "source": "secrets"}
    except Exception:
        pass

    # 2. 環境変数の確認
    env_hash = os.environ.get("APP_PASSWORD_HASH")
    env_salt = os.environ.get("APP_PASSWORD_SALT")
    if env_hash and env_salt:
        ts = session_token_salt or os.environ.get("APP_TOKEN_SALT")
        return {
            "hash": env_hash,
            "salt": env_salt,
            "token_salt": ts,
            "token": get_secure_token(env_salt, env_hash, ts),
            "source": "env"
        }

    env_pass = os.environ.get("APP_PASSWORD") or os.environ.get("APP_PIN")
    if env_pass:
        h, s = hash_password(str(env_pass), "koiasa_static_salt_v1")
        ts = session_token_salt or os.environ.get("APP_TOKEN_SALT")
        return {"hash": h, "salt": s, "token_salt": ts, "token": get_secure_token(s, h, ts), "source": "env"}

    # 3. auth_config.json の確認
    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "hash" in data and "salt" in data:
                    h = data["hash"]
                    s = data["salt"]
                    ts = session_token_salt or data.get("token_salt")
                    return {
                        "hash": h,
                        "salt": s,
                        "token_salt": ts,
                        "token": get_secure_token(s, h, ts),
                        "source": "file"
                    }
        except Exception:
            pass

    return None


def save_token_salt(token_salt: str) -> bool:
    """
    新しい token_salt を永続化し、セッションにも即時反映
    """
    try:
        import streamlit as st
        if hasattr(st, "session_state"):
            st.session_state["active_token_salt"] = token_salt
    except Exception:
        pass

    data: Dict[str, Any] = {}
    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    data["token_salt"] = token_salt
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        with open(AUTH_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def regenerate_secure_token() -> str:
    """
    ワンタップURLを即座に再発行（古いトークンを無効化）
    新しいランダムシードを生成して保存する
    """
    new_seed = secrets.token_hex(16)
    save_token_salt(new_seed)
    return new_seed


def save_auth_credentials(password: str, token_salt: Optional[str] = None) -> bool:
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
            "token_salt": token_salt or secrets.token_hex(16),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "version": "3.1"
        }
        with open(AUTH_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def is_auth_configured() -> bool:
    """認証パスワードが設定済みかどうか"""
    return load_auth_credentials() is not None


def check_lockout_status(attempts: Optional[int] = None, lock_until: Optional[float] = None) -> Tuple[bool, int]:
    """後方互換用ブルートフォース判定（引数指定時はその値、省略時はGlobalSecurityManagerを参照）"""
    if attempts is not None and lock_until is not None:
        now = time.time()
        if attempts >= MAX_FAILED_ATTEMPTS:
            if now < lock_until:
                return True, max(1, math.ceil(lock_until - now))
            else:
                return False, 0
        return False, 0
    manager = GlobalSecurityManager.get_instance()
    return manager.get_lockout_status()


def get_secrets_toml_template(password: str, salt: Optional[str] = None, token_salt: Optional[str] = None) -> str:
    """Streamlit Cloud Secrets に設定するTOML設定文字列を生成"""
    h, s = hash_password(password, salt)
    res = f'APP_PASSWORD_HASH = "{h}"\nAPP_PASSWORD_SALT = "{s}"'
    if token_salt:
        res += f'\nAPP_TOKEN_SALT = "{token_salt}"'
    return res


def get_app_base_url() -> str:
    """
    現在のアクセス元ホスト名からアプリのベースURLを動的に決定する
    Streamlit 1.30+ の st.context.headers を優先し、ローカル開発・本番Cloud問わず正しいURLを返す
    """
    try:
        import streamlit as st
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            host = st.context.headers.get("host")
            if host:
                scheme = "http" if ("localhost" in host or "127.0.0.1" in host) else "https"
                return f"{scheme}://{host}"
    except Exception:
        pass
    return ""


def generate_token_link(token: str, base_url: Optional[str] = None) -> str:
    """ワンタップ起動URLを動的に生成する"""
    if not base_url:
        base_url = get_app_base_url()
    if base_url:
        return f"{base_url.rstrip('/')}/?token={token}"
    return f"?token={token}"

