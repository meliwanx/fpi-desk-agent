"""Tests for company-auth password and session-token helpers."""

from __future__ import annotations

from app.company_auth.security import hash_password, hash_token, verify_password


def test_password_hash_verifies_original_password():
    hashed = hash_password("CorrectHorseBatteryStaple1!")

    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password("CorrectHorseBatteryStaple1!", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_token_hash_is_stable_and_not_plaintext():
    token = "fpi_sess_example_token"

    first = hash_token(token)
    second = hash_token(token)

    assert first == second
    assert first != token
