"""
AI 识别服务 — 仅使用千问API，无降级模拟
调用千问NLP / VL API进行识别，API失败直接抛出异常，无本地规则模拟
仅依赖 requests，不依赖任何本地模型
"""
import requests
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
import time
from ..config import DASHSCOPE_API_KEY, NLP_MODEL, VL_MODEL

# ── 动态获取朝代和作者列表的函数 ──
# 后续由 upload.py 在识别完成后调用 register 方法自动扩充

def get_dynasty_names(db_session=None) -> list:
    """获取数据库中所有朝代名称，DB不可用时返回空列表"""
    if db_session is None:
        return []
    try:
        from sqlalchemy import select
        from ..models import Dynasty as D
        rows = db_session.execute(select(D.name)).scalars().all()
        return list(rows)
    except Exception:
        return []


def get_author_names(db_session=None) -> list:
    """获取数据库中所有作者名称，DB不可用时返回空列表"""
    if db_session is None:
        return []
    try:
        from sqlalchemy import select
        from ..models import Author as A
        rows = db_session.execute(select(A.name)).scalars().all()
        return list(rows)
    except Exception:
        return []


def register_dynasty(name: str, db_session) -> bool:
    """注册一个新朝代（幂等）"""
    if not name or not db_session:
        return False
    try:
        from sqlalchemy import select
        from ..models import Dynasty as D
        existing = db_session.execute(select(D).where(D.name == name)).scalar()
        if not existing:
            db_session.add(D(name=name))
            db_session.commit()
            print(f'[Knowledge] 新增朝代: {name}')
        return True
    except Exception as e:
        print(f'[Knowledge] 注册朝代失败: {e}')
        return False


def register_author(name: str, dynasty: str = None, db_session=None) -> bool:
    """注册一个新作者（幂等）"""
    if not name or not db_session:
        return False
    try:
        from sqlalchemy import select
        from ..models import Author as A
        existing = db_session.execute(select(A).where(A.name == name)).scalar()
        if not existing:
            db_session.add(A(name=name, dynasty=dynasty))
            db_session.commit()
            print(f'[Knowledge] 新增作者: {name}（{dynasty}）')
        return True
    except Exception as e:
        print(f'[Knowledge] 注册作者失败: {e}')
        return False

# 重试配置
MAX_RETRIES = 2
RETRY_DELAY = 1  # 秒


def _valid_key() -> bool:
    """检查 API Key 是否可用于 HTTP 请求"""
    try:
        return bool(DASHSCOPE_API_KEY) and len(DASHSCOPE_API_KEY) > 10
    except:
        return False


def _request_with_retry(url: str, headers: Dict, data: Dict, timeout: int = 30) -> Optional[Dict]:
    """
    带重试机制的HTTP请求
    修复点：将入参data直接传给requests.post的json参数，兼容原有调用传参
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=timeout)
            resp.raise_for_status()  # 抛出HTTP错误
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"[请求失败] 第 {attempt + 1} 次尝试失败: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise Exception(f"千问API请求全部重试失败: {str(e)}")


def _clean_json_content(raw_text: str) -> str:
    """
    逐层剥离千问双层嵌套：外层{"text":"xxx"} → 剥离markdown代码块 → 提取纯业务JSON
    """
    temp = raw_text.strip()

    # 第一层：剥离外层 {"text": "实际内容"} 包裹
    try:
        outer = json.loads(temp.replace("'", '"'))
        if isinstance(outer, dict) and "text" in outer:
            temp = outer["text"]
    except json.JSONDecodeError:
        pass

    # 第二层：移除 ```json / ``` 标记、多余换行空格
    temp = re.sub(r'```(json)?', '', temp)
    temp = temp.strip()

    # 第三层：截取 { ... } 纯业务JSON主体
    start_idx = temp.find("{")
    end_idx = temp.rfind("}")
    if start_idx == -1 or end_idx == -1:
        return ""
    json_body = temp[start_idx:end_idx + 1]

    # 兼容单引号转标准双引号
    json_body = json_body.replace("'", '"')
    return json_body


# ═══════════════════════════
# 图像识别（千问VL模型适配）
# ═══════════════════════════
def recognize_image(file_path: str, file_name: str, file_size: int, file_id: str, recognition_time: str) -> Dict[str, Any]:
    """
    图像识别 — 仅调用千问VL API，无降级逻辑，API失败直接抛出异常
    新增：非文物识别后主动抛出"非文物"异常
    """
    # 基础返回结构
    result = {
        "id": file_id,
        "fileName": file_name,
        "fileType": "image",
        "fileUrl": f"/uploads/{file_id}",
        "fileSize": file_size,
        "recognitionTime": recognition_time,
        "rawData": {"content": ""},
        "result": {}
    }

    if not _valid_key():
        raise Exception("DASHSCOPE_API_KEY 未配置或无效，无法调用千问API")

    import base64
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    # 提示词：强制纯净JSON，禁止外层嵌套、代码块
    prompt = """
