from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

# ==========================================
# Content Pillar Schemas
# ==========================================

class ContentPillarBase(BaseModel):
    name: str
    description: Optional[str] = None

class ContentPillarCreate(ContentPillarBase):
    pass

class ContentPillar(ContentPillarBase):
    id: int
    brand_id: int

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Post Schemas
# ==========================================

class PostBase(BaseModel):
    format: str
    hook: str
    body: str
    cta: str
    hashtags: Optional[str] = None
    visual_idea: str
    status: str = "draft"
    scheduled_for: Optional[datetime] = None
    pillar_id: Optional[int] = None

class PostCreate(PostBase):
    brand_id: int

class Post(PostBase):
    id: int
    brand_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Brand Schemas
# ==========================================

class BrandBase(BaseModel):
    name: str
    niche: str
    target_audience: str
    brand_voice: str

class BrandCreate(BrandBase):
    pass

class Brand(BrandBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BrandDetail(Brand):
    pillars: List[ContentPillar] = []

    model_config = ConfigDict(from_attributes=True)
