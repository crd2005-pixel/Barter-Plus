from sqlalchemy.orm import Session
from . import models, schemas
from typing import List, Optional

# ==========================================
# Brand CRUD
# ==========================================

def get_brand(db: Session, brand_id: int) -> Optional[models.Brand]:
    return db.query(models.Brand).filter(models.Brand.id == brand_id).first()

def get_brands(db: Session, skip: int = 0, limit: int = 100) -> List[models.Brand]:
    return db.query(models.Brand).offset(skip).limit(limit).all()

def create_brand(db: Session, brand: schemas.BrandCreate) -> models.Brand:
    db_brand = models.Brand(**brand.model_dump())
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    return db_brand

# ==========================================
# Content Pillar CRUD
# ==========================================

def create_pillar(db: Session, pillar: schemas.ContentPillarCreate, brand_id: int) -> models.ContentPillar:
    db_pillar = models.ContentPillar(**pillar.model_dump(), brand_id=brand_id)
    db.add(db_pillar)
    db.commit()
    db.refresh(db_pillar)
    return db_pillar

# ==========================================
# Post CRUD
# ==========================================

def create_post(db: Session, post: schemas.PostCreate) -> models.Post:
    db_post = models.Post(**post.model_dump())
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

def get_posts(db: Session, brand_id: Optional[int] = None, status: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[models.Post]:
    query = db.query(models.Post)
    if brand_id is not None:
        query = query.filter(models.Post.brand_id == brand_id)
    if status is not None:
        query = query.filter(models.Post.status == status)
    return query.offset(skip).limit(limit).all()
