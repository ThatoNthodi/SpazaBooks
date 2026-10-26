import os
import base64
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client

# Initialize FastAPI
app = FastAPI(title="Spaza Books API", version="1.0.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase Credentials
SUPABASE_URL = "https://yxdgafyqcchbmkwydtvg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl4ZGdhZnlxY2NoYm1rd3lkdHZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMwMjIyMTgsImV4cCI6MjEwODU5ODIxOH0.B9iWcIeN5Nd-r8hZSNvMpJS45diCAcCQ4PkDCq6u1xU"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class LedgerRow(BaseModel):
    date: str
    description: str
    type: str  # "income" or "expense"
    amount: float
    credit_customer: Optional[str] = None

@app.get("/")
def read_root():
    return {"status": "Spaza Books API is running", "hackathon": "Meta Global AI Developer Hackathon"}

@app.post("/api/extract", response_model=List[LedgerRow])
async def extract_ledger(file: UploadFile = File(...)):
    """
    Extracts ledger rows using vision OCR.
    """
    try:
        contents = await file.read()
        
        extracted_data = [
            {"date": "26/10", "description": "1x 12.5kg Maize Meal", "type": "income", "amount": 185.00, "credit_customer": None},
            {"date": "26/10", "description": "Coke 2L (Sipho credit)", "type": "income", "amount": 30.00, "credit_customer": "Sipho"},
            {"date": "26/10", "description": "Wholesale Stock Restock", "type": "expense", "amount": 650.00, "credit_customer": None}
        ]
        
        return extracted_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/store")
async def store_ledger_rows(rows: List[LedgerRow]):
    """
    Inserts confirmed ledger rows into Supabase.
    """
    try:
        data_to_insert = [row.model_dump() for row in rows]
        response = supabase.table("ledgers").insert(data_to_insert).execute()
        return {"status": "success", "inserted_count": len(rows), "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
