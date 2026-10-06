import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from web3 import Web3

from app.crypto_utils import decrypt_data, encrypt_data, generate_hash, hash_password, verify_password
from app.database import get_all_records, get_by_blockchain_id, init_db, insert_record

# Load environment variables from .env file if available
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("HealthcarePreAuth")

ROOT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT_DIR / "public"
CONTRACT_INFO_PATH = Path(__file__).resolve().parent / "contract.json"

HARDHAT_RPC = os.getenv("PREAUTH_RPC_URL", "http://127.0.0.1:8545")
AES_KEY = os.getenv("PREAUTH_AES_KEY", "local-demo-aes-256-key-healthcare-preauth")
JWT_SECRET = os.getenv("PREAUTH_JWT_SECRET", "local-demo-jwt-secret-healthcare-preauth")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 12
STATUS_LABELS = {0: "Pending", 1: "Approved", 2: "Rejected"}

HOSPITAL_PASS = os.getenv("HOSPITAL_PASSWORD", "password123")
INSURER_PASS = os.getenv("INSURER_PASSWORD", "password123")

USERS = {
    "hospital": {"hash": hash_password(HOSPITAL_PASS), "role": "hospital"},
    "insurer": {"hash": hash_password(INSURER_PASS), "role": "insurer"},
}

POLICY_AUTO_APPROVE_PREFIXES = ("AUTH-",)
POLICY_AUTO_APPROVE_CODES = {"CPT-99214"}


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutdown.")


app = FastAPI(
    title="Automated Healthcare Prior-Authorization Network",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")

w3 = Web3(Web3.HTTPProvider(HARDHAT_RPC))


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class SubmitRequest(BaseModel):
    patientId: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9\-]+$")
    diagnosis: str = Field(..., min_length=1, max_length=500)
    procedureCode: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9\-]+$")


class EvaluateRequest(BaseModel):
    requestId: int = Field(..., ge=1)


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    username = payload.get("sub")
    role = payload.get("role")
    if username not in USERS or USERS[username]["role"] != role:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return {"username": username, "role": role}


def require_role(required_role: str):
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] != required_role:
            raise HTTPException(status_code=403, detail="Not authorized for this action.")
        return user

    return checker


def load_contract_info() -> dict:
    if not CONTRACT_INFO_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Contract metadata not found. Compile and deploy with Hardhat first.",
        )
    return json.loads(CONTRACT_INFO_PATH.read_text(encoding="utf-8"))


def get_contract():
    if not w3.is_connected():
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach the Hardhat node at {HARDHAT_RPC}.",
        )
    info = load_contract_info()
    return w3.eth.contract(address=Web3.to_checksum_address(info["address"]), abi=info["abi"]), info


def hospital_account() -> str:
    accounts = w3.eth.accounts
    if len(accounts) < 2:
        raise HTTPException(status_code=503, detail="Hardhat accounts are not available.")
    return accounts[1]


def insurer_account() -> str:
    accounts = w3.eth.accounts
    if not accounts:
        raise HTTPException(status_code=503, detail="Hardhat accounts are not available.")
    return accounts[0]


def parse_request_id(contract, receipt) -> int:
    decoded = contract.events.RequestCreated().process_receipt(receipt)
    if decoded:
        return int(decoded[0]["args"]["id"])
    return int(contract.functions.requestCount().call())


def on_chain_request(contract, request_id: int) -> dict:
    raw = contract.functions.getRequest(request_id).call()
    return {
        "id": int(raw[0]),
        "documentHash": raw[1],
        "hospital": raw[2],
        "status": int(raw[3]),
        "statusLabel": STATUS_LABELS.get(int(raw[3]), "Unknown"),
        "timestamp": int(raw[4]),
    }


def apply_policy(payload: dict) -> int:
    """Evaluates PA authorization rules.
    Returns: 1 for Approved, 2 for Rejected.
    """
    code = str(payload.get("procedureCode", "")).strip().upper()
    if any(code.startswith(prefix) for prefix in POLICY_AUTO_APPROVE_PREFIXES) or code in POLICY_AUTO_APPROVE_CODES:
        return 1
    return 2


@app.get("/")
def index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    connected = w3.is_connected()
    contract_ready = CONTRACT_INFO_PATH.exists()
    return {
        "ok": connected and contract_ready,
        "hardhatConnected": connected,
        "contractDeployed": contract_ready,
        "rpcUrl": HARDHAT_RPC,
    }


