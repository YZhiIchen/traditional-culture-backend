"""
上传路由：图片上传 / 文本上传（适配新版 recognition_service）
"""
import uuid
from datetime import datetime
from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR, MAX_UPLOAD_SIZE, ALLOWED_IMAGE_TYPES
from ..database import get_db
from ..models import User, Resource
from ..schemas.upload import TextUploadRequest
from ..services import recognition_service
from ..utils.auth import require_user
from ..utils.response import success, fail

router = APIRouter(prefix="/upload", tags=["上传"])
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@router.post("")
def upload_image(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        return fail(400, "仅支持 JPG / PNG / WEBP 格式")

    content = file.file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return fail(400, "文件不超过 10MB")

    file_id = uuid.uuid4().hex[:12]
    ext = Path(file.filename).suffix if file.filename else ".jpg"
    save_name = f"{file_id}{ext}"
    save_path = UPLOAD_DIR / save_name
    with open(save_path, "wb") as f:
        f.write(content)

    # 调用新版 recognition_service（传入 file_id + recognition_time）
    ai = recognition_service.recognize_image(
        str(save_path),
        file.filename or "unknown",
        len(content),
        file_id,
        _now(),
    )

    # ai 返回结构: {id, fileName, fileType, fileUrl, fileSize, recognitionTime, rawData, result}
    r = ai.get("result", {})

    resource = Resource(
        file_id=file_id,
        owner_id=current_user.id,
        file_name=file.filename or "unknown",
        file_type="image",
        file_size=len(content),
        file_url=f"/uploads/{save_name}",
        status="completed",
        recognition_time=datetime.now(),
        title=r.get("title") or file.filename,
        author=r.get("author"),
        dynasty=r.get("dynasty"),
        description=r.get("description"),
        tags=",".join(r.get("tags", [])) if r.get("tags") else "",
        content=r.get("content"),
        confidence=r.get("confidence"),
        raw_data=str(ai),
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return success(resource.to_dict(), "上传并识别成功")


@router.post("/text")
def upload_text(
    data: TextUploadRequest,
    current_user: Annotated[User, Depends(require_user)],
    db: Annotated[Session, Depends(get_db)],
):
    file_id = uuid.uuid4().hex[:12]
    file_name = f"{data.title}.txt"

    ai = recognition_service.recognize_text(
        data.content,
        file_id,
        file_name,
        _now(),
    )

    r = ai.get("result", {})

    resource = Resource(
        file_id=file_id,
        owner_id=current_user.id,
        file_name=file_name,
        file_type="text",
        file_size=len(data.content.encode("utf-8")),
        status="completed",
        recognition_time=datetime.now(),
        title=r.get("title") or data.title,
        author=r.get("author"),
        dynasty=r.get("dynasty"),
        description=r.get("description"),
        tags=",".join(r.get("tags", [])) if r.get("tags") else "",
        content=r.get("content") or data.content,
        confidence=r.get("confidence"),
        raw_data=str(ai),
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return success(resource.to_dict(), "识别完成")
