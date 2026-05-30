from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL 또는 SUPABASE_KEY 환경변수가 설정되지 않았습니다.")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client
