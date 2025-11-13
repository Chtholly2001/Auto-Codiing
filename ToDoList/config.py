# project_generator/config.py
import os
import re

# ================= 配置 =================
# 推荐把 API KEY 放到环境变量 DEEPSEEK_API_KEY
DEEPSEEK_API_KEY = "sk-6572f61cfd644e039072109240b19529"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

OUTPUT_DIR = "generated_project"

# 接口文档目录与文件
IFACE_DIR = os.path.join(OUTPUT_DIR, "interface_doc")
IFACE_MD = os.path.join(IFACE_DIR, "INTERFACE_DOC.md")
IFACE_META = os.path.join(IFACE_DIR, "metadata.json")
RAG_INDEX = os.path.join(IFACE_DIR, "rag_index.json")

# Flashphoto快照配置
FLASH_PHOTO_DIR = os.path.join(OUTPUT_DIR, "flashphoto")
FLASH_PHOTO_FILE = os.path.join(FLASH_PHOTO_DIR, "flashphoto_snapshot.md")
FLASH_PHOTO_META = os.path.join(FLASH_PHOTO_DIR, "flashphoto_meta.json")

# 分块备用参数（未使用向量检索，仅作工具参数）
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MAX_PROMPT_FILE_CHARS = 4000  # 发送到模型的每个文件内容上限（防止超长）

# =============== 正则与格式 ===============
FILE_BLOCK_RE = re.compile(r"---FILE:\s*(?P<path>[^\n]+)\n(?P<content>.*?)\n---END_FILE---", re.DOTALL)
