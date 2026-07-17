from fastapi import FastAPI, HTTPException, Depends, status, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime, timedelta
import database
import auth
from auth import get_current_user, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

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


# --- Authentication Models ---

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

    @field_validator('username')
    @classmethod
    def username_must_be_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v

    @field_validator('email')
    @classmethod
    def email_must_be_valid(cls, v):
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('Invalid email format')
        return v

    @field_validator('password')
    @classmethod
    def password_must_be_strong(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool = True


# --- Authentication Endpoints ---

@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: database.SessionLocal = Depends(auth.get_db_session)):
    """Register a new user."""
    db_user = database.get_user_by_username(db, user.username)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    db_user = database.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    hashed_password = auth.hash_password(user.password)
    db_user = database.create_user(
        session=db,
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    return db_user


@app.post("/login", response_model=Token)
def login_user(form_data: UserLogin, db: database.SessionLocal = Depends(auth.get_db_session)):
    """Login user and return access token."""
    user = database.get_user_by_username(db, form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/logout")
def logout_user(response: Response):
    """Logout user by clearing the token."""
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}


@app.get("/me", response_model=UserResponse)
def read_current_user(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return current_user


# --- API Endpoints ---

@app.get("/api/transactions", response_model=list[TransactionResponse])
def list_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List all transactions for the current user with optional filters."""
    return database.get_transactions(
        user_id=current_user["id"],
        start_date=start_date,
        end_date=end_date,
        category=category,
    )


@app.post("/api/transactions", response_model=TransactionResponse, status_code=201)
def create_transaction(
    transaction: TransactionCreate,
    current_user: dict = Depends(get_current_user),
):
    """Add a new transaction for the current user."""
    new_id = database.add_transaction(
        user_id=current_user["id"],
        date=transaction.date,
        amount=transaction.amount,
        category=transaction.category,
        description=transaction.description,
    )
    return {
        "id": new_id,
        "date": transaction.date,
        "amount": transaction.amount,
        "category": transaction.category,
        "description": transaction.description,
    }


@app.put("/api/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    transaction: TransactionUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing transaction for the current user."""
    existing = database.get_transaction_by_id(
        transaction_id=transaction_id, user_id=current_user["id"]
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Transaction not found")

    success = database.update_transaction(
        transaction_id=transaction_id,
        date=transaction.date,
        amount=transaction.amount,
        category=transaction.category,
        description=transaction.description,
        user_id=current_user["id"],
    )
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {
        "id": transaction_id,
        "date": transaction.date,
        "amount": transaction.amount,
        "category": transaction.category,
        "description": transaction.description,
    }


@app.delete("/api/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete a transaction for the current user."""
    existing = database.get_transaction_by_id(
        transaction_id=transaction_id, user_id=current_user["id"]
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Transaction not found")

    success = database.delete_transaction(
        transaction_id=transaction_id, user_id=current_user["id"]
    )
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {"message": "Transaction deleted successfully"}


@app.get("/api/summary")
def get_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get income/expense/savings summary for the current user."""
    return database.get_summary(
        user_id=current_user["id"],
        start_date=start_date,
        end_date=end_date,
    )


@app.get("/api/chart-data")
def get_chart_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get chart data for dashboard visualizations for the current user."""
    return database.get_chart_data(
        user_id=current_user["id"],
        start_date=start_date,
        end_date=end_date,
    )


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



import os
import httpx
from fastapi.responses import RedirectResponse

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# Ensure the Redirect URIs match the deployed domain or localhost
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

@app.get("/auth/github/login")
def github_login():
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub Client ID not configured")
    redirect_uri = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={GITHUB_REDIRECT_URI}&scope=user:email"
    return RedirectResponse(redirect_uri)

@app.get("/auth/github/callback")
async def github_callback(code: str):
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub credentials not configured")
    
    async with httpx.AsyncClient() as client:
        # Get access token
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            }
        )
        token_data = token_res.json()
        if "access_token" not in token_data:
            raise HTTPException(status_code=400, detail="Failed to get access token from GitHub")
            
        access_token = token_data["access_token"]
        
        # Get user info
        user_res = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_data = user_res.json()
        
        # Get user email
        email_res = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        emails = email_res.json()
        primary_email = next((e["email"] for e in emails if e["primary"]), None)
        if not primary_email and emails:
            primary_email = emails[0]["email"]
            
        if not primary_email:
            raise HTTPException(status_code=400, detail="No email available from GitHub")
            
        provider_id = str(user_data.get("id"))
        username = user_data.get("login")

    return _process_oauth_user("github", provider_id, username, primary_email)


@app.get("/auth/google/login")
def google_login():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google Client ID not configured")
    # Using Google's OAuth 2.0 endpoint for Web Server Apps
    redirect_uri = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        "response_type=code&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        "scope=openid%20email%20profile&"
        "access_type=offline"
    )
    return RedirectResponse(redirect_uri)

@app.get("/auth/google/callback")
async def google_callback(code: str):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google credentials not configured")
    
    async with httpx.AsyncClient() as client:
        # Get access token
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI,
            }
        )
        token_data = token_res.json()
        if "access_token" not in token_data:
            raise HTTPException(status_code=400, detail="Failed to get access token from Google")
            
        access_token = token_data["access_token"]
        
        # Get user info
        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_data = user_res.json()
        
        primary_email = user_data.get("email")
        if not primary_email:
            raise HTTPException(status_code=400, detail="No email available from Google")
            
        provider_id = str(user_data.get("id"))
        username = primary_email.split("@")[0] # Generate a username

    return _process_oauth_user("google", provider_id, username, primary_email)

def _process_oauth_user(provider: str, provider_id: str, username: str, email: str):
    session = database.SessionLocal()
    try:
        # Look up existing user
        user = database.get_user_by_provider(session, provider, provider_id)
        if not user:
            # Check if email is already used by local account
            existing = database.get_user_by_email(session, email)
            if existing:
                user = existing
                user.auth_provider = provider
                user.provider_id = provider_id
                session.commit()
            else:
                # Need a unique username
                base_username = username
                counter = 1
                while database.get_user_by_username(session, username):
                    username = f"{base_username}{counter}"
                    counter += 1
                    
                user = database.create_user(
                    session=session,
                    username=username,
                    email=email,
                    hashed_password=None,
                    auth_provider=provider,
                    provider_id=provider_id
                )
        
        # Generate JWT token
        # Notice that our token payload is usually {"sub": user.username} per login_user endpoint
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth.create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        
        # We redirect to /login#token=XYZ
        return RedirectResponse(f"/login#token={access_token}")
    finally:
        session.close()



@app.get("/login")
def serve_login():
    return FileResponse("static/login.html")

@app.get("/register")
def serve_register():
    return FileResponse("static/register.html")

