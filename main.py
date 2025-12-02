from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from argon2 import PasswordHasher

ph = PasswordHasher()
# from datetime import datetime
# --- MongoDB connection ---
# user: bensindberg_db_user password: CcdjRkMQk42NBm7d
uri = "mongodb+srv://bensindberg_db_user:CcdjRkMQk42NBm7d@cluster0.tpjpecw.mongodb.net/"
client = MongoClient(uri)
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
# --- Minimal Pydantic model ---
class Account(BaseModel):
    username: str
    email: str
    password: str
    quack_bucks: int
    favorite_duck: str
    favorite_duck_url: str
    
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

        # --- Hash password ---
        account.password = ph.hash(account.password)

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
def update_account(username: str, account: Account):
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


@app.delete("/accounts/{username}", status_code=status.HTTP_200_OK)
def delete_account(username: str):
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