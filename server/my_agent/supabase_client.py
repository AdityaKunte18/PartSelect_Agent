from __future__ import annotations
import os
from typing import Optional
from supabase import create_client, Client

_sb: Optional[Client] = None

def sb() -> Client:
    global _sb
    if _sb is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment.")
        _sb = create_client(url, key)
    return _sb
