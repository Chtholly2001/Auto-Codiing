# project_generator/utils/api_client.py
import requests
import json
# 将现有的相对导入改为：
from ToDoList.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL

def call_deepseek(prompt: str) -> str:
    """调用 DeepSeek，并在发生错误时提供调试信息。"""
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY.startswith("sk-REPLACE"):
        raise RuntimeError("未配置 DEEPSEEK_API_KEY。请在环境变量中设置 DEEPSEEK_API_KEY。")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=180)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"请求失败（网络/连接错误）：{e}")

    if resp.status_code == 401:
        body = resp.text[:2000]
        raise RuntimeError(
            "API 返回 401 Unauthorized。请检查 DEEPSEEK_API_KEY 是否正确。\n"
            f"请求 URL: {DEEPSEEK_API_URL}\n响应体（前2000字符）:\n{body}"
        )

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        body = resp.text[:2000]
        raise RuntimeError(f"HTTP 错误：{e}\n响应体（前2000字符）：\n{body}")

    # 尝试解析 JSON
    try:
        rj = resp.json()
    except ValueError:
        # 返回不是 JSON，直接返回文本供后续解析
        return resp.text

    # 兼容不同返回结构
    if isinstance(rj, dict) and "choices" in rj and isinstance(rj["choices"], list) and rj["choices"]:
        return rj["choices"][0].get("message", {}).get("content", "")
    if isinstance(rj, dict) and "result" in rj:
        return rj["result"]
    return json.dumps(rj, ensure_ascii=False)