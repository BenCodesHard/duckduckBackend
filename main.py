from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from datetime import datetime, timedelta
import bcrypt
import certifi
import os
# from datetime import datetime
# --- MongoDB connection ---
# user: bensindberg_db_user password: CcdjRkMQk42NBm7d
uri = os.getenv("MONGODB_URI", "mongodb+srv://bensindberg_db_user:CcdjRkMQk42NBm7d@cluster0.tpjpecw.mongodb.net/")
client = MongoClient(uri, tlsCAFile=certifi.where())
db = client["duckbase"] # Database name
collection = db["Account"] # Collection name (not robots.json, just robots)
# --- FastAPI app setup ---
app = FastAPI()
# Optional: enable CORS if you’ll connect from React/React Native
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # or specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======== JWT / AUTH CONFIG ========
SECRET_KEY = "CHANGE_ME_SUPER_SECRET"  # TODO: move to environment variable in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# OAuth2 token scheme (Authorization: Bearer <token>)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# ======== BCRYPT HELPERS ========
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

# ======== JWT HELPERS ========
def create_jwt_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
# --- Minimal Pydantic model ---
class Account(BaseModel):
    username: str
    email: str
    password: str
    quack_bucks: int = Field(default=0)
    quack_coins: float = Field(default=0.0)
    favorite_duck: str = Field(default="")
    favorite_duck_url: str = Field(default="")
    ducks: List[dict] | None = Field(default_factory=list)

# Auth request/response models
class UserCreate(BaseModel):
    email: str
    password: str
    username: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    token: str
    
# --- Root endpoint ---
@app.get("/hello")
def read_root():
    return {"message": "Hello from FastAPI + MongoDB Atlas jjjjjjjj!"}

# --- Get all accounts ---
@app.get("/accounts")
def get_accounts():
    accounts = list(collection.find()) # Retrieve all documents
    for r in accounts:
        r["_id"] = str(r["_id"]) # Convert ObjectId to string
    return accounts

# --- Get single account by username ---
@app.get("/accounts/{username}", status_code=status.HTTP_200_OK)
def get_account_by_username(username: str):
    try:
        key = username.strip()
        account = collection.find_one({"username": key})
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        account["_id"] = str(account["_id"])
        return account
    except HTTPException:
        raise
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")

# # --- GET all with Error verification ---
@app.get("/accountse")
def get_accountse():
    try:
    # Try to retrieve all documents from MongoDB
        accounts = list(collection.find())
    # Force a runtime error
    # x = 1 / 0
    # Convert ObjectId to string for each account
        for r in accounts:
            r["_id"] = str(r["_id"])
        return accounts
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    
def get_user_by_email(email: str):
    try:
        user = collection.find_one({"email": email})
        return user
    except Exception:
        return None

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = get_user_by_email(email)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return email
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/signup")
def signup(user: UserCreate):
    try:
        if get_user_by_email(user.email):
            raise HTTPException(status_code=400, detail="User already exists")
        # Prepare account document
        doc = {
            "username": user.username or user.email.split("@")[0],
            "email": user.email,
            "password": hash_password(user.password),
            "quack_bucks": 0,
            "favorite_duck": "",
            "favorite_duck_url": "",
        }
        collection.insert_one(doc)
        return {"msg": "signup ok"}
    except HTTPException:
        raise
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/login", response_model=Token)
def login(user: UserLogin):
    db_user = get_user_by_email(user.email)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(user.password, db_user.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt_token({"sub": db_user["email"]})
    return {"token": token}

@app.get("/me")
def me(current_user: str = Depends(get_current_user)):
    return {"email": current_user}
    
@app.post("/accounts", status_code=status.HTTP_201_CREATED)
def add_account(account: Account):
    try:
        # --- Check if account already exists ---
        existing = collection.find_one({"username": account.username})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Account already exists"
            )

        # --- Hash password (bcrypt) ---
        account.password = hash_password(account.password)

        # --- Insert into database ---
        collection.insert_one(account.dict())
        return {"message": "Account added successfully"}

    # --- Database connection or query failure ---
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")

    # --- Any unexpected Python error ---
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    
# @app.post("/robots", status_code=status.HTTP_201_CREATED)
# def add_robot(robot: Robot):
#     collection.insert_one(robot.dict())
#     try:
#     # --- Check if robot already exists ---
#         existing = collection.find_one({"name": robot.name})
#         if existing:
#             raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="Robot already exists"
#             )
#     # --- Insert into database ---
#         collection.insert_one(robot.dict())
#         return {"message": "Robot added successfully"}
#     # --- Database connection or query failure ---
#     except HTTPException:
#         raise
#     except PyMongoError as e:
#         print("Database error:", e)
#         raise HTTPException(status_code=503, detail="Database not reachable")
#     # --- Any unexpected Python error ---
#     except Exception as e:
#         print("Unexpected error:", e)
#         raise HTTPException(status_code=500, detail="Internal server error")


