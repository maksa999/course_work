from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import database, models, schemas
import os
import pytz

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="Warehouse Inventory System",
    description="Система управления складскими запасами - Остатки, поставки, инвентаризации",
    version="2.0.0"
)

if not os.path.exists("templates"):
    os.makedirs("templates")
templates = Jinja2Templates(directory="templates")

moscow_tz = pytz.timezone('Europe/Moscow')

SECRET_KEY = "warehouse-secret-key-2024-course-project"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer()



def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "sub": data["sub"]})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



async def get_current_user_for_api(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
        db: Session = Depends(database.get_db)
):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_user_for_web(request: Request, db: Session = Depends(database.get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None

    user = get_user_by_email(db, email)
    return user


def require_auth_for_api(current_user: models.User = Depends(get_current_user_for_api)):
    return current_user


def require_auth_for_web(current_user=Depends(get_current_user_for_web)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login-page"}
        )
    return current_user



@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(database.get_db)):
    current_user = await get_current_user_for_web(request, db)

    if current_user:
        products_count = db.query(models.Product).filter(models.Product.user_id == current_user.id).count()
        supplies_count = db.query(models.Supply).filter(models.Supply.user_id == current_user.id).count()
        inventories_count = db.query(models.Inventory).filter(models.Inventory.user_id == current_user.id).count()
    else:
        products_count = 0
        supplies_count = 0
        inventories_count = 0

    return templates.TemplateResponse("index.html", {
        "request": request,
        "products_count": products_count,
        "supplies_count": supplies_count,
        "inventories_count": inventories_count,
        "current_user": current_user
    })


@app.get("/login-page", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register-page", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register_from_form(
        email: str = Form(...),
        password: str = Form(...),
        full_name: str = Form(...),
        db: Session = Depends(database.get_db)
):
    try:
        if len(password) < 6:
            return RedirectResponse(url="/register-page?error=Password+must+be+at+least+6+characters", status_code=303)

        existing_user = db.query(models.User).filter(models.User.email == email).first()
        if existing_user:
            return RedirectResponse(url="/register-page?error=Email+already+registered", status_code=303)

        hashed_password = get_password_hash(password)

        db_user = models.User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name
        )

        db.add(db_user)
        db.commit()

        return RedirectResponse(url="/login-page?success=Registration+successful", status_code=303)

    except Exception as e:
        return RedirectResponse(url="/register-page?error=Registration+failed+try+again", status_code=303)


@app.post("/login")
async def login_from_form(
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(database.get_db)
):
    user = authenticate_user(db, email, password)
    if not user:
        return RedirectResponse(url="/login-page?error=Invalid+credentials", status_code=303)

    access_token = create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/?success=Login+successful", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="access_token")
    return response


@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Warehouse API is running"}



