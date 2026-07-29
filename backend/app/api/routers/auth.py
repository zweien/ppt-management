"""Auth router: login / logout / change password (PRD §14.1)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, PasswordChangeRequest, TokenResponse, UserOut, UserOutResolver

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")
    token = create_access_token(user.id, extra={"username": user.username})
    return TokenResponse(access_token=token, user=UserOutResolver.from_model(user))


@router.post("/logout")
def logout(user: User = Depends(get_current_user)) -> dict:
    # Stateless JWT: client discards token. Return success.
    return {"detail": "已登出"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOutResolver.from_model(user)


@router.put("/password")
def change_password(
    body: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    user.password_hash = hash_password(body.new_password)
    db.add(user)
    db.commit()
    return {"detail": "密码已修改"}