只输出纯净JSON字符串，禁止外层包裹{"text":...}、禁止```markdown代码块、禁止任何注释多余文字。
若图片不属于文物、古画、古籍、传统器物、书法、石窟壁画等传统文化藏品：
description固定填写「图片未识别到文物」，tags使用["普通图片","非文物"]，dynasty填现代。
严格仅输出以下JSON，无任何附加内容：
{
    "title": "图片标题",
    "author": "作者（无则填佚名）",
    "dynasty": "朝代",
    "description": "300字以内描述，非文物固定填：图片未识别到文物",
    "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"],
    "confidence": 0.95,
    "content": null
}
"""

    # 千问VL调用
    resp_data = _request_with_retry(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}", "Content-Type": "application/json"},
        data={
            "model": VL_MODEL,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{b64}"},
                        {"text": prompt}
                    ]
                }]
            },
            "parameters": {
                "top_p": 0.8,
                "temperature": 0.7,
                "max_tokens": 800,
                "result_format": "json"
            }
        },
        timeout=30
    )

    # 解析API响应
    if resp_data and "output" in resp_data and resp_data["output"].get("choices"):
        choice = resp_data["output"]["choices"][0]
        msg_content = choice.get("message", {}).get("content", "")

        # 兼容list格式content → 直接提取 text 字段
        if isinstance(msg_content, list):
            texts = []
            for item in msg_content:
                if isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
                elif isinstance(item, str):
                    texts.append(item)
            content = "\n".join(texts)
        else:
            content = msg_content.strip()

        if content:
            json_str = _clean_json_content(content)
            if not json_str:
                raise Exception("千问VL未输出有效JSON")
            try:
                ai_result = json.loads(json_str)
                # 校验必填字段
                required_fields = ["title", "author", "dynasty", "description", "tags", "confidence"]
                for field in required_fields:
                    if field not in ai_result:
                        raise Exception(f"千问返回JSON缺失字段: {field}")
                ai_result["confidence"] = float(ai_result.get("confidence"))
                ai_result["content"] = None

                # 检测非文物标签，拒绝入库
                if "非文物" in (ai_result.get("tags") or []):
                    raise Exception("非文物")

                result["result"] = ai_result
                return result
            except json.JSONDecodeError as e:
                raise Exception(f"{str(e)}\n清洗后JSON片段：{json_str[:300]}")

    raise Exception("千问VL返回数据格式异常，无有效识别结果")


# ═══════════════════════════
# 文本识别（千问Plus模型适配）
# ═══════════════════════════
def recognize_text(content: str, file_id: str, file_name: str, recognition_time: str) -> Dict[str, Any]:
    """
    文本分析 — 仅调用千问Plus API，无降级逻辑
    """
    result = {
        "id": file_id,
        "fileName": file_name,
        "fileType": "text",
        "fileUrl": "",
        "fileSize": len(content.encode('utf-8')),
        "recognitionTime": recognition_time,
        "rawData": {"content": content},
        "result": {}
    }

    if not _valid_key():
        raise Exception("DASHSCOPE_API_KEY 未配置或无效，无法调用千问API")

    prompt = f"""
只输出纯净JSON，禁止外层{{"text":}}、禁止```代码块，无多余文字。
若文本不属于诗词歌赋、古文典籍、经史子集、戏曲小说、传统技艺、民俗礼仪、中医中药、书画篆刻、传统建筑、传统服饰、神话传说等传统文化相关内容：
description固定填写「文本未识别到传统文化内容」，tags使用["普通文本","非传统文化"]，dynasty填现代。
文本内容：{content[:500]}
输出格式：
{{
    "title": "文本标题（不超30字）",
    "author": "作者无则填佚名",
    "dynasty": "朝代",
    "description": "文本分析描述，非传统文化固定填：文本未识别到传统文化内容",
    "tags": ["标签1","标签2","标签3","标签4","标签5"],
    "content": "{content[:1000]}",
    "confidence": 0.95
}}"""

    resp_data = _request_with_retry(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}", "Content-Type": "application/json"},
        data={
            "model": NLP_MODEL,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": prompt
                }]
            },
            "parameters": {
                "result_format": "json",
                "top_p": 0.8,
                "temperature": 0.7,
                "max_tokens": 1500
            }
        },
        timeout=20
    )

    if resp_data and "output" in resp_data and resp_data["output"].get("choices"):
        choice = resp_data["output"]["choices"][0]
        msg_content = choice.get("message", {}).get("content", "").strip()

        if msg_content and "{" in msg_content:
            json_str = _clean_json_content(msg_content)
            if not json_str:
                raise Exception("千问NLP未输出有效JSON")
            try:
                ai_result = json.loads(json_str)
                required_fields = ["title", "author", "dynasty", "description", "tags", "confidence", "content"]
                for field in required_fields:
                    if field not in ai_result:
                        raise Exception(f"千问返回JSON缺失字段: {field}")
                ai_result["confidence"] = float(ai_result["confidence"])
                ai_result["content"] = ai_result.get("content", content)

                # 检测非传统文化标签，拒绝入库
                if "非传统文化" in (ai_result.get("tags") or []):
                    raise Exception("非传统文化")

                result["result"] = ai_result
                return result
            except json.JSONDecodeError as e:
                raise Exception(f"{str(e)}\n清洗后JSON片段：{json_str[:300]}")

    raise Exception("千问NLP返回数据格式异常，无有效识别结果")