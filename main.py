import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Paper

app = FastAPI(title="Exam Paper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Exam Papers API running"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Utility to convert Mongo _id to string
class PaperOut(Paper):
    id: str


@app.post("/api/papers", response_model=dict)
async def create_paper(paper: Paper):
    """Create a new paper document"""
    try:
        paper_id = create_document("paper", paper)
        return {"id": paper_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers", response_model=List[PaperOut])
async def list_papers(
    subject: Optional[str] = None,
    board: Optional[str] = None,
    level: Optional[str] = None,
    year: Optional[int] = None,
    q: Optional[str] = Query(None, description="Search in title/description/tags"),
    limit: int = Query(50, ge=1, le=200),
):
    """List papers with optional filters and basic search"""
    try:
        filters = {}
        if subject:
            filters["subject"] = {"$regex": f"^{subject}$", "$options": "i"}
        if board:
            filters["board"] = {"$regex": f"^{board}$", "$options": "i"}
        if level:
            filters["level"] = {"$regex": f"^{level}$", "$options": "i"}
        if year:
            filters["year"] = year
        if q:
            filters["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
                {"tags": {"$elemMatch": {"$regex": q, "$options": "i"}}},
            ]

        docs = get_documents("paper", filters or {}, limit)
        result: List[PaperOut] = []
        for d in docs:
            d["id"] = str(d.get("_id"))
            d.pop("_id", None)
            result.append(PaperOut(**d))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/filters", response_model=dict)
async def get_filter_values():
    """Return distinct values for facets like subject, board, level, years"""
    try:
        subjects = sorted(db["paper"].distinct("subject")) if db else []
        boards = sorted(db["paper"].distinct("board")) if db else []
        levels = sorted(db["paper"].distinct("level")) if db else []
        years = sorted(db["paper"].distinct("year")) if db else []
        return {"subjects": subjects, "boards": boards, "levels": levels, "years": years}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
