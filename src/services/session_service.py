from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.models import Message, Session
from src.utils.llm import get_dialog_to_script_similarity
from src.config import Settings


class SessionService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.active_sessions: Dict[tuple[str, str], int] = {}

    async def get_or_create_session(self, bot_id: str, chat_id: str) -> int:
        cache_key = (bot_id, chat_id)
        if cache_key in self.active_sessions:
            return self.active_sessions[cache_key]

        async with self.session_factory() as db_session:
            result = await db_session.execute(
                select(Session)
                .where(Session.bot_id == bot_id)
                .where(Session.chat_id == chat_id)
                .where(Session.status.in_(["waiting", "active"]))
                .order_by(Session.updated_at.desc())
            )
            session = result.scalar_one_or_none()

            if session:
                session_id = session.session_id
            else:
                new_session = Session(
                    bot_id=bot_id,
                    chat_id=chat_id,
                    status="waiting",
                )
                db_session.add(new_session)
                await db_session.commit()
                await db_session.refresh(new_session)
                session_id = new_session.session_id

            self.active_sessions[cache_key] = session_id
            return session_id

    async def get_active_session_by_chat_id(
        self, bot_id: str, chat_id: str
    ) -> Optional[Session]:
        async with self.session_factory() as db_session:
            result = await db_session.execute(
                select(Session)
                .where(Session.bot_id == bot_id)
                .where(Session.chat_id == chat_id)
                .where(Session.status.in_(["waiting", "active"]))
                .order_by(Session.updated_at.desc())
            )
            return result.scalar_one_or_none()

    async def get_active_session_by_manager_id(
        self, bot_id: str, manager_id: str
    ) -> Optional[Session]:
        async with self.session_factory() as db_session:
            result = await db_session.execute(
                select(Session)
                .where(Session.bot_id == bot_id)
                .where(Session.manager_id == manager_id)
                .where(Session.status == "active")
                .order_by(Session.updated_at.desc())
            )
            return result.scalar_one_or_none()

    async def get_free_managers(
        self, bot_id: str, manager_ids: List[str]
    ) -> List[str]:
        """Find managers from the list who don't have active sessions in this bot."""
        if not manager_ids:
            return []
        async with self.session_factory() as db_session:
            result = await db_session.execute(
                select(Session.manager_id)
                .where(Session.bot_id == bot_id)
                .where(Session.status == "active")
                .where(Session.manager_id.in_(manager_ids))
            )
            busy_managers = {row[0] for row in result.all() if row[0]}
            return [m for m in manager_ids if m not in busy_managers]

    async def get_next_waiting_session(self, bot_id: str) -> Optional[Session]:
        """Get the oldest waiting session for a bot."""
        async with self.session_factory() as db_session:
            result = await db_session.execute(
                select(Session)
                .where(Session.bot_id == bot_id)
                .where(Session.status == "waiting")
                .order_by(Session.created_at.asc())
            )
            return result.scalar_one_or_none()

    async def accept_session(self, session_id: int, manager_id: str) -> bool:
        async with self.session_factory() as db_session:
            result = await db_session.execute(
                select(Session).where(Session.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            if session and session.status == "waiting":
                session.status = "active"
                session.manager_id = manager_id
                session.updated_at = datetime.now(timezone.utc)
                await db_session.commit()
                return True
            return False

    async def close_session(self, session_id: int) -> bool:
        async with self.session_factory() as db_session:
            result = await db_session.execute(
                select(Session)
                .options(selectinload(Session.messages))
                .where(Session.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            if session and session.status == "active":
                session.status = "closed"
                session.updated_at = datetime.now(timezone.utc)
                
                bot_id = session.bot_id
                chat_id = session.chat_id
                manager_id = session.manager_id
                
                await db_session.commit()

                cache_key = (bot_id, chat_id)
                if cache_key in self.active_sessions:
                    del self.active_sessions[cache_key]

                # We return True to indicate session was closed
                # But we might need to perform LLM analysis
                # We do it after commit and cache cleanup to be "instantly" responsive if called from bot
                
                settings = Settings.from_env()
                if settings.llm_deepseek_api_key and settings.manager_scripts:
                    # Load all scripts from files
                    scripts_content = []
                    from src.utils.logger import logger
                    import os
                    import asyncio
                    for script_path in settings.manager_scripts:
                        try:
                            if os.path.exists(script_path):
                                with open(script_path, 'r', encoding='utf-8') as f:
                                    content = f.read().strip()
                                    if content:
                                        scripts_content.append(f"### SCRIPT FROM {script_path} ###\n{content}")
                            else:
                                logger.error(f"Script file not found: {script_path}")
                        except Exception as e:
                            logger.error(f"Failed to read script file {script_path}: {e}")

                    if scripts_content:
                        combined_script = "\n\n".join(scripts_content)
                        dialog_str = str(session)
                        try:
                            # Use run_in_executor for file reading if it was many files, but here we just do the LLM call
                            rating = await get_dialog_to_script_similarity(
                                dialog_str, combined_script
                            )
                            if rating is not None:
                                # Re-open session to update rating
                                async with self.session_factory() as db_session_update:
                                    result = await db_session_update.execute(
                                        select(Session).where(Session.session_id == session_id)
                                    )
                                    session_to_update = result.scalar_one_or_none()
                                    if session_to_update:
                                        session_to_update.rating = rating
                                        await db_session_update.commit()
                        except Exception as e:
                            logger.error(f"Failed to get dialog similarity: {e}")

                return True
            return False

    async def add_message_to_session(
        self,
        session_id: int,
        text: str,
        message_type: str,
        sender: Optional[str] = None,
        telegram_message_id: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> int:
        async with self.session_factory() as db_session:
            message = Message(
                session_id=session_id,
                message_type=message_type,
                sender=sender,
                text=text,
                telegram_message_id=telegram_message_id,
                status=status,
                error_message=error_message,
            )
            db_session.add(message)

            result = await db_session.execute(
                select(Session).where(Session.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                session.updated_at = datetime.now(timezone.utc)

            await db_session.commit()
            await db_session.refresh(message)
            return message.message_id

    async def get_session_messages(self, session_id: int) -> Optional[Dict[str, Any]]:
        async with self.session_factory() as db_session:
            result = await db_session.execute(
                select(Session).where(Session.session_id == session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                return None

            result = await db_session.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.asc())
            )
            messages = result.scalars().all()

            return {
                "session_id": session.session_id,
                "bot_id": session.bot_id,
                "chat_id": session.chat_id,
                "context_id": session.context_id,
                "messages": [
                    {
                        "message_id": msg.message_id,
                        "type": msg.message_type,
                        "sender": msg.sender,
                        "text": msg.text,
                        "status": msg.status,
                        "created_at": msg.created_at.isoformat(),
                        "telegram_message_id": msg.telegram_message_id,
                    }
                    for msg in messages
                ],
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            }

    async def get_all_sessions(
        self, chat_id: Optional[str] = None, bot_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        async with self.session_factory() as db_session:
            query = (
                select(Session)
                .options(selectinload(Session.messages))
                .order_by(Session.updated_at.desc())
            )

            if bot_id:
                query = query.where(Session.bot_id == bot_id)
            if chat_id:
                query = query.where(Session.chat_id == chat_id)

            result = await db_session.execute(query)
            sessions = result.scalars().unique().all()

            return [
                {
                    "session_id": s.session_id,
                    "bot_id": s.bot_id,
                    "chat_id": s.chat_id,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "message_count": len(s.messages),
                }
                for s in sessions
            ]

    async def get_manager_messages(
        self, manager_id: str, bot_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all messages from all sessions assigned to a specific manager."""
        async with self.session_factory() as db_session:
            query = (
                select(Message)
                .join(Session, Message.session_id == Session.session_id)
                .where(Session.manager_id == manager_id)
                .order_by(Message.created_at.asc())
            )

            if bot_id:
                query = query.where(Session.bot_id == bot_id)

            result = await db_session.execute(query)
            messages = result.scalars().all()

            return [
                {
                    "message_id": msg.message_id,
                    "session_id": msg.session_id,
                    "type": msg.message_type,
                    "sender": msg.sender,
                    "text": msg.text,
                    "status": msg.status,
                    "created_at": msg.created_at.isoformat(),
                    "telegram_message_id": msg.telegram_message_id,
                }
                for msg in messages
            ]
