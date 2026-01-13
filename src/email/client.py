"""Microsoft Graph email client wrapper."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any, Optional, cast

from msgraph import GraphServiceClient

from src.email.filters import EmailFilter
from src.email.models import Email, MailFolder

logger = logging.getLogger(__name__)


class EmailClient:
    """Wrapper around GraphServiceClient for email operations."""

    def __init__(self, graph_client: GraphServiceClient):
        self._graph_client = graph_client

    async def list_emails(
        self,
        folder: str = "inbox",
        limit: int = 25,
        skip: int = 0,
        email_filter: Optional[EmailFilter] = None,
    ) -> list[Email]:
        """Fetch emails from a folder with pagination."""
        folder_id = await self._resolve_folder_id(folder)
        messages_request = self._get_folder_messages_request(folder_id)
        filter_query = email_filter.build() if email_filter else None
        request_configuration = self._build_messages_request_config(limit=limit, skip=skip, filter_query=filter_query)

        if request_configuration is not None:
            response = await messages_request.get(request_configuration=request_configuration)
        else:
            response = await messages_request.get()

        messages = self._extract_collection(response)
        emails: list[Email] = []
        for message in messages:
            try:
                emails.append(Email.from_graph_message(message, folder_id=folder_id))
            except ValueError as exc:
                logger.warning("Skipping message due to mapping error: %s", exc)
        return emails

    async def get_email(self, message_id: str) -> Email:
        """Fetch a single email by ID."""
        messages_builder = cast(Any, self._graph_client.me.messages)
        if hasattr(messages_builder, "by_message_id"):
            message_request = messages_builder.by_message_id(message_id)
        else:
            message_request = messages_builder.by_id(message_id)

        message = await message_request.get()
        return Email.from_graph_message(message)

    async def list_folders(self) -> list[MailFolder]:
        """List available mail folders."""
        request_configuration = self._build_folders_request_config()
        mail_folders_builder = self._graph_client.me.mail_folders

        if request_configuration is not None:
            response = await mail_folders_builder.get(request_configuration=request_configuration)
        else:
            response = await mail_folders_builder.get()

        folders = self._extract_collection(response)
        return [MailFolder.from_graph_folder(folder) for folder in folders]

    async def _resolve_folder_id(self, folder: str) -> str:
        normalized = folder.strip().lower().replace(" ", "")
        well_known = {
            "inbox": "inbox",
            "sent": "sentitems",
            "sentitems": "sentitems",
            "drafts": "drafts",
            "archive": "archive",
            "deleted": "deleteditems",
            "deleteditems": "deleteditems",
            "junk": "junkemail",
            "junkemail": "junkemail",
            "outbox": "outbox",
        }

        if normalized in well_known:
            return well_known[normalized]

        # Try to resolve by display name.
        folders = await self.list_folders()
        for mail_folder in folders:
            if mail_folder.display_name.strip().lower() == folder.strip().lower():
                return mail_folder.id

        return folder

    def _get_folder_messages_request(self, folder_id: str) -> Any:
        mail_folders = self._graph_client.me.mail_folders
        if hasattr(mail_folders, "by_id"):
            folder_request = mail_folders.by_id(folder_id)
        else:
            folder_request = mail_folders.by_mail_folder_id(folder_id)
        return folder_request.messages

    def _build_messages_request_config(self, limit: int, skip: int, filter_query: Optional[str] = None) -> Optional[Any]:
        builder = self._import_builder(
            [
                "msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder",
                "msgraph.generated.users.item.messages.messages_request_builder",
            ],
            "MessagesRequestBuilder",
        )
        if not builder:
            return None

        query_params = builder.MessagesRequestBuilderGetQueryParameters(
            top=limit,
            skip=skip,
            filter=filter_query or None,
            select=[
                "id",
                "subject",
                "sender",
                "from",
                "receivedDateTime",
                "bodyPreview",
                "body",
                "isRead",
                "hasAttachments",
                "parentFolderId",
            ],
            orderby=["receivedDateTime desc"],
        )
        return builder.MessagesRequestBuilderGetRequestConfiguration(query_parameters=query_params)

    def _build_folders_request_config(self) -> Optional[Any]:
        builder = self._import_builder(
            ["msgraph.generated.users.item.mail_folders.mail_folders_request_builder"],
            "MailFoldersRequestBuilder",
        )
        if not builder:
            return None

        query_params = builder.MailFoldersRequestBuilderGetQueryParameters(
            select=[
                "id",
                "displayName",
                "parentFolderId",
                "childFolderCount",
                "totalItemCount",
                "unreadItemCount",
            ]
        )
        return builder.MailFoldersRequestBuilderGetRequestConfiguration(query_parameters=query_params)

    @staticmethod
    def _import_builder(module_paths: list[str], class_name: str) -> Optional[Any]:
        for module_path in module_paths:
            try:
                module = import_module(module_path)
                return getattr(module, class_name)
            except (ModuleNotFoundError, AttributeError):
                continue
        return None

    @staticmethod
    def _extract_collection(response: Any) -> list[Any]:
        if response is None:
            return []
        if isinstance(response, list):
            return response
        value = getattr(response, "value", None)
        if value is None:
            return []
        return list(value)
