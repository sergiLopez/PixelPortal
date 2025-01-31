from fastapi import Depends, FastAPI, HTTPException,Request
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
import repository,models, schemas
from database import SessionLocal, engine
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from utils import verify_password, create_access_token, create_refresh_token, get_hashed_password #production
import models
from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import SessionLocal, engine  # Asegúrate de que tu módulo de base de datos está importado correctamente
import models, schemas, repository  # Asegúrate de que tu
app = FastAPI()
import re
models.Base.metadata.create_all(bind=engine) # Creem la base de dades amb els models que hem definit a SQLAlchemy
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from repository import create_user
from models import Usuario as DBUsuario
from schemas import UsuarioCreate, Usuario
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import models, schemas, repository
from dependencies import get_db, verify_password, create_access_token, get_current_user
from datetime import timedelta
from repository import get_user_by_email
from typing import List

#email pattern
email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = repository.get_user_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.contrasena):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


#Registro
@app.post("/usuario/")
def create_user(user: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    db_email = repository.get_user_by_email(db, user.email)
    if db_email:
        raise HTTPException(status_code=404, detail="Email already registered")

    db_user = repository.get_user_by_username(db, user.nombre)
    if db_user:
        raise HTTPException(status_code=404, detail="User already registered")
    if not user.email:
        raise HTTPException(status_code=400, detail="The 'email' field is required")
    if not user.nombre:
        raise HTTPException(status_code=400, detail="The 'name' field is required")
    if not user.contrasena:
        raise HTTPException(status_code=400, detail="The 'password' field is required")
    if not re.match(email_pattern, user.email):
        raise HTTPException(status_code=400, detail="the format of the field 'email' is not valid.")

    db_user = repository.create_user(db, user)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": schemas.Token(access_token=access_token, token_type="bearer"), "user": db_user}

#Login
@app.post("/login")
async def login(usuario: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    db_user = db.query(DBUsuario).filter(DBUsuario.email == usuario.email).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not in Database")
    
    if not verify_password(usuario.contrasena, db_user.contrasena):
        raise HTTPException(status_code=404, detail="Incorrect password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": usuario.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer", "username": db_user.nombre}

#Modificar perfil de usuario
@app.put('/usuario/{username}', summary="Put user", response_model=schemas.Usuario)
def update_account(username: str, account: schemas.Usuario, db: Session = Depends(get_db)):
    db_account = repository.update_account(db, username, account)
    if db_account is None:
        raise HTTPException(status_code=404, detail="User does not exist")
    return db_account

#Obtener usuario por ID
@app.get("/usuarios/", response_model=List[schemas.Usuario])
def read_user( db: Session = Depends(get_db)):
    db_user = repository.get_all_user(db)
    return db_user


@app.get("/usuario/{user_id}", response_model=schemas.Usuario)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = repository.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return db_user

@app.get("/users/me/", response_model=schemas.Usuario)
async def read_users_me(current_user: models.Usuario = Depends(get_current_user)):
    return current_user

@app.post("/publicaciones/", response_model=schemas.Publicacion)
async def crear_publicacion(publicacion: schemas.PublicacionCreate, db: Session = Depends(get_db),current_user: models.Usuario = Depends(get_current_user) ):
    if not publicacion.titulo:
        raise HTTPException(status_code=400, detail="The 'titulo' field is required")
    if not publicacion.descripcion:
        raise HTTPException(status_code=400, detail="The 'descripcion' field is required")
    if not publicacion.usuario_nombre:
        raise HTTPException(status_code=400, detail="The 'usuario_nombre' field is required")
    if not publicacion.imagen_url:
        raise HTTPException(status_code=400, detail="The 'imagen_url' field is required")
    return repository.crear_publicacion(db=db, publicacion=publicacion, usuario_id=current_user.id)

@app.get("/publicaciones/", response_model=List[schemas.Publicacion])
def obtener_publicaciones(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    publicaciones = repository.obtener_publicaciones(db, skip=skip, limit=limit)
    return publicaciones

@app.delete("/publicacion/{publication_id}", response_model=schemas.Publicacion)
def delete_team(publication_id: int, db: Session = Depends(get_db),current_user: models.Usuario = Depends(get_current_user) ):
        db_publication = repository.delete_publication(db, publication_id)
        if db_publication is None:
            raise HTTPException(status_code=404, detail="Match not found")
        return db_publication
