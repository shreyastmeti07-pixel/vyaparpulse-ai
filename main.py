import time
import secrets
import hashlib
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from lstm_engine import FastLSTMForecaster

DATABASE_URL = "sqlite:///./vyaparpulse_fullstack.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

lstm_ai = FastLSTMForecaster(lookback=7)


def hash_password(password: str) -> str:
    salt = "vyaparpulse_2026_salt"
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# --- Database Models ---
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


def ensure_shop_seeded(db: Session, business_type: str):
    if db.query(Product).filter(Product.business_type == business_type).count() == 0:
        for item in STARTER_CATALOGS.get(business_type, STARTER_CATALOGS["Supermart"]):
            db.add(Product(business_type=business_type, **item))
        db.commit()

    if db.query(Invoice).filter(Invoice.business_type == business_type).count() == 0:
        sample_invoices = [
            Invoice(invoice_no=f"INV-{business_type[:3].upper()}-101", business_type=business_type, customer_name="Ramesh Kumar", payment_mode="UPI", subtotal=420.0, gst_total=21.0, grand_total=441.0, items_json=[]),
            Invoice(invoice_no=f"INV-{business_type[:3].upper()}-102", business_type=business_type, customer_name="Priya Nair", payment_mode="Cash", subtotal=680.0, gst_total=34.0, grand_total=714.0, items_json=[]),
            Invoice(invoice_no=f"INV-{business_type[:3].upper()}-103", business_type=business_type, customer_name="Walk-in Customer", payment_mode="Card", subtotal=540.0, gst_total=27.0, grand_total=567.0, items_json=[]),
        ]
        db.add_all(sample_invoices)
        db.commit()


