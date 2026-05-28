from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(slots=True)
class AnalysisSession:
    id: str
    user_id: int
    image_paths: list[Path] = field(default_factory=list)
    media_group_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionManager:
    def __init__(self, ttl_minutes: int, max_images: int) -> None:
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_images = max_images
        self._sessions: dict[int, AnalysisSession] = {}
        self._albums: dict[str, AnalysisSession] = {}

    def start(self, user_id: int) -> AnalysisSession:
        session = AnalysisSession(id=uuid4().hex, user_id=user_id)
        self._sessions[user_id] = session
        return session

    def get_or_create(self, user_id: int) -> AnalysisSession:
        self.cleanup()
        return self._sessions.get(user_id) or self.start(user_id)

    def get_album_or_create(self, user_id: int, media_group_id: str) -> AnalysisSession:
        self.cleanup()
        session = self._albums.get(media_group_id)
        if session:
            return session
        session = AnalysisSession(id=uuid4().hex, user_id=user_id, media_group_id=media_group_id)
        self._albums[media_group_id] = session
        return session

    def add_image(self, session: AnalysisSession, path: Path) -> None:
        if len(session.image_paths) >= self.max_images:
            raise ValueError(f"Session image limit reached: {self.max_images}")
        session.image_paths.append(path)
        session.updated_at = datetime.now(timezone.utc)

    def pop(self, user_id: int) -> AnalysisSession | None:
        return self._sessions.pop(user_id, None)

    def pop_album(self, media_group_id: str) -> AnalysisSession | None:
        return self._albums.pop(media_group_id, None)

    def pop_album_for_user(self, user_id: int) -> AnalysisSession | None:
        for media_group_id, session in list(self._albums.items()):
            if session.user_id == user_id:
                return self._albums.pop(media_group_id)
        return None

    def cancel(self, user_id: int) -> AnalysisSession | None:
        return self._sessions.pop(user_id, None)

    def cleanup(self) -> None:
        now = datetime.now(timezone.utc)
        expired_users = [uid for uid, item in self._sessions.items() if now - item.updated_at > self.ttl]
        for uid in expired_users:
            self._sessions.pop(uid, None)
        expired_albums = [key for key, item in self._albums.items() if now - item.updated_at > self.ttl]
        for key in expired_albums:
            self._albums.pop(key, None)
