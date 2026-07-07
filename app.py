from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
import database

# Initialize database on startup
database.init_db()

app = FastAPI(title="Personal Finance Tracker", version="1.0.0")


# --- Pydantic Models ---

class TransactionCreate(BaseModel):
    date: str
    amount: float
    category: str
    description: str = ""

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be a positive number")
        return v

    @field_validator("category")
    @classmethod
    def category_must_be_valid(cls, v):
        if v not in ("Income", "Expense"):
            raise ValueError("Category must be 'Income' or 'Expense'")
        return v

    @field_validator("date")
    @classmethod
    def date_must_be_valid(cls, v):
        try:
            datetime.strptime(v, "%d-%m-%Y")
        except ValueError:
            raise ValueError("Date must be in DD-MM-YYYY format")
        return v


class TransactionUpdate(TransactionCreate):
    pass


class TransactionResponse(BaseModel):
    id: int
    date: str
    amount: float
    category: str
    description: str


# --- API Endpoints ---

@app.get("/api/transactions", response_model=list[TransactionResponse])
def list_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
):
    """List all transactions with optional filters."""
    return database.get_transactions(start_date, end_date, category)


@app.post("/api/transactions", response_model=TransactionResponse, status_code=201)
def create_transaction(transaction: TransactionCreate):
    """Add a new transaction."""
    new_id = database.add_transaction(
        transaction.date,
        transaction.amount,
        transaction.category,
        transaction.description,
    )
    return {
        "id": new_id,
        "date": transaction.date,
        "amount": transaction.amount,
        "category": transaction.category,
        "description": transaction.description,
    }


@app.put("/api/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(transaction_id: int, transaction: TransactionUpdate):
    """Update an existing transaction."""
    existing = database.get_transaction_by_id(transaction_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Transaction not found")

    database.update_transaction(
        transaction_id,
        transaction.date,
        transaction.amount,
        transaction.category,
        transaction.description,
    )
    return {
        "id": transaction_id,
        "date": transaction.date,
        "amount": transaction.amount,
        "category": transaction.category,
        "description": transaction.description,
    }


@app.delete("/api/transactions/{transaction_id}")
def delete_transaction(transaction_id: int):
    """Delete a transaction."""
    existing = database.get_transaction_by_id(transaction_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Transaction not found")

    database.delete_transaction(transaction_id)
    return {"message": "Transaction deleted successfully"}


@app.get("/api/summary")
def get_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get income/expense/savings summary."""
    return database.get_summary(start_date, end_date)


@app.get("/api/chart-data")
def get_chart_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get chart data for dashboard visualizations."""
    return database.get_chart_data(start_date, end_date)


# --- Serve Frontend ---

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_dashboard():
    return FileResponse("static/index.html")


@app.get("/transactions")
def serve_transactions():
    return FileResponse("static/transactions.html")


@app.get("/add")
def serve_add():
    return FileResponse("static/add.html")