@app.get("/api/config")
def config() -> dict:
    info = load_contract_info()
    return {
        "address": info["address"],
        "abi": info["abi"],
        "chainId": info.get("chainId", 31337),
        "rpcUrl": info.get("rpcUrl", HARDHAT_RPC),
        "owner": info.get("owner"),
    }


@app.post("/api/login")
def login(body: LoginRequest) -> dict:
    username = body.username.strip().lower()
    user = USERS.get(username)
    if user is None or not verify_password(body.password, user["hash"]):
        logger.warning(f"Failed login attempt for user: {username}")
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": username,
            "role": user["role"],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=JWT_EXPIRE_HOURS)).timestamp()),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    logger.info(f"User logged in successfully: {username}")
    return {"token": token, "role": user["role"], "username": username}


@app.post("/api/request")
def submit_authorization(
    body: SubmitRequest,
    _user: dict = Depends(require_role("hospital")),
) -> dict:
    payload = {
        "patientId": body.patientId.strip(),
        "diagnosis": body.diagnosis.strip(),
        "procedureCode": body.procedureCode.strip(),
    }
    encrypted_hex, iv = encrypt_data(payload, AES_KEY)
    document_hash = generate_hash(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    contract, _ = get_contract()
    sender = hospital_account()
    tx_hash = contract.functions.submitRequest(document_hash).transact({"from": sender})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        logger.error(f"On-chain submitRequest failed for patient {payload['patientId']}")
        raise HTTPException(status_code=500, detail="On-chain submitRequest transaction failed.")

    request_id = parse_request_id(contract, receipt)
    insert_record(
        patient_id=payload["patientId"],
        encrypted_data=encrypted_hex,
        iv=iv,
        document_hash=document_hash,
        blockchain_request_id=request_id,
    )
    logger.info(f"Submitted PA request #{request_id} for patient {payload['patientId']}")
    return {
        "requestId": request_id,
        "documentHash": document_hash,
        "txHash": receipt.transactionHash.to_0x_hex(),
        "status": "Pending",
    }


@app.post("/api/evaluate")
def evaluate_authorization(
    body: EvaluateRequest,
    _user: dict = Depends(require_role("insurer")),
) -> dict:
    row = get_by_blockchain_id(body.requestId)
    if row is None:
        raise HTTPException(status_code=404, detail="No off-chain record found for that request id.")

    decrypted = decrypt_data(row["encrypted_data"], row["iv"], AES_KEY)
    new_status = apply_policy(decrypted)

    if new_status not in (1, 2):
        raise HTTPException(status_code=500, detail="Policy engine returned invalid status.")

    contract, _ = get_contract()
    on_chain = on_chain_request(contract, body.requestId)
    if on_chain["status"] != 0:
        return {
            "requestId": body.requestId,
            "status": on_chain["statusLabel"],
            "statusCode": on_chain["status"],
            "alreadyEvaluated": True,
            "details": decrypted,
        }

    sender = insurer_account()
    tx_hash = contract.functions.evaluateRequest(body.requestId, new_status).transact({"from": sender})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        logger.error(f"On-chain evaluateRequest failed for request #{body.requestId}")
        raise HTTPException(status_code=500, detail="On-chain evaluateRequest transaction failed.")

    updated = on_chain_request(contract, body.requestId)
    logger.info(f"Evaluated PA request #{body.requestId}: Status {updated['statusLabel']}")
    return {
        "requestId": body.requestId,
        "status": updated["statusLabel"],
        "statusCode": updated["status"],
        "txHash": receipt.transactionHash.to_0x_hex(),
        "policyMatched": new_status == 1,
        "details": decrypted,
    }


@app.get("/api/requests")
def list_requests(_user: dict = Depends(get_current_user)) -> list[dict]:
    contract, _ = get_contract()
    results = []
    for row in get_all_records():
        decrypted = decrypt_data(row["encrypted_data"], row["iv"], AES_KEY)
        chain = on_chain_request(contract, int(row["blockchain_request_id"]))
        results.append(
            {
                "id": row["id"],
                "requestId": int(row["blockchain_request_id"]),
                "patientId": decrypted.get("patientId", row["patient_id"]),
                "diagnosis": decrypted.get("diagnosis", ""),
                "procedureCode": decrypted.get("procedureCode", ""),
                "documentHash": row["document_hash"],
                "status": chain["statusLabel"],
                "statusCode": chain["status"],
                "hospital": chain["hospital"],
                "timestamp": chain["timestamp"],
                "details": decrypted,
            }
        )
    return results