# @app.post("/robotse", status_code=status.HTTP_201_CREATED)
# def add_robot(robot: Robot):
#     try:
#         # --- Check if robot already exists ---
#         existing = collection.find_one({"name": robot.name})
#         if existing:
#             raise HTTPException(
#                 status_code=status.HTTP_409_CONFLICT,
#                 detail="Robot already exists"
#             )
#         # --- Insert into database ---
#         collection.insert_one(robot.dict())
#         return {"message": "Robot added successfully"}
#     # --- Database connection or query failure ---
#     except PyMongoError as e:
#         print("Database error:", e)
#         raise HTTPException(status_code=503, detail="Database not reachable")
#     # --- Any unexpected Python error ---
#     except Exception as e:
#         print("Unexpected error:", e)
#         raise HTTPException(status_code=500, detail="Internal server error")

# --- PUT update robot (name cannot change) ---
@app.put("/accounts/{username}", status_code=status.HTTP_200_OK)
def update_account(username: str, account: Account, current_user: str = Depends(get_current_user)):
    try:
        # The next is only for DEBUGGing
        import sys
        # Force flush output
        print(f"\n=== PUT REQUEST RECEIVED ===", file=sys.stderr)
        print(f"Path parameter 'username': '{username}'", file=sys.stderr)
        print(f"Username length: {len(username)}", file=sys.stderr)
        print(f"Username repr: {repr(username)}", file=sys.stderr)
        sys.stderr.flush()
        
        # Trim whitespace and try to find the account
        username = username.strip()
        existing = collection.find_one({"username": username})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        # Only update price, description, imageUrl
        updates = {
            "quack_bucks": account.quack_bucks,
            "quack_coins": account.quack_coins,
            "favorite_duck": account.favorite_duck,
            "favorite_duck_url": account.favorite_duck_url
        }
        collection.update_one({"username": username}, {"$set": updates})
        return {"message": "Account updated successfully"}
    except HTTPException:
        raise
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Duck model and PUT to add ducks ---
class Duck(BaseModel):
    name: str
    rarity: str
    imageURL: str

@app.put("/accounts/{username}/ducks", status_code=status.HTTP_200_OK)
def add_ducks(username: str, ducks: List[Duck], current_user: str = Depends(get_current_user)):
    try:
        username = username.strip()
        existing = collection.find_one({"username": username})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        docs = [d.dict() for d in ducks]
        collection.update_one(
            {"username": username},
            {"$push": {"ducks": {"$each": docs}}}
        )
        return {"message": "Ducks added successfully", "count": len(docs)}
    except HTTPException:
        raise
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/accounts/{username}", status_code=status.HTTP_200_OK)
def delete_account(username: str, current_user: str = Depends(get_current_user)):
    try:
        # Trim whitespace and try to find the account
        username = username.strip()
        existing = collection.find_one({"username": username})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        result = collection.delete_one({"username": username})
        if result.deleted_count == 1:
            return {"message": "Account deleted successfully"}
        else:
            # This should not normally happen if `existing` was truthy
            raise HTTPException(status_code=500, detail="Failed to delete account")
    except HTTPException:
        raise
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")