Here are the **modern and recommended approaches** (as of 2025–2026) to access **Outlook.com** / **Hotmail** / **Live.com** personal emails using Python, fetch messages with different filters (sender, subject, date, etc.), and eventually store them (including content and attachments) in a database.

### Recommended Solution in 2025+: Microsoft Graph API (via Python SDK)

Microsoft is pushing very strongly toward **Microsoft Graph** for all personal (@outlook.com, @hotmail.com, @live.com) and work accounts.
Basic authentication (username/password via IMAP) has been **deprecated for years** for security reasons.

#### Step-by-step modern approach (Microsoft Graph + Python)

1. **Register an application** in Azure Portal
   https://portal.azure.com → Microsoft Entra ID → App registrations → New registration

   - Supported account types → **Accounts in any organizational directory and personal Microsoft accounts** ("common")
   - Redirect URI → for desktop script you can use `http://localhost` (or leave blank for device code flow)

2. **Add API permissions** (delegated – most common for personal use)

   - Microsoft Graph → Delegated permissions
   - `Mail.Read` (minimum)
   - `offline_access` (recommended → refresh tokens)
   - `User.Read` (usually added automatically)

   → **Grant admin consent** if needed (personal accounts usually don't require it)

3. **Get your Client ID** (Application ID)

   You will also need:
   - Tenant = `common` (for personal Microsoft accounts)
   - Scopes = `["https://graph.microsoft.com/Mail.Read", "https://graph.microsoft.com/offline_access", "https://graph.microsoft.com/User.Read"]`

4. **Most convenient libraries in 2025**

   | Library                                 | Recommendation          | OAuth Flow support         | Ease of use | Attachments |
   |-----------------------------------------|--------------------------|-----------------------------|-------------|-------------|
   | `msgraph-sdk-python` (official)         | ★★★★★ Best choice       | DeviceCode + others         | Very good   | Excellent   |
   | `O365`                                  | ★★★★ Good alternative   | Many flows including device | Good        | Very good   |
   | `requests` + `msal` manually            | ★★★ More control         | All                         | Hard        | Manual      |

#### Quick example using **official Microsoft Graph Python SDK** (2025 style)

```python
# pip install msgraph-sdk-python azure-identity

import asyncio
from msgraph import GraphServiceClient
from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import MessagesRequestBuilder
from azure.identity import DeviceCodeCredential  # ← easiest for scripts / personal accounts

# -------------------------------
CLIENT_ID = "your-azure-app-client-id"
AUTHORITY = "https://login.microsoftonline.com/common"   # very important for personal accounts!

scopes = ["https://graph.microsoft.com/.default"]
# -------------------------------


async def get_graph_client():
    credential = DeviceCodeCredential(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        # tenant_id="common"   # optional
    )
    return GraphServiceClient(credential, scopes=scopes)


async def main():
    client = await get_graph_client()

    # Example 1: Last 25 emails in Inbox
    messages = await client.me.mail_folders.by_id("inbox").messages.get(
        request_configuration=MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                select=["subject", "from", "receivedDateTime", "hasAttachments"],
                orderby=["receivedDateTime desc"],
                top=25,
            )
        )
    )

    for msg in messages.value:
        print(f"{msg.received_date_time} | {msg.subject}")
        print(f"   From: {msg.from_.email_address.address}")

    # Example 2: Filter by sender + subject (OData query)
    query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        filter="from/emailAddress/address eq 'boss@company.com' and contains(subject, 'urgent')",
        select=["subject", "bodyPreview", "receivedDateTime"],
        orderby=["receivedDateTime desc"],
        top=50
    )

    filtered = await client.me.mail_folders.by_id("inbox").messages.get(
        query_parameters=query_params
    )

    # Example 3: Get single message + download attachments
    msg_id = "AAMkAG..."  # get from previous query
    message = await client.me.messages.by_message_id(msg_id).get(
        request_configuration=...  # add expand=["attachments"]
    )

    if message.has_attachments:
        attachments = await client.me.messages.by_message_id(msg_id).attachments.get()
        for att in attachments.value:
            if att.content_type.startswith("application/"):
                content = await client.me.messages.by_message_id(msg_id)\
                    .attachments.by_attachment_id(att.id).content.get()
                with open(att.name, "wb") as f:
                    f.write(await content.read())

asyncio.run(main())
```

#### Popular OData filters examples (use in `filter=` parameter)

```text
receivedDateTime ge 2025-12-01T00:00:00Z
receivedDateTime ge 2025-01-01T00:00:00Z and receivedDateTime le 2025-01-31T23:59:59Z
from/emailAddress/address eq 'newsletter@company.com'
contains(subject, 'invoice')
contains(bodyPreview, 'payment failed')
hasAttachments eq true
isRead eq false
```

### Alternative (still sometimes used): IMAP (not recommended anymore)

```python
# pip install imap-tools

from imap_tools import MailBox, AND

with MailBox('outlook.office365.com').login('your@hotmail.com', 'your-app-password', 'INBOX') as mb:
    for msg in mb.fetch(AND(from_='amazon.com', subject='order'), limit=50, reverse=True):
        print(msg.subject, msg.from_, msg.date_str)
        for att in msg.attachments:
            with open(att.filename, 'wb') as f:
                f.write(att.payload)
```

→ You need an **app password** (classic password doesn't work anymore)

### Summary Table – What to Choose in 2026?

```text
Goal / Situation                                 | Recommended Solution
-------------------------------------------------|--------------------------------------
Personal @outlook.com account, long-term script  | Microsoft Graph + msgraph-sdk-python ★
Need to filter by many criteria                  | Microsoft Graph (excellent OData filters)
Want to download many attachments                | Microsoft Graph or O365 library
Quick & dirty one-time task                      | imap-tools + app password (if still works)
Corporate / Office 365 account                   | Microsoft Graph (preferred) or exchangelib+Oauth
```

Good luck and happy emailing! 🚀
Most future-proof path = **Microsoft Graph API** — invest time in it once.