@app.post("/token")
async def login_for_access_token(
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(database.get_db)
):
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/products/", response_model=List[schemas.Product])
def read_products_api(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    return db.query(models.Product).filter(
        models.Product.user_id == current_user.id
    ).offset(skip).limit(limit).all()


@app.get("/products/{product_id}", response_model=schemas.Product)
def read_product_api(
        product_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.user_id == current_user.id
    ).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/products/", response_model=schemas.Product)
def create_product_api(
        product: schemas.ProductCreate,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    db_product = models.Product(**product.dict(), user_id=current_user.id)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.put("/products/{product_id}", response_model=schemas.Product)
def update_product_api(
        product_id: int,
        product: schemas.ProductCreate,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    db_product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.user_id == current_user.id
    ).first()

    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    for key, value in product.dict().items():
        setattr(db_product, key, value)

    db.commit()
    db.refresh(db_product)
    return db_product


@app.delete("/products/{product_id}")
def delete_product_api(
        product_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    db_product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.user_id == current_user.id
    ).first()

    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(db_product)
    db.commit()
    return {"message": "Product deleted successfully"}


@app.get("/supplies/", response_model=List[schemas.Supply])
def read_supplies_api(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    return db.query(models.Supply).filter(
        models.Supply.user_id == current_user.id
    ).offset(skip).limit(limit).all()


@app.post("/supplies/", response_model=schemas.Supply)
def create_supply_api(
        supply: schemas.SupplyCreate,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    product = db.query(models.Product).filter(
        models.Product.id == supply.product_id,
        models.Product.user_id == current_user.id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    db_supply = models.Supply(**supply.dict(), user_id=current_user.id)
    product.current_stock += supply.quantity

    db.add(db_supply)
    db.commit()
    db.refresh(db_supply)
    return db_supply


@app.delete("/supplies/{supply_id}")
def delete_supply_api(
        supply_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    supply = db.query(models.Supply).filter(
        models.Supply.id == supply_id,
        models.Supply.user_id == current_user.id
    ).first()

    if not supply:
        raise HTTPException(status_code=404, detail="Supply not found")

    product = db.query(models.Product).filter(
        models.Product.id == supply.product_id,
        models.Product.user_id == current_user.id
    ).first()

    if product:
        product.current_stock -= supply.quantity

    db.delete(supply)
    db.commit()
    return {"message": "Supply deleted successfully"}


@app.get("/inventories/", response_model=List[schemas.Inventory])
def read_inventories_api(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    return db.query(models.Inventory).filter(
        models.Inventory.user_id == current_user.id
    ).offset(skip).limit(limit).all()


@app.post("/inventories/", response_model=schemas.Inventory)
def create_inventory_api(
        inventory: schemas.InventoryCreate,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    moscow_time = datetime.now(moscow_tz)
    db_inventory = models.Inventory(
        **inventory.dict(),
        user_id=current_user.id,
        created_at=moscow_time
    )
    db.add(db_inventory)
    db.commit()
    db.refresh(db_inventory)
    return db_inventory


@app.put("/inventories/{inventory_id}", response_model=schemas.Inventory)
def update_inventory_api(
        inventory_id: int,
        inventory: schemas.InventoryUpdate,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    db_inventory = db.query(models.Inventory).filter(
        models.Inventory.id == inventory_id,
        models.Inventory.user_id == current_user.id
    ).first()

    if db_inventory is None:
        raise HTTPException(status_code=404, detail="Inventory not found")

    update_data = inventory.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_inventory, key, value)

    db_inventory.updated_at = datetime.now(moscow_tz)

    db.commit()
    db.refresh(db_inventory)
    return db_inventory


@app.delete("/inventories/{inventory_id}")
def delete_inventory_api(
        inventory_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_api)
):
    db_inventory = db.query(models.Inventory).filter(
        models.Inventory.id == inventory_id,
        models.Inventory.user_id == current_user.id
    ).first()

    if db_inventory is None:
        raise HTTPException(status_code=404, detail="Inventory not found")

    db.delete(db_inventory)
    db.commit()
    return {"message": "Inventory deleted successfully"}



@app.get("/products-page", response_class=HTMLResponse)
async def products_page(
        request: Request,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    products = db.query(models.Product).filter(models.Product.user_id == current_user.id).all()
    return templates.TemplateResponse("products.html", {
        "request": request,
        "products": products,
        "current_user": current_user
    })


@app.get("/supplies-page", response_class=HTMLResponse)
async def supplies_page(
        request: Request,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    supplies = db.query(models.Supply).filter(models.Supply.user_id == current_user.id).all()
    products = db.query(models.Product).filter(models.Product.user_id == current_user.id).all()
    return templates.TemplateResponse("supplies.html", {
        "request": request,
        "supplies": supplies,
        "products": products,
        "current_user": current_user
    })


@app.get("/inventories-page", response_class=HTMLResponse)
async def inventories_page(
        request: Request,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    inventories = db.query(models.Inventory).filter(models.Inventory.user_id == current_user.id).all()
    return templates.TemplateResponse("inventories.html", {
        "request": request,
        "inventories": inventories,
        "current_user": current_user
    })



@app.post("/products/create")
async def create_product_from_form(
        request: Request,
        name: str = Form(...),
        sku: str = Form(...),
        description: str = Form(None),
        min_stock: int = Form(0),
        max_stock: int = Form(1000),
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    existing_product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if existing_product:
        return RedirectResponse(url="/products-page?error=SKU+already+exists", status_code=303)

    db_product = models.Product(
        name=name,
        sku=sku,
        description=description,
        min_stock=min_stock,
        max_stock=max_stock,
        user_id=current_user.id
    )
    db.add(db_product)
    db.commit()

    return RedirectResponse(url="/products-page?success=Product+created", status_code=303)


@app.post("/products/delete/{product_id}")
async def delete_product_from_form(
        request: Request,
        product_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.user_id == current_user.id
    ).first()
    if product:
        db.delete(product)
        db.commit()
        return RedirectResponse(url="/products-page?success=Product+deleted", status_code=303)
    return RedirectResponse(url="/products-page?error=Product+not+found", status_code=303)


@app.post("/supplies/create")
async def create_supply_from_form(
        request: Request,
        product_id: int = Form(...),
        quantity: int = Form(...),
        supplier: str = Form(...),
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.user_id == current_user.id
    ).first()
    if not product:
        return RedirectResponse(url="/supplies-page?error=Product+not+found", status_code=303)

    moscow_time = datetime.now(moscow_tz)
    db_supply = models.Supply(
        product_id=product_id,
        quantity=quantity,
        supplier=supplier,
        supply_date=moscow_time,
        user_id=current_user.id
    )
    product.current_stock += quantity

    db.add(db_supply)
    db.commit()

    return RedirectResponse(url="/supplies-page?success=Supply+created", status_code=303)


@app.post("/supplies/delete/{supply_id}")
async def delete_supply_from_form(
        request: Request,
        supply_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    supply = db.query(models.Supply).filter(
        models.Supply.id == supply_id,
        models.Supply.user_id == current_user.id
    ).first()

    if not supply:
        return RedirectResponse(url="/supplies-page?error=Поставка+не+найдена", status_code=303)

    product = db.query(models.Product).filter(
        models.Product.id == supply.product_id,
        models.Product.user_id == current_user.id
    ).first()

    if product:
        product.current_stock -= supply.quantity

    db.delete(supply)
    db.commit()

    return RedirectResponse(url="/supplies-page?success=Поставка+удалена", status_code=303)


@app.post("/inventories/create")
async def create_inventory_from_form(
        request: Request,
        name: str = Form(...),
        description: str = Form(None),
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    moscow_time = datetime.now(moscow_tz)
    db_inventory = models.Inventory(
        name=name,
        description=description,
        created_at=moscow_time,
        user_id=current_user.id
    )
    db.add(db_inventory)
    db.commit()

    return RedirectResponse(url="/inventories-page?success=Инвентаризация+создана", status_code=303)


@app.post("/inventories/update/{inventory_id}")
async def update_inventory_from_form(
        request: Request,
        inventory_id: int,
        name: str = Form(...),
        comment: str = Form(None),
        is_successful: bool = Form(False),
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    inventory = db.query(models.Inventory).filter(
        models.Inventory.id == inventory_id,
        models.Inventory.user_id == current_user.id
    ).first()

    if not inventory:
        return RedirectResponse(url="/inventories-page?error=Инвентаризация+не+найдена", status_code=303)

    inventory.name = name
    inventory.comment = comment
    inventory.is_successful = is_successful
    inventory.updated_at = datetime.now(moscow_tz)

    db.commit()

    return RedirectResponse(url="/inventories-page?success=Инвентаризация+обновлена", status_code=303)


@app.post("/inventories/update-status/{inventory_id}")
async def update_inventory_status(
        request: Request,
        inventory_id: int,
        status: str = Form(...),
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    inventory = db.query(models.Inventory).filter(
        models.Inventory.id == inventory_id,
        models.Inventory.user_id == current_user.id
    ).first()
    if not inventory:
        return RedirectResponse(url="/inventories-page?error=Inventory+not+found", status_code=303)

    valid_statuses = ["pending", "completed", "cancelled"]
    if status not in valid_statuses:
        return RedirectResponse(url="/inventories-page?error=Invalid+status", status_code=303)

    inventory.status = status
    db.commit()

    return RedirectResponse(url="/inventories-page?success=Status+updated", status_code=303)


@app.post("/inventories/delete/{inventory_id}")
async def delete_inventory_from_form(
        request: Request,
        inventory_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.User = Depends(require_auth_for_web)
):
    inventory = db.query(models.Inventory).filter(
        models.Inventory.id == inventory_id,
        models.Inventory.user_id == current_user.id
    ).first()
    if inventory:
        db.delete(inventory)
        db.commit()
        return RedirectResponse(url="/inventories-page?success=Inventory+deleted", status_code=303)
    return RedirectResponse(url="/inventories-page?error=Inventory+not+found", status_code=303)



from fastapi.openapi.utils import get_openapi


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }

    public_endpoints = [
        "/", "/login-page", "/register-page",
        "/register", "/login", "/logout",
        "/health", "/token", "/docs", "/openapi.json"
    ]

    for path, methods in openapi_schema["paths"].items():
        if path in public_endpoints or path.endswith("-page"):
            continue

        for method_name, method in methods.items():
            method["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

@app.on_event("startup")
def startup_event():
    db = database.SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            hashed_password = get_password_hash("admin123")
            user = models.User(
                email="admin@warehouse.com",
                hashed_password=hashed_password,
                full_name="Administrator"
            )
            db.add(user)
            db.commit()
            print("✅ Initial user created: admin@warehouse.com / admin123")
    except Exception as e:
        print(f"⚠️ Startup warning: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)