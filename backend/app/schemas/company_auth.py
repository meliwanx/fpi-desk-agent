"""Pydantic schemas for company-user authentication."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CompanyUserInfo(BaseModel):
    id: str
    email: str
    display_name: str
    role: str


class CompanyLoginRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class CompanyLoginResponse(BaseModel):
    token: str
    expires_at: datetime
    user: CompanyUserInfo


class CompanySessionResponse(BaseModel):
    user: CompanyUserInfo
