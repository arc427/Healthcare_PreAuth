import pytest
from fastapi.testclient import TestClient

from app.crypto_utils import decrypt_data, encrypt_data, generate_hash, hash_password, verify_password
from app.main import app

client = TestClient(app)


def test_crypto_hash_and_pbkdf2():
    password = "secret_hospital_pass"
    pwd_hash = hash_password(password)
    assert verify_password(password, pwd_hash) is True
    assert verify_password("wrong_password", pwd_hash) is False


def test_crypto_aes_encrypt_decrypt():
    key = "test-encryption-key-healthcare-preauth"
    payload = {"patientId": "PT-9999", "diagnosis": "Test Diagnosis", "procedureCode": "AUTH-123"}
    encrypted_hex, iv_hex = encrypt_data(payload, key)
    decrypted = decrypt_data(encrypted_hex, iv_hex, key)
    assert decrypted == payload


def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert "hardhatConnected" in data


def test_api_login_success_and_failure():
    # Valid hospital login
    res_h = client.post("/api/login", json={"username": "hospital", "password": "password123"})
    assert res_h.status_code == 200
    data_h = res_h.json()
    assert data_h["role"] == "hospital"
    assert "token" in data_h

    # Valid insurer login
    res_i = client.post("/api/login", json={"username": "insurer", "password": "password123"})
    assert res_i.status_code == 200
    assert res_i.json()["role"] == "insurer"

    # Invalid password
    res_inv = client.post("/api/login", json={"username": "hospital", "password": "bad_password"})
    assert res_inv.status_code == 401


def test_protected_routes_unauthorized():
    res_req = client.post("/api/request", json={"patientId": "P1", "diagnosis": "D1", "procedureCode": "C1"})
    assert res_req.status_code == 401

    res_eval = client.post("/api/evaluate", json={"requestId": 1})
    assert res_eval.status_code == 401

    res_list = client.get("/api/requests")
    assert res_list.status_code == 401


def test_role_authorization_forbidden():
    # Login as hospital
    res_h = client.post("/api/login", json={"username": "hospital", "password": "password123"})
    h_token = res_h.json()["token"]

    # Hospital attempting to call insurer route should receive 403 Forbidden
    res_eval = client.post(
        "/api/evaluate",
        json={"requestId": 1},
        headers={"Authorization": f"Bearer {h_token}"},
    )
    assert res_eval.status_code == 403
