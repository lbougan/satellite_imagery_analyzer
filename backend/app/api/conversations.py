from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.database import get_db
from app.models import Conversation, Message
from app.api.chat import cancel_running_agent

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str = "New Conversation"


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    metadata_json: dict | None = None
    created_at: str


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(body: ConversationCreate, db: AsyncSession = Depends(get_db)):
    conv = Conversation(title=body.title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationOut(id=conv.id, title=conv.title, created_at=conv.created_at.isoformat())


@router.get("", response_model=list[ConversationOut])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).order_by(Conversation.created_at.desc()))
    convs = result.scalars().all()
    return [
        ConversationOut(id=c.id, title=c.title, created_at=c.created_at.isoformat())
        for c in convs
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                metadata_json=m.metadata_json,
                created_at=m.created_at.isoformat(),
            )
            for m in conv.messages
        ],
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    cancel_running_agent(conversation_id)
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()
