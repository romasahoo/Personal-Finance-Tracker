import os
import csv
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, func, case, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

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


# --- SQLAlchemy Models ---

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    auth_provider = Column(String, default="local")
    provider_id = Column(String, nullable=True, index=True)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at,
        }


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    date = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, default="")

    user = relationship("User", back_populates="transactions")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date,
            "amount": self.amount,
            "category": self.category,
            "description": self.description or "",
        }


# --- Initialization ---
def init_db():
    """Create tables and migrate CSV data if needed."""
    Base.metadata.create_all(bind=engine)

    # Add user_id column if it doesn't exist (for existing databases)
    try:
        with engine.begin() as conn:
            # This will fail gracefully if the column already exists
            conn.execute(text("ALTER TABLE transactions ADD COLUMN user_id INTEGER REFERENCES users(id)"))
    except Exception as e:
        print(f"Schema migration note: {e}")

    # Migrate CSV data on first run (assign to a default user if one exists)
    session = SessionLocal()
    try:
        # Ensure a default user exists for orphaned or legacy transactions
        default_user = session.query(User).filter(User.username == "default_admin").first()
        if not default_user:
            default_user = User(
                username="default_admin",
                email="admin@example.com",
                hashed_password="legacy",
                auth_provider="local"
            )
            session.add(default_user)
            session.commit()
            session.refresh(default_user)

        # Assign any existing SQLite transactions without a user to default_user
        orphaned = session.query(Transaction).filter(Transaction.user_id == None).all()
        if orphaned:
            for tx in orphaned:
                tx.user_id = default_user.id
            session.commit()

        count = session.query(Transaction).count()
        if count == 0 and os.path.exists(CSV_FILE):
            migrate_csv(session, default_user.id)
    finally:
        session.close()


def migrate_csv(session, default_user_id):
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
                        user_id=default_user_id,
                    )
                    session.add(tx)
                    migrated += 1
            session.commit()
            print(f"Migrated {migrated} transactions from CSV to database.")
    except Exception as e:
        session.rollback()
        print(f"CSV migration error: {e}")


# --- User CRUD ---

def get_user_by_username(session, username: str):
    return session.query(User).filter(User.username == username).first()


def get_user_by_email(session, email: str):
    return session.query(User).filter(User.email == email).first()


def get_user_by_id(session, user_id: int):
    return session.query(User).filter(User.id == user_id).first()


def create_user(session, username: str, email: str, hashed_password: str = None, auth_provider: str = "local", provider_id: str = None) -> User:
    user = User(username=username, email=email, hashed_password=hashed_password, auth_provider=auth_provider, provider_id=provider_id)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def get_user_by_provider(session, auth_provider: str, provider_id: str):
    return session.query(User).filter(User.auth_provider == auth_provider, User.provider_id == provider_id).first()


# --- Transaction CRUD (user-scoped) ---

def add_transaction(user_id: int, date: str, amount: float, category: str, description: str) -> int:
    """Add a new transaction and return its ID."""
    session = SessionLocal()
    try:
        tx = Transaction(
            user_id=user_id,
            date=date,
            amount=amount,
            category=category,
            description=description,
        )
        session.add(tx)
        session.commit()
        session.refresh(tx)
        return tx.id
    finally:
        session.close()


def get_transactions(
    user_id: int,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
) -> list:
    """Get transactions with optional filtering, scoped to a user."""
    session = SessionLocal()
    try:
        query = session.query(Transaction).filter(Transaction.user_id == user_id)

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


def get_transaction_by_id(transaction_id: int, user_id: int = None) -> dict:
    """Get a single transaction by ID, optionally scoped to a user."""
    session = SessionLocal()
    try:
        query = session.query(Transaction).filter(Transaction.id == transaction_id)
        if user_id is not None:
            query = query.filter(Transaction.user_id == user_id)
        tx = query.first()
        return tx.to_dict() if tx else None
    finally:
        session.close()


def update_transaction(
    transaction_id: int,
    date: str,
    amount: float,
    category: str,
    description: str,
    user_id: int = None,
) -> bool:
    """Update an existing transaction. Returns True if successful."""
    session = SessionLocal()
    try:
        query = session.query(Transaction).filter(Transaction.id == transaction_id)
        if user_id is not None:
            query = query.filter(Transaction.user_id == user_id)
        tx = query.first()
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


def delete_transaction(transaction_id: int, user_id: int = None) -> bool:
    """Delete a transaction by ID. Returns True if successful."""
    session = SessionLocal()
    try:
        query = session.query(Transaction).filter(Transaction.id == transaction_id)
        if user_id is not None:
            query = query.filter(Transaction.user_id == user_id)
        tx = query.first()
        if not tx:
            return False
        session.delete(tx)
        session.commit()
        return True
    finally:
        session.close()


def get_summary(user_id: int, start_date: str = None, end_date: str = None) -> dict:
    """Get income/expense/savings summary, scoped to a user."""
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
        ).filter(Transaction.user_id == user_id)

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


def get_chart_data(user_id: int, start_date: str = None, end_date: str = None) -> dict:
    """Get data formatted for Chart.js charts, scoped to a user."""
    session = SessionLocal()
    try:
        # Base filter
        query = session.query(Transaction).filter(Transaction.user_id == user_id)
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
