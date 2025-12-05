from fastapi import FastAPI, HTTPException, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

# ------------------------------
# JWT CONFIG
# ------------------------------
SECRET_KEY = "CHANGE_ME_SUPER_SECRET"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# ------------------------------
# ARGON2 PASSWORD HASHING
# ------------------------------
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

# ------------------------------
# USER DATABASE
# ------------------------------
users_db = {
    "tech": {
        "username": "tech",
        "password": pwd_context.hash("tech123"),  # argon2 has no limits
    },
    "husaynirfan": {
        "username": "husaynirfan",
        "password": pwd_context.hash("Husayn#2001"),  # argon2 has no limits
    }
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

app = FastAPI()

# ------------------------------
# CORS
# ------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Helper Functions
# ------------------------------
def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def authenticate_user(username, password):
    user = users_db.get(username)
    if not user:
        return False
    if not verify_password(password, user["password"]):
        return False
    return user

# ------------------------------
# Login
# ------------------------------
@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {"access_token": access_token, "token_type": "bearer"}

# ------------------------------
# Protected Endpoint
# ------------------------------
@app.get("/protected")
def protected(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"message": f"Hello {username}"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
