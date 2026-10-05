"""
Official OAuth2 Mail Agent for Gmail & Outlook
Manages 1-click Google OAuth2 & Microsoft Graph authentication, token rotation,
and autonomous inbox synchronization & reply dispatch.
"""

import json
import base64
import urllib.parse
from email.utils import parseaddr
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.core.event_logger import agent_logger
from backend.app.core.security import decrypt_secret, encrypt_secret

class OAuthMailAgent:
    def __init__(self):
        # Google OAuth constants
        self.google_auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        self.google_token_endpoint = "https://oauth2.googleapis.com/token"
        self.google_scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/userinfo.email"
        ]

        # Microsoft OAuth constants
        self.ms_auth_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        self.ms_token_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        self.ms_scopes = [
            "offline_access",
            "User.Read",
            "Mail.Read",
            "Mail.Send"
        ]

    # ==================== Google OAuth2 Flow ====================
    def get_google_auth_url(self) -> str:
        """Generates Google OAuth consent screen URL."""
        if (not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET) and not settings.DEMO_DATA_ENABLED:
            raise RuntimeError("Google OAuth için GOOGLE_CLIENT_ID ve GOOGLE_CLIENT_SECRET ayarlanmalı.")
        client_id = settings.GOOGLE_CLIENT_ID or "mock-google-client-id.apps.googleusercontent.com"
        redirect_uri = settings.GOOGLE_REDIRECT_URI
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.google_scopes),
            "access_type": "offline",
            "prompt": "consent"
        }
        return f"{self.google_auth_endpoint}?{urllib.parse.urlencode(params)}"

    async def handle_google_callback(self, code: str) -> Dict[str, Any]:
        """Exchanges Google auth code for tokens and registers user in DB."""
        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET
        redirect_uri = settings.GOOGLE_REDIRECT_URI

        # In dev/mock mode if no real Google credentials provided
        if not client_id or not client_secret:
            if not settings.DEMO_DATA_ENABLED:
                raise RuntimeError("Google OAuth kimlik bilgileri eksik; sahte hesap oluşturulmadı.")
            mock_email = "candidate.career@gmail.com"
            self._save_oauth_account(
                provider="google",
                email=mock_email,
                access_token="mock_google_access_token_xyz",
                refresh_token="mock_google_refresh_token_abc",
                expires_in=3600,
                scope=" ".join(self.google_scopes)
            )
            agent_logger.log_event("OAUTH_MAIL", f"Connected Google account (Simulated Mode): {mock_email}")
            return {
                "status": "SUCCESS",
                "provider": "google",
                "email": mock_email,
                "message": "Google hesabı başarıyla bağlandı (Geliştirici / Simülasyon Modu)."
            }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.google_token_endpoint,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            token_data = resp.json()
            if resp.status_code != 200:
                return {"status": "ERROR", "message": token_data.get("error_description", "Token exchange failed.")}

            # Fetch user email
            user_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )
            user_email = user_resp.json().get("email", "unknown@gmail.com")

            self._save_oauth_account(
                provider="google",
                email=user_email,
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                expires_in=token_data.get("expires_in", 3600),
                scope=token_data.get("scope", "")
            )

            agent_logger.log_event("OAUTH_MAIL", f"Successfully authenticated Google OAuth for {user_email}")
            return {
                "status": "SUCCESS",
                "provider": "google",
                "email": user_email,
                "message": f"Google hesabı ({user_email}) başarıyla bağlandı."
            }

    # ==================== Microsoft Outlook Flow ====================
    def get_microsoft_auth_url(self) -> str:
        """Generates Microsoft Azure AD OAuth consent screen URL."""
        if (not settings.MICROSOFT_CLIENT_ID or not settings.MICROSOFT_CLIENT_SECRET) and not settings.DEMO_DATA_ENABLED:
            raise RuntimeError("Microsoft OAuth için MICROSOFT_CLIENT_ID ve MICROSOFT_CLIENT_SECRET ayarlanmalı.")
        client_id = settings.MICROSOFT_CLIENT_ID or "mock-ms-client-id-0001"
        redirect_uri = settings.MICROSOFT_REDIRECT_URI
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": " ".join(self.ms_scopes)
        }
        return f"{self.ms_auth_endpoint}?{urllib.parse.urlencode(params)}"

    async def handle_microsoft_callback(self, code: str) -> Dict[str, Any]:
        """Exchanges Microsoft auth code for tokens and saves to DB."""
        client_id = settings.MICROSOFT_CLIENT_ID
        client_secret = settings.MICROSOFT_CLIENT_SECRET
        redirect_uri = settings.MICROSOFT_REDIRECT_URI

        if not client_id or not client_secret:
            if not settings.DEMO_DATA_ENABLED:
                raise RuntimeError("Microsoft OAuth kimlik bilgileri eksik; sahte hesap oluşturulmadı.")
            mock_email = "candidate.career@outlook.com"
            self._save_oauth_account(
                provider="microsoft",
                email=mock_email,
                access_token="mock_ms_access_token_xyz",
                refresh_token="mock_ms_refresh_token_abc",
                expires_in=3600,
                scope=" ".join(self.ms_scopes)
            )
            agent_logger.log_event("OAUTH_MAIL", f"Connected Microsoft account (Simulated Mode): {mock_email}")
            return {
                "status": "SUCCESS",
                "provider": "microsoft",
                "email": mock_email,
                "message": "Microsoft Outlook hesabı başarıyla bağlandı (Simülasyon Modu)."
            }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.ms_token_endpoint,
                data={
                    "client_id": client_id,
                    "scope": " ".join(self.ms_scopes),
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                    "client_secret": client_secret
                }
            )
            token_data = resp.json()
            if resp.status_code != 200:
                return {"status": "ERROR", "message": token_data.get("error_description", "Token exchange failed.")}

            # Fetch profile
            me_resp = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )
            ms_email = me_resp.json().get("mail") or me_resp.json().get("userPrincipalName") or "candidate@outlook.com"

            self._save_oauth_account(
                provider="microsoft",
                email=ms_email,
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                expires_in=token_data.get("expires_in", 3600),
                scope=token_data.get("scope", "")
            )

            agent_logger.log_event("OAUTH_MAIL", f"Successfully authenticated Microsoft OAuth for {ms_email}")
            return {
                "status": "SUCCESS",
                "provider": "microsoft",
                "email": ms_email,
                "message": f"Microsoft hesabı ({ms_email}) başarıyla bağlandı."
            }

    # ==================== Account Storage & Token Management ====================
    def _save_oauth_account(
        self, provider: str, email: str, access_token: str,
        refresh_token: Optional[str], expires_in: int, scope: str
    ):
        conn = get_db_connection()
        cursor = conn.cursor()
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        cursor.execute("""
            INSERT INTO oauth_accounts (
                provider, account_email, access_token, refresh_token, expires_at, scope, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', CURRENT_TIMESTAMP)
            ON CONFLICT(provider) DO UPDATE SET
                account_email = excluded.account_email,
                access_token = excluded.access_token,
                refresh_token = coalesce(excluded.refresh_token, oauth_accounts.refresh_token),
                expires_at = excluded.expires_at,
                scope = excluded.scope,
                status = 'ACTIVE',
                updated_at = CURRENT_TIMESTAMP
        """, (provider, email, encrypt_secret(access_token), encrypt_secret(refresh_token) if refresh_token else None, expires_at.strftime("%Y-%m-%d %H:%M:%S"), scope))
        conn.commit()
        conn.close()

    def get_accounts_status(self) -> Dict[str, Any]:
        """Returns connection status for all OAuth providers."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT provider, account_email, expires_at, status, updated_at FROM oauth_accounts")
        rows = cursor.fetchall()
        conn.close()

        accounts = {r["provider"]: dict(r) for r in rows}

        def auth_url_or_none(provider: str) -> Optional[str]:
            try:
                return self.get_google_auth_url() if provider == "google" else self.get_microsoft_auth_url()
            except RuntimeError:
                return None

        return {
            "google": {
                "connected": "google" in accounts and accounts["google"]["status"] == "ACTIVE",
                "email": accounts.get("google", {}).get("account_email"),
                "status": accounts.get("google", {}).get("status", "DISCONNECTED"),
                "auth_url": auth_url_or_none("google"),
                "configuration_required": not bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
            },
            "microsoft": {
                "connected": "microsoft" in accounts and accounts["microsoft"]["status"] == "ACTIVE",
                "email": accounts.get("microsoft", {}).get("account_email"),
                "status": accounts.get("microsoft", {}).get("status", "DISCONNECTED"),
                "auth_url": auth_url_or_none("microsoft"),
                "configuration_required": not bool(settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET),
            }
        }

    def disconnect(self, provider: str) -> Dict[str, Any]:
        """Removes linked OAuth credentials."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM oauth_accounts WHERE provider = ?", (provider,))
        conn.commit()
        conn.close()
        agent_logger.log_event("OAUTH_MAIL", f"Disconnected {provider} OAuth account.")
        return {"status": "SUCCESS", "message": f"{provider.capitalize()} hesabı bağlantısı kesildi."}

    # ==================== Live Email Sync Engine ====================
    def _account_expired(self, account: Any) -> bool:
        expires_at = account.get("expires_at") if isinstance(account, dict) else account["expires_at"]
        if not expires_at:
            return True
        try:
            parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00").replace(" ", "T"))
            if parsed.tzinfo:
                parsed = parsed.replace(tzinfo=None)
            return parsed <= datetime.now() + timedelta(seconds=60)
        except (TypeError, ValueError):
            return True

    async def _get_access_token(self, provider: str, account: Any) -> Optional[str]:
        """Return a usable token, refreshing OAuth credentials when needed."""
        current_token = decrypt_secret(account["access_token"])
        if not self._account_expired(account):
            return current_token

        refresh_token = decrypt_secret(account["refresh_token"]) if account["refresh_token"] else ""
        if not refresh_token:
            return current_token

        if provider == "google":
            data = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
            token_endpoint = self.google_token_endpoint
        elif provider == "microsoft":
            data = {
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(self.ms_scopes),
            }
            token_endpoint = self.ms_token_endpoint
        else:
            return None

        if not data.get("client_id") or not data.get("client_secret"):
            return current_token

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(token_endpoint, data=data)
        if response.status_code >= 400:
            agent_logger.log_event("OAUTH_MAIL", f"{provider} access token refresh failed ({response.status_code}).")
            return None

        token_data = response.json()
        new_token = token_data.get("access_token")
        if not new_token:
            return None
        expires_in = int(token_data.get("expires_in", 3600))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE oauth_accounts SET access_token = ?, expires_at = ?, updated_at = CURRENT_TIMESTAMP WHERE provider = ?",
            (encrypt_secret(new_token), (datetime.now() + timedelta(seconds=expires_in)).strftime("%Y-%m-%d %H:%M:%S"), provider),
        )
        conn.commit()
        conn.close()
        return new_token

    @staticmethod
    def _decode_gmail_part(part: Dict[str, Any]) -> str:
        body = part.get("body", {})
        encoded = body.get("data")
        if encoded:
            try:
                return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8", errors="replace")
            except (ValueError, UnicodeDecodeError):
                return ""
        for child in part.get("parts", []) or []:
            decoded = OAuthMailAgent._decode_gmail_part(child)
            if decoded:
                return decoded
        return ""

    async def _fetch_gmail_messages(self, access_token: str) -> List[Dict[str, Any]]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            listing = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params={"labelIds": "INBOX", "q": "is:unread", "maxResults": 20},
            )
            listing.raise_for_status()
            messages = []
            for item in listing.json().get("messages", []):
                detail = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}",
                    headers=headers,
                    params={"format": "full"},
                )
                detail.raise_for_status()
                payload = detail.json().get("payload", {})
                header_map = {
                    h.get("name", "").lower(): h.get("value", "")
                    for h in payload.get("headers", [])
                }
                sender_name, sender_email = parseaddr(header_map.get("from", ""))
                messages.append({
                    "external_message_id": f"gmail:{item['id']}",
                    "sender_email": sender_email or header_map.get("from", "unknown@example.com"),
                    "sender_name": sender_name,
                    "subject": header_map.get("subject", "(Konu yok)"),
                    "body_text": self._decode_gmail_part(payload)[:20000],
                })
            return messages

    async def _fetch_microsoft_messages(self, access_token: str) -> List[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Prefer": 'outlook.body-content-type="text"',
        }
        params = {
            "$filter": "isRead eq false",
            "$top": "20",
            "$select": "id,subject,body,from,receivedDateTime",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            result = []
            for item in response.json().get("value", []):
                sender = item.get("from", {}).get("emailAddress", {})
                body = item.get("body", {}).get("content", "")
                result.append({
                    "external_message_id": f"microsoft:{item.get('id', '')}",
                    "sender_email": sender.get("address", "unknown@example.com"),
                    "sender_name": sender.get("name", ""),
                    "subject": item.get("subject", "(Konu yok)"),
                    "body_text": body[:20000],
                })
            return result

    async def sync_emails(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Pulls recent unread messages from connected Gmail or Outlook accounts,
        and feeds them directly into the Inbox Automation Agent.
        """
        from backend.app.modules.outcome.inbox_agent import inbox_agent

        status = self.get_accounts_status()
        providers_to_sync = [p for p in (["google", "microsoft"] if not provider else [provider]) if status.get(p, {}).get("connected")]

        if not providers_to_sync:
            return {
                "status": "NO_ACCOUNT",
                "synced_count": 0,
                "message": "Bağlı aktif OAuth e-posta hesabı bulunamadı. Lütfen Google veya Outlook bağlayınız."
            }

        synced_count = 0
        duplicate_count = 0
        errors = []
        new_messages = []

        for prov in providers_to_sync:
            agent_logger.log_event("OAUTH_MAIL", f"Checking incoming emails for {prov.capitalize()}...")
            
            # Fetch stored account
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM oauth_accounts WHERE provider = ?", (prov,))
            account = cursor.fetchone()
            conn.close()

            if not account:
                continue

            # For simulated/demo accounts or mock tokens, inject high-fidelity real world employer responses
            stored_token = decrypt_secret(account["access_token"]) if account else ""
            if account and "mock" in stored_token and settings.DEMO_DATA_ENABLED:
                mock_payloads = [
                    {
                        "external_message_id": f"{prov}:mock-interview-invitation",
                        "sender_email": "talent@databricks.com",
                        "sender_name": "Databricks Recruiting",
                        "subject": "Interview Invitation: Staff Distributed Systems Engineer",
                        "body_text": "Hi Alperen,\n\nWe were really impressed by your portfolio on autonomous agent engines. We would like to invite you for a 45-minute architectural discussion:\nhttps://meet.google.com/abc-defg-hij\n\nLooking forward to meeting you!"
                    }
                ]
                fetched_messages = mock_payloads
            elif account and "mock" in stored_token:
                errors.append({"provider": prov, "error": "Sahte OAuth hesabı normal çalışma modunda kullanılmıyor. Gerçek OAuth hesabını yeniden bağlayın."})
                continue
            else:
                try:
                    token = await self._get_access_token(prov, account)
                    if not token:
                        errors.append({"provider": prov, "error": "Access token alınamadı veya yenilenemedi."})
                        continue
                    fetched_messages = (
                        await self._fetch_gmail_messages(token)
                        if prov == "google"
                        else await self._fetch_microsoft_messages(token)
                    )
                except httpx.HTTPError as exc:
                    errors.append({"provider": prov, "error": f"Mail sağlayıcı isteği başarısız: {exc}"})
                    continue

            for message in fetched_messages:
                res = await inbox_agent.ingest_incoming_email(
                    sender_email=message["sender_email"],
                    sender_name=message.get("sender_name", ""),
                    subject=message["subject"],
                    body_text=message["body_text"],
                    source_provider=prov,
                    external_message_id=message["external_message_id"],
                )
                if res.get("duplicate"):
                    duplicate_count += 1
                else:
                    new_messages.append(res)
                    synced_count += 1

        processed_count = synced_count + duplicate_count
        return {
            "status": "PARTIAL" if errors and processed_count else ("ERROR" if errors and not processed_count else "SUCCESS"),
            # synced_count is the number fetched/processed this run; new_count
            # excludes idempotent duplicates and is the useful notification KPI.
            "synced_count": processed_count,
            "new_count": synced_count,
            "duplicate_count": duplicate_count,
            "errors": errors,
            "messages": new_messages,
            "message": f"{synced_count} yeni e-posta senkronize edildi ve Inbox AI'a aktarıldı."
        }

oauth_mail_agent = OAuthMailAgent()
