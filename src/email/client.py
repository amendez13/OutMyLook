"""Microsoft Graph email client wrapper."""

from __future__ import annotations

import json
import logging
from importlib import import_module
from typing import Any, Optional, cast

from kiota_abstractions.method import Method
from kiota_abstractions.request_information import RequestInformation
from msgraph import GraphServiceClient

from src.database.repository import EmailRepository
from src.email.filters import EmailFilter
from src.email.models import Email, MailFolder

logger = logging.getLogger(__name__)


class EmailClient:
    """Wrapper around GraphServiceClient for email operations."""

    def __init__(self, graph_client: GraphServiceClient, email_repository: Optional[EmailRepository] = None):
        self._graph_client = graph_client
        self._email_repository = email_repository

    async def list_emails(
        self,
        folder: Optional[str] = "inbox",
        limit: int = 25,
        skip: int = 0,
        email_filter: Optional[EmailFilter] = None,
    ) -> list[Email]:
        """Fetch emails from a folder or the whole mailbox with pagination."""
        folder_id = await self._resolve_folder_id(folder) if folder is not None else None
        messages_request = self._get_messages_request(folder_id)
        filter_query = email_filter.build() if email_filter else None
        request_configuration = self._build_messages_request_config(
            limit=limit,
            skip=skip,
            filter_query=filter_query,
            include_orderby=folder_id is not None,
        )

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
        if self._email_repository and emails:
            await self._email_repository.save_many(emails)
        return emails

    async def ensure_folder(self, display_name: str) -> MailFolder:
        """Return an existing top-level folder or create it when missing."""
        normalized = display_name.strip()
        if not normalized:
            raise ValueError("Folder name cannot be empty.")

        folders = await self.list_folders()
        for folder in folders:
            if folder.display_name.strip().lower() == normalized.lower():
                return folder

        created = await self._create_folder(normalized)
        if created.display_name.strip().lower() == normalized.lower():
            return created

        raise ValueError(f"Folder '{normalized}' was created but returned unexpected metadata.")

    async def get_folder(self, folder_id: str) -> Optional[MailFolder]:
        """Return a folder by Graph ID when it exists."""
        normalized = folder_id.strip()
        if not normalized:
            raise ValueError("Folder ID cannot be empty.")

        mail_folders = self._graph_client.me.mail_folders
        if hasattr(mail_folders, "by_id"):
            folder_request = mail_folders.by_id(normalized)
        else:
            folder_request = mail_folders.by_mail_folder_id(normalized)

        try:
            folder = await folder_request.get()
        except Exception:
            return None
        if folder is None:
            return None
        return MailFolder.from_graph_folder(folder)

    async def move_email(self, message_id: str, destination_folder: str) -> None:
        """Move a message into the destination folder."""
        destination_id = await self._resolve_folder_id(destination_folder)
        await self._post_json(
            "{+baseurl}/me/messages/{message%2Did}/move",
            {"message%2Did": message_id},
            {"destinationId": destination_id},
        )

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

    def _get_messages_request(self, folder_id: Optional[str]) -> Any:
        if folder_id is None:
            return self._graph_client.me.messages
        return self._get_folder_messages_request(folder_id)

    def _get_folder_messages_request(self, folder_id: str) -> Any:
        mail_folders = self._graph_client.me.mail_folders
        if hasattr(mail_folders, "by_id"):
            folder_request = mail_folders.by_id(folder_id)
        else:
            folder_request = mail_folders.by_mail_folder_id(folder_id)
        return folder_request.messages

    async def _create_folder(self, display_name: str) -> MailFolder:
        response = await self._post_json(
            "{+baseurl}/me/mailFolders",
            {},
            {"displayName": display_name},
        )
        if not response:
            raise ValueError(f"Folder '{display_name}' was created but Microsoft Graph returned no payload.")
        return MailFolder.from_graph_folder(response)

    async def _post_json(
        self,
        url_template: str,
        path_parameters: dict[str, str],
        payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        request_adapter = getattr(self._graph_client, "request_adapter", None)
        if request_adapter is None:
            raise ValueError("Graph client does not expose a request adapter.")

        request_info = RequestInformation(
            Method.POST,
            url_template,
            path_parameters,
        )
        request_info.headers.try_add("Accept", "application/json")
        request_info.set_stream_content(
            json.dumps(payload).encode("utf-8"),
            "application/json",
        )
        response = await request_adapter.send_primitive_async(request_info, "bytes", None)
        if response is None:
            return None
        if isinstance(response, bytearray):
            response = bytes(response)
        if isinstance(response, bytes):
            text = response.decode("utf-8").strip()
            if not text:
                return None
            return cast(dict[str, Any], json.loads(text))
        raise TypeError("Unsupported response payload type")

    def _build_messages_request_config(
        self,
        limit: int,
        skip: int,
        filter_query: Optional[str] = None,
        include_orderby: bool = True,
    ) -> Optional[Any]:
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
            orderby=["receivedDateTime desc"] if include_orderby else None,
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
            top=200,
            select=[
                "id",
                "displayName",
                "parentFolderId",
                "childFolderCount",
                "totalItemCount",
                "unreadItemCount",
            ],
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
