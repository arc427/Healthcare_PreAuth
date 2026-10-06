# Automated Healthcare Prior-Authorization Network

An automated prior-authorization (PA) platform connecting healthcare providers (hospitals) and payors (insurers) using **FastAPI**, **SQLite**, and **Ethereum Smart Contracts (Hardhat / Solidity)**.

Patient Health Information (PHI) is encrypted off-chain using **AES-256-CBC**, while cryptographic SHA-256 hashes and decision outcomes are stored on-chain for tamper-proof integrity and auditability.

---

## Features

- **Off-Chain Encrypted Storage**: PHI payload encrypted with AES-256-CBC and stored in SQLite.
- **On-Chain Audit Ledger**: Document hashes and decision events logged immutably on Ethereum smart contracts.
- **Role-Based Access Control**: JWT authentication for `hospital` and `insurer` roles.
- **Automated Policy Evaluation**: Policy rules engine auto-approves pre-authorized procedure codes (`AUTH-*`, `CPT-99214`).
- **Interactive UI**: Single-page dashboard built with Tailwind CSS, supporting hospital submissions and insurer real-time evaluations.
- **Complete Test Suites**: Full unit test coverage for smart contract (Hardhat/Chai) and backend REST API (Pytest/TestClient).

---

## Prerequisites

- **Node.js**: v18+ and `npm`
- **Python**: 3.10+
- **Hardhat**: included in `package.json`

---

## Quick Start

### 1. Installation

Clone the repository and install Node.js and Python dependencies:

```bash
# Install Node dependencies
npm install

# Setup Python environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install Python requirements
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Adjust secrets or RPC URL in `.env` if desired.

---

## Running the Application

### Step A: Start Local Hardhat Blockchain Node

In Terminal 1:
```bash
npx hardhat node
```

### Step B: Compile & Deploy Smart Contract

In Terminal 2:
```bash
# Compile Solidity contract
npm run compile

# Deploy to local network
npm run deploy
```

This compiles `contracts/PriorAuthorization.sol` and writes contract address + ABI to `app/contract.json` and `public/contract.json`.

### Step C: Run FastAPI Web Server

In Terminal 2:
```bash
# Activate virtual environment if not active
venv\Scripts\activate

# Start server on http://127.0.0.1:8000
uvicorn app.main:app --reload --port 8000
```

Open **`http://127.0.0.1:8000`** in your browser.

---

## Demo Accounts

| Role | Username | Password | Actions Allowed |
|---|---|---|---|
| **Hospital** | `hospital` | `password123` | Submit authorization requests |
| **Insurer** | `insurer` | `password123` | View live queue, auto-evaluate requests |

---

## Running Tests

### Smart Contract Unit Tests (Hardhat / Chai)
```bash
npx hardhat test
```

### Backend API & Crypto Tests (Pytest)
```bash
python -m pytest tests/
```

---

## API Reference

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/api/health` | `GET` | Public | System and blockchain status |
| `/api/config` | `GET` | Public | Deployed contract ABI and address |
| `/api/login` | `POST` | Public | Authenticate and obtain JWT token |
| `/api/request` | `POST` | Hospital | Submit new PA request |
| `/api/evaluate` | `POST` | Insurer | Evaluate pending PA request |
| `/api/requests` | `GET` | Auth | List authorization records |

---

## Project Structure

```
Healthcare_PreAuth/
├── app/
│   ├── main.py          # FastAPI application & endpoints
│   ├── crypto_utils.py  # AES-256-CBC encryption & PBKDF2 password hashing
│   └── database.py      # SQLite database access
├── contracts/
│   └── PriorAuthorization.sol # Solidity smart contract
├── public/
│   ├── index.html       # Web UI HTML template
│   └── app.js           # Frontend client logic & ethers.js integration
├── scripts/
│   └── deploy.js        # Hardhat deployment script
├── test/
│   └── PriorAuthorization.test.js # Smart contract unit tests
├── tests/
│   └── test_api.py      # FastAPI REST API unit tests
├── .env.example         # Environment configuration template
├── hardhat.config.js    # Hardhat setup
├── package.json         # Node.js manifest
└── requirements.txt     # Python manifest
```
