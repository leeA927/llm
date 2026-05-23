import os
import uuid
import json
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import agent
import memory

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

API_KEY = os.getenv('API_KEY', 'ms-c82ae55c-bd9a-4d3f-8c16-d1947bfb725e')
MODEL_BASE_URL = 'https://api-inference.modelscope.cn/v1'
MODEL_NAME = 'Qwen/Qwen3-235B-A22B-Instruct-2507'

client = None
if OPENAI_AVAILABLE:
    client = OpenAI(
        base_url=MODEL_BASE_URL,
        api_key=API_KEY
    )

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    api_key: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_used: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    tools: dict
    version: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    await memory.init_db()
    yield

app = FastAPI(
    title="智能体 API",
    description="具有记忆和工具调用能力的智能助手",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_api_key(api_key: Optional[str]) -> bool:
    if api_key is None:
        return False
    return api_key == API_KEY

def call_llm(messages: list) -> str:
    if not OPENAI_AVAILABLE or client is None:
        return None
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=False,
            max_tokens=1024,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM 调用失败: {str(e)}")
        return None

def generate_response(user_input: str, history: list) -> tuple:
    tool_match = agent.registry.match_tool(user_input)

    if tool_match:
        tool_name, params = tool_match
        tool = agent.registry.get_tool(tool_name)
        if tool:
            result = tool.execute(**params)
            return f"{result}", tool_name

    messages = [
        {'role': 'system', 'content': '你是一个乐于助人的智能助手。'}
    ]
    
    for msg in history[-10:]:
        role = 'user' if msg['role'] == 'user' else 'assistant'
        messages.append({'role': role, 'content': msg['content']})
    
    messages.append({'role': 'user', 'content': user_input})
    
    response_text = call_llm(messages)
    
    if response_text is not None:
        return response_text, None
    
    fallback_responses = {
        'hello': '你好！很高兴见到你！有什么我可以帮助你的吗？',
        'hi': '你好！我是智能助手，随时为你服务！',
        '你好': '你好！请问有什么可以帮助你的？',
        '谢谢': '不客气！能帮到你我很高兴！',
        '谢谢啦': '不用谢！有需要随时找我！',
        '再见': '再见！祝你有美好的一天！',
        '拜拜': '拜拜！下次见！',
        '你是谁': '我是一个由 Python 构建的智能助手，可以帮你查询天气、计算数学题、获取时间等。',
        '你叫什么名字': '你可以叫我智能助手！',
        '你会什么': '我可以帮你查询天气、计算数学题、获取当前时间，还能和你聊天！',
        '帮助': '我可以帮你：\n- 查询天气（如：北京天气）\n- 计算数学题（如：25*17等于多少）\n- 获取当前时间（如：现在几点）\n- 或者和你聊天！',
    }
    
    user_lower = user_input.lower()
    for key, response in fallback_responses.items():
        if key in user_lower:
            return response, None
    
    history_context = ""
    if history:
        history_context = "（根据历史对话）"
    
    import random
    responses = [
        f"我明白了{history_context}。你说的是：{user_input}。还有什么我可以帮你的吗？",
        f"收到{history_context}！关于「{user_input}」这个话题，我很感兴趣！",
        f"你提到了「{user_input}」{history_context}，能告诉我更多细节吗？",
        f"好的{history_context}，我来帮你分析一下「{user_input}」...",
        f"有意思！{user_input}{history_context}，让我想想...",
    ]
    
    return random.choice(responses), None

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not verify_api_key(request.api_key):
        raise HTTPException(status_code=401, detail="API密钥无效或未提供")

    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    session_id = request.session_id
    if not session_id:
        session_id = str(uuid.uuid4())

    history = await memory.get_conversation_history(session_id)

    response_text, tool_used = generate_response(request.message, history)

    await memory.add_message(session_id, "user", request.message, None)
    await memory.add_message(session_id, "assistant", response_text, tool_used)

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        tool_used=tool_used
    )

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        tools=agent.registry.list_tools(),
        version="1.0.0"
    )

@app.get("/session/{session_id}/history")
async def get_history(session_id: str):
    history = await memory.get_conversation_history(session_id)
    return {"session_id": session_id, "history": history}

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    await memory.clear_session(session_id)
    return {"message": "会话已清除", "session_id": session_id}

@app.get("/sessions")
async def list_sessions():
    sessions = await memory.get_all_sessions()
    return {"sessions": sessions}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