app = FastAPI(title="VyaparPulse Pro Full-Stack + PyTorch LSTM + OTP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Pydantic Schemas ---
class OTPRequest(BaseModel):
    mobile: str


class OTPVerify(BaseModel):
    mobile: str
    otp: str


class OwnerRegister(BaseModel):
    full_name: str
    business_name: str
    business_type: str
    email: EmailStr
    mobile: str
    password: str


class OwnerLogin(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordReset(BaseModel):
    mobile: str
    otp: str
    new_password: str


class ProductCreate(BaseModel):
    business_type: str
    sku: str
    name: str
    category: str
    unit: str = "Unit"
    price: float
    gst_rate: float = 5.0
    stock: int
    min_stock: int = 10


class BillItem(BaseModel):
    product_id: int
    qty: int


class BillCreate(BaseModel):
    business_type: str
    customer_name: str = "Walk-in Customer"
    payment_mode: str = "UPI"
    items: list[BillItem]


@app.get("/")
def serve_frontend():
    return FileResponse("index.html")


# --- 1. Owner Auth, OTP Verification & Forgot Password ---
@app.post("/api/auth/send-otp")
def send_otp(payload: OTPRequest, db: Session = Depends(get_db)):
    mobile = payload.mobile.strip()
    if len(mobile) != 10 or not mobile.isdigit():
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit Indian mobile number")

    otp_code = str(secrets.randbelow(900000) + 100000)
    record = db.query(OTPVerification).filter(OTPVerification.mobile == mobile).first()
    if not record:
        record = OTPVerification(mobile=mobile)
        db.add(record)

    record.otp_code = otp_code
    record.expires_at = time.time() + 300
    record.verified = False
    db.commit()
    return {"status": "otp_sent", "mobile": f"+91 {mobile}", "demo_otp": otp_code}


@app.post("/api/auth/verify-otp")
def verify_otp(payload: OTPVerify, db: Session = Depends(get_db)):
    mobile = payload.mobile.strip()
    record = db.query(OTPVerification).filter(OTPVerification.mobile == mobile).first()
    if not record:
        raise HTTPException(status_code=400, detail="Please request an OTP first")
    if time.time() > record.expires_at:
        raise HTTPException(status_code=400, detail="OTP expired. Please resend OTP")
    if record.otp_code != payload.otp.strip():
        raise HTTPException(status_code=400, detail="Invalid 6-digit OTP")

    record.verified = True
    db.commit()
    return {"status": "verified"}


@app.post("/api/auth/register")
def register_owner(payload: OwnerRegister, db: Session = Depends(get_db)):
    mobile = payload.mobile.strip()
    otp_record = db.query(OTPVerification).filter(OTPVerification.mobile == mobile).first()
    if not otp_record or not otp_record.verified:
        raise HTTPException(status_code=403, detail="Please verify your mobile OTP before registering")

    if db.query(Owner).filter(Owner.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(Owner).filter(Owner.mobile == mobile).first():
        raise HTTPException(status_code=400, detail="Mobile number already registered")

    owner = Owner(
        full_name=payload.full_name,
        business_name=payload.business_name,
        business_type=payload.business_type,
        email=payload.email,
        mobile=mobile,
        is_mobile_verified=True,
        hashed_password=hash_password(payload.password),
    )
    db.add(owner)
    db.delete(otp_record)
    db.commit()
    ensure_shop_seeded(db, payload.business_type)

    return {
        "status": "registered",
        "owner": {
            "full_name": owner.full_name,
            "business_name": owner.business_name,
            "business_type": owner.business_type,
            "email": owner.email,
            "mobile": owner.mobile,
        },
    }


@app.post("/api/auth/login")
def login_owner(payload: OwnerLogin, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.email == payload.email).first()
    if not owner or not verify_password(payload.password, owner.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    ensure_shop_seeded(db, owner.business_type)
    return {
        "status": "authenticated",
        "owner": {
            "full_name": owner.full_name,
            "business_name": owner.business_name,
            "business_type": owner.business_type,
            "email": owner.email,
            "mobile": owner.mobile,
        },
    }


@app.post("/api/auth/forgot-password/send-otp")
def send_forgot_password_otp(payload: OTPRequest, db: Session = Depends(get_db)):
    mobile = payload.mobile.strip()
    owner = db.query(Owner).filter(Owner.mobile == mobile).first()
    if not owner:
        raise HTTPException(status_code=404, detail="No owner account found with this mobile number")

    otp_code = str(secrets.randbelow(900000) + 100000)
    record = db.query(OTPVerification).filter(OTPVerification.mobile == mobile).first()
    if not record:
        record = OTPVerification(mobile=mobile)
        db.add(record)

    record.otp_code = otp_code
    record.expires_at = time.time() + 300
    record.verified = False
    db.commit()

    return {
        "status": "otp_sent",
        "email": owner.email,
        "demo_otp": otp_code,
    }


@app.post("/api/auth/forgot-password/reset")
def reset_owner_password(payload: ForgotPasswordReset, db: Session = Depends(get_db)):
    mobile = payload.mobile.strip()
    record = db.query(OTPVerification).filter(OTPVerification.mobile == mobile).first()
    if not record or record.otp_code != payload.otp.strip() or time.time() > record.expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    owner = db.query(Owner).filter(Owner.mobile == mobile).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner account not found")

    owner.hashed_password = hash_password(payload.new_password)
    db.delete(record)
    db.commit()
    return {"status": "password_reset", "email": owner.email}


# --- 2. Dashboard, Inventory, GST Billing & PyTorch LSTM Endpoints ---
@app.get("/api/dashboard/{business_type}")
def get_dashboard_data(business_type: str, db: Session = Depends(get_db)):
    ensure_shop_seeded(db, business_type)
    products = db.query(Product).filter(Product.business_type == business_type).all()
    invoices = db.query(Invoice).filter(Invoice.business_type == business_type).order_by(Invoice.id.desc()).all()

    enriched_products = []
    low_stock_count = 0
    inventory_value = 0.0

    for p in products:
        ai_pred = lstm_ai.forecast(p.id, p.daily_sales_history, p.stock)
        if ai_pred["low_stock_alert"] or p.stock <= p.min_stock:
            low_stock_count += 1
        inventory_value += p.price * p.stock
        enriched_products.append({
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "unit": p.unit,
            "price": p.price,
            "gst_rate": p.gst_rate,
            "stock": p.stock,
            "min_stock": p.min_stock,
            "daily_sales_history": p.daily_sales_history,
            "lstm_forecast": ai_pred,
        })

    total_revenue = sum(inv.grand_total for inv in invoices)
    return {
        "kpis": {
            "total_revenue": round(total_revenue, 2),
            "invoice_count": len(invoices),
            "inventory_value": round(inventory_value, 2),
            "low_stock_count": low_stock_count,
        },
        "products": enriched_products,
        "invoices": [
            {
                "invoice_no": inv.invoice_no,
                "customer_name": inv.customer_name,
                "payment_mode": inv.payment_mode,
                "subtotal": inv.subtotal,
                "gst_total": inv.gst_total,
                "grand_total": inv.grand_total,
                "items": inv.items_json or [],
            }
            for inv in invoices[:15]
        ],
    }


@app.post("/api/products")
def add_shop_product(item: ProductCreate, db: Session = Depends(get_db)):
    default_curve = [max(2, round(item.stock * 0.35))] * 14
    product = Product(**item.model_dump(), daily_sales_history=default_curve)
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"status": "created", "id": product.id}


@app.post("/api/products/{product_id}/restock")
def restock_product(product_id: int, qty: int = 10, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.stock += qty
    db.commit()
    return {"status": "restocked", "new_stock": product.stock}


@app.post("/api/billing/create")
def create_gst_bill(bill: BillCreate, db: Session = Depends(get_db)):
    subtotal, gst_total = 0.0, 0.0
    billed_items = []

    for entry in bill.items:
        product = db.query(Product).filter(Product.id == entry.product_id).first()
        if not product or product.stock < entry.qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product ID {entry.product_id}")

        product.stock -= entry.qty
        hist = list(product.daily_sales_history or [])
        if hist:
            hist[-1] += entry.qty
        else:
            hist.append(float(entry.qty))
        product.daily_sales_history = hist

        line_base = product.price * entry.qty
        line_gst = round(line_base * (product.gst_rate / 100.0), 2)
        subtotal += line_base
        gst_total += line_gst

        billed_items.append({
            "name": product.name,
            "qty": entry.qty,
            "price": product.price,
            "gst": line_gst,
            "total": round(line_base + line_gst, 2),
        })

    inv_no = f"INV-{int(time.time()) % 100000}"
    invoice = Invoice(
        invoice_no=inv_no,
        business_type=bill.business_type,
        customer_name=bill.customer_name,
        payment_mode=bill.payment_mode,
        subtotal=round(subtotal, 2),
        gst_total=round(gst_total, 2),
        grand_total=round(subtotal + gst_total, 2),
        items_json=billed_items,
    )
    db.add(invoice)
    db.commit()
    return {
        "status": "billed",
        "invoice_no": inv_no,
        "customer_name": bill.customer_name,
        "payment_mode": bill.payment_mode,
        "subtotal": invoice.subtotal,
        "gst_total": invoice.gst_total,
        "grand_total": invoice.grand_total,
        "items": billed_items,
    }