from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from . import crud, models, schemas
from .database import engine, get_db
from .services.ai_generator import generate_post_content

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="App 1: Estudio de Contenido")

# ==========================================
# Brand Endpoints
# ==========================================

@app.post("/brands/", response_model=schemas.Brand)
def create_brand(brand: schemas.BrandCreate, db: Session = Depends(get_db)):
    return crud.create_brand(db=db, brand=brand)

@app.get("/brands/", response_model=List[schemas.Brand])
def read_brands(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    brands = crud.get_brands(db, skip=skip, limit=limit)
    return brands

@app.get("/brands/{brand_id}", response_model=schemas.BrandDetail)
def read_brand(brand_id: int, db: Session = Depends(get_db)):
    db_brand = crud.get_brand(db, brand_id=brand_id)
    if db_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return db_brand

# ==========================================
# Content Pillar Endpoints
# ==========================================

@app.post("/brands/{brand_id}/pillars/", response_model=schemas.ContentPillar)
def create_pillar_for_brand(
    brand_id: int, pillar: schemas.ContentPillarCreate, db: Session = Depends(get_db)
):
    db_brand = crud.get_brand(db, brand_id=brand_id)
    if db_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return crud.create_pillar(db=db, pillar=pillar, brand_id=brand_id)

# ==========================================
# Post Endpoints
# ==========================================

@app.post("/brands/{brand_id}/generate-post", response_model=schemas.Post)
def generate_post_endpoint(
    brand_id: int, request: schemas.PostGenerateRequest, db: Session = Depends(get_db)
):
    db_brand = crud.get_brand(db, brand_id=brand_id)
    if db_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    pillar_name = None
    if request.pillar_id:
        db_pillar = db.query(models.ContentPillar).filter(
            models.ContentPillar.id == request.pillar_id,
            models.ContentPillar.brand_id == brand_id
        ).first()
        if db_pillar is None:
            raise HTTPException(status_code=404, detail="Pillar not found for this brand")
        pillar_name = db_pillar.name

    try:
        generated_content = generate_post_content(
            brand=db_brand,
            pillar_name=pillar_name,
            post_format=request.format,
            extra_topic=request.extra_topic
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    post_in = schemas.PostCreate(
        brand_id=brand_id,
        pillar_id=request.pillar_id,
        format=request.format,
        hook=generated_content.hook,
        body=generated_content.body,
        cta=generated_content.cta,
        hashtags=generated_content.hashtags,
        visual_idea=generated_content.visual_idea,
        status="generated"
    )

    return crud.create_post(db=db, post=post_in)


@app.post("/posts/", response_model=schemas.Post)
def create_post(post: schemas.PostCreate, db: Session = Depends(get_db)):
    db_brand = crud.get_brand(db, brand_id=post.brand_id)
    if db_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return crud.create_post(db=db, post=post)

@app.get("/posts/", response_model=List[schemas.Post])
def read_posts(
    brand_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    posts = crud.get_posts(db, brand_id=brand_id, status=status, skip=skip, limit=limit)
    return posts
