import os
from supabase import create_client, Client

supabase: Client = None


def init_supabase():
    global supabase

    SUPABASE_PROJECT_URL = os.getenv("SUPABASE_PROJECT_URL")
    SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

    if not SUPABASE_PROJECT_URL or not SUPABASE_API_KEY:
        raise ValueError(
            "SUPABASE_PROJECT_URL and SUPABASE_API_KEY environment variables must be set"
        )

    supabase = create_client(SUPABASE_PROJECT_URL, SUPABASE_API_KEY)
    return supabase


def get_supabase() -> Client:
    global supabase
    if supabase is None:
        supabase = init_supabase()
    return supabase
