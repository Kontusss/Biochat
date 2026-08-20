from biochat.schemas.chat import ChatMessage, MessageRole, SessionInfo
from biochat.services.session_service import SessionService


class DictSessionStore:
    def __init__(self):
        self.messages = {}
        self.info = {}

    def list_sessions(self):
        return sorted(self.info.values(), key=lambda item: item.updated_at, reverse=True)

    def get_session(self, session_id):
        return list(self.messages.get(session_id, []))

    def save_session(self, session_id, messages):
        self.messages[session_id] = list(messages)

    def get_session_info(self, session_id):
        return self.info.get(session_id)

    def save_session_info(self, info):
        self.info[info.session_id] = info

    def delete_session(self, session_id):
        self.messages.pop(session_id, None)
        self.info.pop(session_id, None)


class MetadataReplacingSessionStore(DictSessionStore):
    """Store whose message save replaces metadata with incomplete values."""

    def save_session(self, session_id, messages):
        super().save_session(session_id, messages)
        self.info[session_id] = SessionInfo(
            session_id=session_id,
            title="replaced by store",
            message_count=len(messages),
            created_at="",
            updated_at="",
        )


def test_custom_store_does_not_require_private_meta():
    """Changing a custom store's private layout must not break session creation."""
    service = SessionService(DictSessionStore())

    session_id = service.create_session("Wanted title")

    info = service.list_sessions()[0]
    assert info.session_id == session_id
    assert info.title == "Wanted title"
    assert info.created_at


def test_message_save_preserves_created_at_and_updates_title():
    """Replacing message history must retain its original creation timestamp."""
    service = SessionService()
    session_id = service.create_session("Initial")
    created_at = service.list_sessions()[0].created_at
    assert created_at

    service.add_message(session_id, ChatMessage(role=MessageRole.USER, content="First question"))

    info = service.list_sessions()[0]
    assert info.title == "First question"
    assert info.created_at == created_at


def test_get_session_returns_a_copy():
    """Mutating a returned history must not mutate the stored session."""
    service = SessionService()
    session_id = service.create_session()

    leaked = service.get_session(session_id)
    leaked.append(ChatMessage(role=MessageRole.USER, content="unsaved"))

    assert service.get_session(session_id) == []


def test_message_save_preserves_metadata_when_store_replaces_it():
    """A store's message-save side effect must not erase creation metadata."""
    service = SessionService(MetadataReplacingSessionStore())
    session_id = service.create_session("Initial")
    created_at = service.list_sessions()[0].created_at

    service.add_message(session_id, ChatMessage(role=MessageRole.USER, content="Question"))

    assert service.list_sessions()[0].created_at == created_at


def test_clear_preserves_metadata_when_store_replaces_it():
    """Clearing must retain creation metadata despite store save side effects."""
    service = SessionService(MetadataReplacingSessionStore())
    session_id = service.create_session("Initial")
    created_at = service.list_sessions()[0].created_at

    service.clear_session(session_id)

    assert service.list_sessions()[0].created_at == created_at
