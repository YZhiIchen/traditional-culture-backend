"""
上传路由：图片上传 / 文本上传（适配新版 recognition_service）
"""
import json
import uuid
from datetime import datetime
from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR, MAX_UPLOAD_SIZE, MAX_TEXT_SIZE, ALLOWED_IMAGE_TYPES, FILE_MAGIC
from ..database import get_db
from ..models import Resource
from ..models.user import User
from ..schemas.upload import TextUploadRequest
from ..services import recognition_service
from ..utils.auth import require_user
from ..utils.response import success, fail


def _register_if_new(r, db):
    """如果AI识别出新的朝代/作者，自动注册到知识库"""
    if r.get("dynasty") and r["dynasty"] != "现代":
        recognition_service.register_dynasty(r["dynasty"], db)
    if r.get("author") and r["author"] != "佚名":
        recognition_service.register_author(r["author"], r.get("dynasty"), db)

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

    # 魔数校验：验证文件头与声称的 content_type 一致
    content_type = file.content_type
    expected_magic = FILE_MAGIC.get(content_type)
    if expected_magic and not content.startswith(expected_magic):
        # WebP 特殊处理：开头是 RIFF + 4字节长度 + WEBP
        if content_type == "image/webp":
            if len(content) < 12 or content[8:12] != b"WEBP":
                return fail(400, "文件内容与类型不匹配（魔数校验失败）")
        else:
            return fail(400, "文件内容与类型不匹配（魔数校验失败）")

    file_id = uuid.uuid4().hex[:12]
    ext = Path(file.filename).suffix if file.filename else ".jpg"
    save_name = f"{file_id}{ext}"
    save_path = UPLOAD_DIR / save_name
    with open(save_path, "wb") as f:
        f.write(content)

    # 调用AI识别，捕获所有异常
    try:
        ai = recognition_service.recognize_image(
            str(save_path),
            file.filename or "unknown",
            len(content),
            file_id,
            _now(),
        )
    except Exception as e:
        # 识别失败删除临时图片
        try:
            Path(save_path).unlink(missing_ok=True)
        except:
            pass
        err_text = str(e)
        if err_text == "非文物":
            return fail(500, "AI图像识别失败\n非文物")
        return fail(500, f"AI图像识别失败：{err_text}")

    # 正常文物，入库
    r = ai.get("result", {})
    # 自动注册新朝代/作者到知识库
    _register_if_new(r, db)
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
        raw_data=json.dumps(ai, ensure_ascii=False),
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
    # 校验文本大小
    text_bytes = data.content.encode("utf-8")
    if len(text_bytes) > MAX_TEXT_SIZE:
        return fail(400, f"文本内容超过限制（最大 {MAX_TEXT_SIZE // 1024}KB）")

    file_id = uuid.uuid4().hex[:12]
    file_name = f"{data.title}.txt"

    try:
        ai = recognition_service.recognize_text(
            data.content,
            file_id,
            file_name,
            _now(),
        )
    except Exception as e:
        err_text = str(e)
        if err_text == "非传统文化":
            return fail(500, "AI文本识别失败\n非传统文化")
        return fail(500, f"AI文本识别失败：{err_text}")

    r = ai.get("result", {})
    _register_if_new(r, db)
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
        raw_data=json.dumps(ai, ensure_ascii=False),
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return success(resource.to_dict(), "识别完成")