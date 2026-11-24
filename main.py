import os
import time
import secrets
import hashlib
import requests
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session

try:
    from lstm_engine import FastLSTMForecaster
    lstm_ai = FastLSTMForecaster(lookback=7)
except Exception:
    lstm_ai = None

DATABASE_URL = "sqlite:///./vyaparpulse_fullstack.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def hash_password(password: str) -> str:
    salt = "vyaparpulse_2026_salt"
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def dispatch_real_sms(mobile: str, otp_code: str) -> bool:
    api_key = os.getenv("FAST2SMS_API_KEY", "").strip()
    if not api_key:
        return False
    try:
        resp = requests.post(
            "https://www.fast2sms.com/dev/bulkV2",
            headers={"authorization": api_key, "Content-Type": "application/json"},
            json={
                "route": "q",
                "message": f"Your VyaparPulse Pro verification OTP is {otp_code}. Valid for 5 minutes.",
                "language": "english",
                "numbers": mobile,
            },
            timeout=8,
        )
        return resp.status_code == 200 and resp.json().get("return", False)
    except Exception:
        return False


class OTPVerification(Base):
    __tablename__ = "otp_verifications"
    mobile = Column(String, primary_key=True, index=True)
    otp_code = Column(String)
    expires_at = Column(Float)
    verified = Column(Boolean, default=False)


class Owner(Base):
    __tablename__ = "owners"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    business_name = Column(String)
    business_type = Column(String)
    email = Column(String, unique=True, index=True)
    mobile = Column(String, unique=True)
    is_mobile_verified = Column(Boolean, default=True)
    hashed_password = Column(String)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    business_type = Column(String, index=True)
    sku = Column(String)
    name = Column(String)
    category = Column(String)
    unit = Column(String, default="Unit")
    price = Column(Float)
    gst_rate = Column(Float, default=5.0)
    stock = Column(Integer)
    min_stock = Column(Integer, default=10)
    daily_sales_history = Column(JSON, default=list)


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_no = Column(String, unique=True)
    business_type = Column(String)
    customer_name = Column(String)
    payment_mode = Column(String)
    subtotal = Column(Float)
    gst_total = Column(Float)
    grand_total = Column(Float)
    items_json = Column(JSON)


Base.metadata.create_all(bind=engine)

