import json
import os
import boto3
from typing import Optional, List, Dict, Any, Tuple
from botocore.exceptions import ClientError
from datetime import datetime

from blogboard.config.settings import app_settings

# Local storage directory (used as fallback when R2 is not configured)
LOCAL_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "blogboard", "web")


def _r2_is_configured() -> bool:
    """Check if R2 credentials are actually configured."""
    return bool(app_settings.r2.ACCOUNT_ID and app_settings.r2.ACCESS_KEY_ID and app_settings.r2.SECRET_ACCESS_KEY)


class R2StorageService:
    """
    Unified storage service for Cloudflare R2.
    Falls back to local file storage when R2 is not configured.
    """

    def __init__(self):
        self.bucket_name = app_settings.r2.BUCKET_NAME.strip(' ="'\ ') if app_settings.r2.BUCKET_NAME else ""
        self._r2_enabled = _r2_is_configured()
        
        if self._r2_enabled:
            self.client = boto3.client(
                service_name="s3",
                endpoint_url=f"https://{app_settings.r2.ACCOUNT_ID}.r2.cloudflarestorage.com",
                aws_access_key_id=app_settings.r2.ACCESS_KEY_ID,
                aws_secret_access_key=app_settings.r2.SECRET_ACCESS_KEY,
                region_name="auto"
            )
        else:
            os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)

    def _local_path(self, key: str) -> str:
        return os.path.join(LOCAL_STORAGE_DIR, key)

    def get_object(self, key: str) -> Optional[str]:
        if self._r2_enabled:
            try:
                response = self.client.get_object(Bucket=self.bucket_name, Key=key)
                return response["Body"].read().decode("utf-8")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    return None
                print(f"[ERROR] R2 get_object ({key}): {e}")
                return None
            except Exception as e:
                print(f"[ERROR] Unexpected error fetching {key}: {e}")
                return None
        else:
            # Local fallback
            local = self._local_path(key)
            if os.path.exists(local):
                with open(local, "r", encoding="utf-8") as f:
                    return f.read()
            return None

    def put_object(self, key: str, data: str, content_type: str = "text/plain") -> bool:
        if self._r2_enabled:
            try:
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=data.encode("utf-8"),
                    ContentType=content_type
                )
                print(f"  ✅ Uploaded to R2: {self.bucket_name}/{key}")
                return True
            except ClientError as e:
                print(f"[ERROR] Failed to upload {key} to R2: {e}")
                return False
        else:
            # Local fallback
            local = self._local_path(key)
            os.makedirs(os.path.dirname(local), exist_ok=True)
            with open(local, "w", encoding="utf-8") as f:
                f.write(data)
            print(f"  ✅ Saved locally: {local}")
            return True

    def get_json(self, key: str) -> Optional[List[Dict[str, Any]]]:
        data = self.get_object(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                print(f"[WARN] Failed to decode JSON from {key}. Starting fresh.")
                return []
        return []

    def get_articles_json(self, domain: str) -> List[Dict[str, Any]]:
        return self.get_json(f"blogs/{domain}/articles.json") or []

    def save_articles_json(self, domain: str, articles: List[Dict[str, Any]]) -> bool:
        json_str = json.dumps(articles, indent=2, ensure_ascii=False)
        return self.put_object(f"blogs/{domain}/articles.json", json_str, content_type="application/json")

    def get_recent_history(self, domain: str, limit: int = 3) -> List[Dict[str, Any]]:
        articles = self.get_articles_json(domain)
        sorted_articles = sorted(articles, key=lambda x: x.get("date", ""), reverse=True)
        recent = sorted_articles[:limit]
        return [{
            "title": a.get("title"),
            "topic": a.get("topic"),
            "subtopics": a.get("subtopics", "")
        } for a in recent]

    def get_all_domains_last_updated(self) -> Dict[str, str]:
        latest_dates = {}
        for domain_slug in app_settings.tags.model_dump().keys():
            articles = self.get_articles_json(domain_slug)
            if not articles:
                latest_dates[domain_slug] = "Never"
            else:
                sorted_articles = sorted(articles, key=lambda x: x.get("date", ""), reverse=True)
                latest_dates[domain_slug] = sorted_articles[0].get("date", "Unknown")
        return latest_dates
