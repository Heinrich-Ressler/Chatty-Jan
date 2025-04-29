from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class PostBase(BaseModel):
    title: str
    content: str

class PostCreate(PostBase):
    pass

class PostUpdate(PostBase):
    title: Optional[str] = None
    content: Optional[str] = None

class PostOut(PostBase):
    id: int
    author_id: int
    author_username: str
    created_at: datetime
    image_url: Optional[str] = None
    likes_count: int
    comments_count: int

    model_config = ConfigDict(from_attributes=True)

class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    pass

class CommentUpdate(CommentBase):
    pass

class CommentOut(CommentBase):
    id: int
    post_id: int
    author_id: int
    author_username: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LikeOut(BaseModel):
    post_id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)

class PostCreatedEvent(BaseModel):
    post_id: int
    user_id: int
    title: str

class PostDeletedEvent(BaseModel):
    post_id: int
    user_id: int

class CommentCreatedEvent(BaseModel):
    comment_id: int
    post_id: int
    user_id: int
    content: str

class CommentDeletedEvent(BaseModel):
    comment_id: int
    post_id: int
    user_id: int

class LikeAddedEvent(BaseModel):
    post_id: int
    user_id: int

class LikeRemovedEvent(BaseModel):
    post_id: int
    user_id: int