STARTER_CATALOGS = {
    "Hotel": [
        {"sku": "HTL-01", "name": "Masala Dosa", "category": "South Indian", "unit": "Plate", "price": 80, "gst_rate": 5, "stock": 14, "min_stock": 15, "daily_sales_history": [28, 30, 26, 32, 38, 45, 42, 29, 31, 35, 40, 48, 44, 36]},
        {"sku": "HTL-02", "name": "Filter Coffee", "category": "Beverages", "unit": "Cup", "price": 30, "gst_rate": 5, "stock": 48, "min_stock": 20, "daily_sales_history": [50, 52, 48, 55, 60, 68, 65, 51, 54, 58, 62, 70, 66, 59]},
        {"sku": "HTL-03", "name": "South Indian Meals", "category": "Lunch", "unit": "Thali", "price": 130, "gst_rate": 5, "stock": 9, "min_stock": 12, "daily_sales_history": [20, 22, 19, 24, 28, 34, 31, 21, 23, 25, 29, 36, 32, 27]},
        {"sku": "HTL-04", "name": "Paneer Butter Masala", "category": "Main Course", "unit": "Bowl", "price": 190, "gst_rate": 5, "stock": 22, "min_stock": 10, "daily_sales_history": [10, 12, 11, 14, 18, 22, 20, 11, 13, 15, 19, 24, 21, 16]},
        {"sku": "HTL-05", "name": "Idli Vada Combo", "category": "South Indian", "unit": "Plate", "price": 60, "gst_rate": 5, "stock": 30, "min_stock": 15, "daily_sales_history": [32, 35, 30, 38, 42, 49, 46, 34, 36, 40, 44, 52, 48, 41]},
        {"sku": "HTL-06", "name": "Veg Pulao", "category": "Rice & Biryani", "unit": "Plate", "price": 110, "gst_rate": 5, "stock": 11, "min_stock": 14, "daily_sales_history": [15, 17, 14, 19, 22, 27, 25, 16, 18, 20, 24, 29, 26, 21]},
    ],
    "Supermart": [
        {"sku": "SPM-01", "name": "Aashirvaad Atta (5kg)", "category": "Staples", "unit": "Bag", "price": 245, "gst_rate": 5, "stock": 8, "min_stock": 12, "daily_sales_history": [10, 12, 11, 14, 18, 22, 19, 11, 13, 15, 20, 24, 21, 16]},
        {"sku": "SPM-02", "name": "Sunpure Sunflower Oil (1L)", "category": "Edible Oil", "unit": "Pouch", "price": 135, "gst_rate": 5, "stock": 28, "min_stock": 15, "daily_sales_history": [15, 16, 14, 18, 21, 25, 23, 16, 17, 19, 22, 26, 24, 20]},
        {"sku": "SPM-03", "name": "Tata Salt (1kg)", "category": "Groceries", "unit": "Pack", "price": 28, "gst_rate": 0, "stock": 42, "min_stock": 20, "daily_sales_history": [22, 24, 21, 25, 28, 32, 30, 23, 25, 27, 29, 34, 31, 26]},
        {"sku": "SPM-04", "name": "Surf Excel Matic (2kg)", "category": "Home Care", "unit": "Pack", "price": 390, "gst_rate": 18, "stock": 6, "min_stock": 10, "daily_sales_history": [6, 7, 5, 8, 10, 13, 12, 6, 8, 9, 11, 14, 12, 9]},
        {"sku": "SPM-05", "name": "Sona Masoori Rice (10kg)", "category": "Staples", "unit": "Bag", "price": 560, "gst_rate": 5, "stock": 15, "min_stock": 10, "daily_sales_history": [8, 9, 7, 10, 13, 16, 15, 9, 10, 12, 14, 17, 15, 12]},
        {"sku": "SPM-06", "name": "Red Label Tea (500g)", "category": "Beverages", "unit": "Pack", "price": 265, "gst_rate": 5, "stock": 19, "min_stock": 12, "daily_sales_history": [9, 11, 10, 12, 15, 18, 16, 10, 11, 13, 15, 19, 17, 14]},
    ],
    "General Store": [
        {"sku": "GEN-01", "name": "Nandini Toned Milk (1L)", "category": "Dairy", "unit": "Packet", "price": 54, "gst_rate": 0, "stock": 16, "min_stock": 20, "daily_sales_history": [40, 42, 39, 44, 48, 52, 50, 41, 43, 45, 49, 55, 51, 46]},
        {"sku": "GEN-02", "name": "Parle-G Gold Biscuits", "category": "Snacks", "unit": "Pack", "price": 25, "gst_rate": 12, "stock": 38, "min_stock": 15, "daily_sales_history": [18, 20, 17, 22, 25, 29, 27, 19, 21, 23, 26, 30, 28, 24]},
        {"sku": "GEN-03", "name": "Colgate Strong Teeth (200g)", "category": "Personal Care", "unit": "Tube", "price": 115, "gst_rate": 18, "stock": 7, "min_stock": 10, "daily_sales_history": [7, 8, 6, 9, 11, 14, 12, 8, 9, 10, 12, 15, 13, 10]},
        {"sku": "GEN-04", "name": "Classmate Notebook (180pg)", "category": "Stationery", "unit": "Book", "price": 65, "gst_rate": 12, "stock": 25, "min_stock": 12, "daily_sales_history": [10, 11, 9, 12, 15, 18, 16, 11, 12, 14, 16, 19, 17, 13]},
        {"sku": "GEN-05", "name": "Maggi 2-Minute Noodles", "category": "Snacks", "unit": "Pack", "price": 14, "gst_rate": 12, "stock": 45, "min_stock": 20, "daily_sales_history": [25, 27, 24, 29, 33, 38, 35, 26, 28, 31, 34, 40, 36, 31]},
        {"sku": "GEN-06", "name": "Amul Butter (100g)", "category": "Dairy", "unit": "Pack", "price": 58, "gst_rate": 12, "stock": 9, "min_stock": 12, "daily_sales_history": [12, 13, 11, 14, 17, 20, 18, 12, 14, 15, 18, 21, 19, 16]},
    ],
}
