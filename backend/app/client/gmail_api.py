import os
import base64
import re
from html import unescape
from urllib.parse import urlparse, urlunparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def create_service(
    client_secret_file,
    api_name,
    api_version,
    scopes,
    prefix="",
    token_dir="token files",
):
    CLIENT_SECRET_FILE = client_secret_file
    API_SERVICE_NAME = api_name
    API_VERSION = api_version
    SCOPES = scopes

    creds = None
    working_dir = os.getcwd()
    token_file = f"token_{API_SERVICE_NAME}_{API_VERSION}{prefix}.json"

    ### Check if token dir exists first, if not, create the folder
    if not os.path.exists(os.path.join(working_dir, token_dir)):
        os.mkdir(os.path.join(working_dir, token_dir))

    if os.path.exists(os.path.join(working_dir, token_dir, token_file)):
        creds = Credentials.from_authorized_user_file(
            os.path.join(working_dir, token_dir, token_file), SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

    with open(os.path.join(working_dir, token_dir, token_file), "w") as token:
        token.write(creds.to_json())

    try:
        service = build(
            API_SERVICE_NAME, API_VERSION, credentials=creds, static_discovery=False
        )
        print(API_SERVICE_NAME, API_VERSION, "service created successfully")
        return service
    except Exception as e:
        print(e)
        print(f"Failed to create service instance for {API_SERVICE_NAME}")
        os.remove(os.path.join(working_dir, token_dir, token_file))
        return None


def clean_url_simple(url):
    """
    Simple URL cleaner - removes all query parameters
    """
    try:
        parsed = urlparse(url)
        
        # Keep only scheme, netloc, and path
        clean_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            '',  # remove params
            '',  # remove query
            ''   # remove fragment
        ))
        
        return clean_url
        
    except Exception:
        return url

def clean_email_body(body):
    """
    Clean up messy email body content
    """
    if not body:
        return body
    
    # Remove CSS content (media queries, style rules, etc.)
    body = re.sub(r'\{[^{}]*\}', ' ', body)
    
    # Remove HTML tags but keep text content
    clean_body = re.sub(r'<[^>]+>', ' ', body)
    
    # Decode HTML entities
    clean_body = unescape(clean_body)
    
    # Remove URL tracking parameters from all URLs
    clean_body = re.sub(r'https?://[^\s]+(?=\s|$)', lambda match: clean_url_simple(match.group()), clean_body)
    
    # Normalize whitespace
    clean_body = re.sub(r'\s+', ' ', clean_body)
    
    # Clean up special characters and multiple spaces
    clean_body = re.sub(r'[ \t\r\n\f\v]+', ' ', clean_body)
    clean_body = clean_body.strip()
    
    return clean_body



def init_gmail_service(
    client_file,
    api_name="gmail",
    api_version="v1",
    scopes=["https://mail.google.com/"],
    token_dir="token files",
):
    return create_service(client_file, api_name, api_version, scopes, token_dir=token_dir)


def _extract_body(payload):
    body = "<Text body not available>"
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "multipart/alternative":
                for subpart in part["parts"]:
                    # Try plain text first
                    if subpart["mimeType"] == "text/plain" and "data" in subpart["body"]:
                        body = base64.urlsafe_b64decode(subpart["body"]["data"]).decode("utf-8")
                        return body
                    # Fall back to HTML if no plain text
                    elif subpart["mimeType"] == "text/html" and "data" in subpart["body"]:
                        body = base64.urlsafe_b64decode(subpart["body"]["data"]).decode("utf-8")
            elif part["mimeType"] == "text/plain" and "data" in part["body"]:
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                break
            elif part["mimeType"] == "text/html" and "data" in part["body"]:
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
    elif "body" in payload and "data" in payload["body"]:
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
    return body


def get_email_messages(
    service, user_id="me", label_ids=None, folder_name="INBOX", max_results=5
):
    messages = []
    next_page_token = None

    if folder_name:
        label_results = service.users().labels().list(userId=user_id).execute()
        labels = label_results.get("labels", [])
        folder_label_id = next(
            (
                label["id"]
                for label in labels
                if label["name"].lower() == folder_name.lower()
            ),
            None,
        )
        if folder_label_id:
            if label_ids:
                label_ids.append(folder_label_id)
            else:
                label_ids = [folder_label_id]
        else:
            raise ValueError(f"Folder '{folder_name}' not found.")

    while True:
        result = (
            service.users()
            .messages()
            .list(
                userId=user_id,
                labelIds=label_ids,
                maxResults=(
                    min(500, max_results - len(messages)) if max_results else 500
                ),
                pageToken=next_page_token,
            )
            .execute()
        )

        messages.extend(result.get("messages", []))

        next_page_token = result.get("nextPageToken")

        if not next_page_token or (max_results and len(messages) >= max_results):
            break

    return messages[:max_results] if max_results else messages


def _split_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_email_message_details(service, msg_id):
    message = (
        service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    )
    payload = message["payload"]
    headers = payload.get("headers", [])

    subject = next(
        (header["value"] for header in headers if header["name"].lower() == "subject"),
        None,
    )

    if not subject:
        subject = message.get("subject", "No subject")
    sender = next(
        (header["value"] for header in headers if header["name"] == "From"), "No sender"
    )
    recipients_raw = next(
        (header["value"] for header in headers if header["name"] == "To"),
        "",
    )
    snippet = message.get("snippet", "No snippet")
    has_attachments = any(
        part.get("filename")
        for part in payload.get("parts", [])
        if part.get("filename")
    )
    date = next(
        (header["value"] for header in headers if header["name"] == "Date"), "No date"
    )
    star = message.get("labelIds", []).count("STARRED") > 0
    label = ", ".join(message.get("labelIds", []))
    body = _extract_body(payload)
    cleaned_body = clean_email_body(body)
    parsed_date = None
    try:
        parsed_date = parsedate_to_datetime(date) if date else None
    except (TypeError, ValueError):
        parsed_date = None

    return {
        "gmail_id": msg_id,
        "subject": subject,
        "sender": sender,
        "recipients": _split_addresses(recipients_raw),
        "body": cleaned_body,
        "snippet": snippet,
        "has_attachments": has_attachments,
        "date": date,
        "star": star,
        "labels": message.get("labelIds", []),
        "parsed_date": parsed_date,
    }
