import os
import csv
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, func, case
from sqlalchemy.orm import declarative_base, sessionmaker

# Load .env file for local development
load_dotenv()

# --- Database Configuration (Dual-mode) ---
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Production: Supabase PostgreSQL
    # Fix Supabase URIs that start with "postgres://" (SQLAlchemy requires "postgresql://")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    print("Using PostgreSQL database")
else:
    # Local development: SQLite fallback
    engine = create_engine("sqlite:///finance_tracker.db", connect_args={"check_same_thread": False})
    print("Using local SQLite database")

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# --- Constants ---
CSV_FILE = "finance_data.csv"
DATE_FORMAT = "%d-%m-%Y"


# --- SQLAlchemy Model ---
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, default="")

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "amount": self.amount,
            "category": self.category,
            "description": self.description or "",
        }


# --- Initialization ---
def init_db():
    """Create tables and migrate CSV data if needed."""
    Base.metadata.create_all(bind=engine)

    # Migrate CSV data on first run
    session = SessionLocal()
    try:
        count = session.query(Transaction).count()
        if count == 0 and os.path.exists(CSV_FILE):
            migrate_csv(session)
    finally:
        session.close()


def migrate_csv(session):
    """Import existing CSV data into the database."""
    try:
        with open(CSV_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            migrated = 0
            for row in reader:
                if row.get("date") and row.get("amount"):
                    tx = Transaction(
                        date=row["date"].strip(),
                        amount=float(row["amount"]),
                        category=row["category"].strip(),
                        description=row.get("description", "").strip(),
                    )
                    session.add(tx)
                    migrated += 1
            session.commit()
            print(f"Migrated {migrated} transactions from CSV to database.")
    except Exception as e:
        session.rollback()
        print(f"CSV migration error: {e}")


# --- CRUD Operations ---
def add_transaction(date: str, amount: float, category: str, description: str) -> int:
    """Add a new transaction and return its ID."""
    session = SessionLocal()
    try:
        tx = Transaction(date=date, amount=amount, category=category, description=description)
        session.add(tx)
        session.commit()
        session.refresh(tx)
        return tx.id
    finally:
        session.close()


def get_transactions(start_date: str = None, end_date: str = None, category: str = None) -> list:
    """Get transactions with optional filtering."""
    session = SessionLocal()
    try:
        query = session.query(Transaction)

        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        if category and category.lower() != "all":
            query = query.filter(Transaction.category == category)

        query = query.order_by(Transaction.date.desc())
        rows = query.all()
        return [row.to_dict() for row in rows]
    finally:
        session.close()


def get_transaction_by_id(transaction_id: int) -> dict:
    """Get a single transaction by ID."""
    session = SessionLocal()
    try:
        tx = session.query(Transaction).filter(Transaction.id == transaction_id).first()
        return tx.to_dict() if tx else None
    finally:
        session.close()


def update_transaction(
    transaction_id: int, date: str, amount: float, category: str, description: str
) -> bool:
    """Update an existing transaction. Returns True if successful."""
    session = SessionLocal()
    try:
        tx = session.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not tx:
            return False
        tx.date = date
        tx.amount = amount
        tx.category = category
        tx.description = description
        session.commit()
        return True
    finally:
        session.close()


def delete_transaction(transaction_id: int) -> bool:
    """Delete a transaction by ID. Returns True if successful."""
    session = SessionLocal()
    try:
        tx = session.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not tx:
            return False
        session.delete(tx)
        session.commit()
        return True
    finally:
        session.close()


def get_summary(start_date: str = None, end_date: str = None) -> dict:
    """Get income/expense/savings summary."""
    session = SessionLocal()
    try:
        query = session.query(
            func.coalesce(
                func.sum(case((Transaction.category == "Income", Transaction.amount))), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(case((Transaction.category == "Expense", Transaction.amount))), 0
            ).label("total_expense"),
            func.count(Transaction.id).label("transaction_count"),
        )

        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)

        result = query.one()
        total_income = float(result.total_income)
        total_expense = float(result.total_expense)

        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "net_savings": total_income - total_expense,
            "transaction_count": result.transaction_count,
        }
    finally:
        session.close()


def get_chart_data(start_date: str = None, end_date: str = None) -> dict:
    """Get data formatted for Chart.js charts."""
    session = SessionLocal()
    try:
        # Base filter
        query = session.query(Transaction)
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)

        transactions = query.order_by(Transaction.date).all()

        # Build line chart data
        dates = sorted(set(tx.date for tx in transactions))
        income_by_date = {}
        expense_by_date = {}

        for tx in transactions:
            if tx.category == "Income":
                income_by_date[tx.date] = income_by_date.get(tx.date, 0) + tx.amount
            else:
                expense_by_date[tx.date] = expense_by_date.get(tx.date, 0) + tx.amount

        income_data = [income_by_date.get(d, 0) for d in dates]
        expense_data = [expense_by_date.get(d, 0) for d in dates]

        # Build doughnut chart data (expense breakdown by description)
        expense_totals = {}
        for tx in transactions:
            if tx.category == "Expense":
                label = tx.description or "Uncategorized"
                expense_totals[label] = expense_totals.get(label, 0) + tx.amount

        # Sort by total descending
        sorted_expenses = sorted(expense_totals.items(), key=lambda x: x[1], reverse=True)
        expense_labels = [item[0] for item in sorted_expenses]
        expense_amounts = [item[1] for item in sorted_expenses]

        return {
            "line_chart": {
                "labels": dates,
                "income": income_data,
                "expense": expense_data,
            },
            "doughnut_chart": {
                "labels": expense_labels,
                "data": expense_amounts,
            },
        }
    finally:
        session.close()
