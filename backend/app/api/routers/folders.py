"""文件夹路由(单层文件归类,组织工具)。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Folder, Presentation, User
from app.schemas.presentation import FolderOut

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("", response_model=list[FolderOut])
def list_folders(db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> list[FolderOut]:
    return [FolderOut(id=f.id, name=f.name, created_at=f.created_at)
            for f in db.query(Folder).order_by(Folder.created_at).all()]


@router.post("", response_model=FolderOut)
def create_folder(body: dict, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> FolderOut:
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "文件夹名不能为空")
    f = Folder(name=name, owner_id=user.id)
    db.add(f)
    db.commit()
    db.refresh(f)
    return FolderOut(id=f.id, name=f.name, created_at=f.created_at)


@router.patch("/{folder_id}", response_model=FolderOut)
def rename_folder(folder_id: str, body: dict, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> FolderOut:
    f = db.get(Folder, folder_id)
    if not f:
        raise HTTPException(404, "文件夹不存在")
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "文件夹名不能为空")
    f.name = name
    db.commit()
    db.refresh(f)
    return FolderOut(id=f.id, name=f.name, created_at=f.created_at)


@router.delete("/{folder_id}")
def delete_folder(folder_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> dict:
    f = db.get(Folder, folder_id)
    if not f:
        raise HTTPException(404, "文件夹不存在")
    # 文件夹内文件 folder_id 置空(FK ondelete=SET NULL 兜底,显式也清)
    db.query(Presentation).filter(Presentation.folder_id == folder_id).update(
        {Presentation.folder_id: None}, synchronize_session=False
    )
    db.delete(f)
    db.commit()
    return {"detail": "已删除文件夹(文件已移出)"}
