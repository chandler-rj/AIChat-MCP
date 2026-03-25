"""
AIChat MCP Server
将AIChat的REST API封装为MCP (Model Context Protocol) 服务器，供Claude、Cursor等AI客户端调用。

## 功能

AI可以通过MCP工具调用你的AIChat服务：
- 创建和管理AI角色用户
- 创建和管理多AI会话
- 启动/停止群聊自动对话
- 搜索历史著名论战作为对话素材

## 认证配置（3种方式，择一使用）

1. **API Key（推荐）**：在AIChat网页端生成API Key后配置
   - 环境变量：AICHAT_API_KEY

2. **用户名密码**：自动登录获取Token
   - 环境变量：AICHAT_USERNAME + AICHAT_PASSWORD

3. **直接Token**：使用已有的Access Token
   - 环境变量：AICHAT_ACCESS_TOKEN

## 快速开始

1. 安装依赖：pip install -r requirements.txt
2. 配置认证环境变量
3. 启动服务：python server.py
4. 在AI客户端配置MCP Server连接

## 可用工具 (16个)

账户管理：
- update_account_role: 修改账户角色（USER/ADMIN）

消息控制：
- send_message: 向会话发送消息并获取AI回复

用户管理：
- list_users: 列出所有AI角色用户
- create_user: 创建新的AI角色
- get_user: 根据ID获取用户详情
- get_user_by_name: 根据用户名获取用户详情
- update_user: 更新AI角色信息

会话管理：
- list_sessions: 列出所有会话
- create_session: 创建新会话
- get_session: 获取会话详情和消息历史
- delete_session: 删除会话
- clear_messages: 清空会话消息
- update_session: 更新会话配置

对话控制：
- start_chat: 启动自动对话（多AI轮流回复）
- stop_chat: 停止自动对话

工具：
- update_account_role: 修改账户角色（USER/ADMIN）
- send_message: 向会话发送消息并获取AI回复
- search_famous_debates: 搜索历史著名论战

## 使用示例

AI可以自动完成这样的工作流：
1. 搜索"物理"相关的历史论战
2. 创建"牛顿"和"爱因斯坦"两个AI角色
3. 创建一个关于量子力学的会话
4. 启动自动对话，让两个AI展开讨论
"""

import asyncio
import json
import os
import sys
import threading
import time
from typing import Any, Optional

import requests
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server


# ============== 配置 ==============
BASE_URL = os.environ.get("AICHAT_BASE_URL", "http://localhost:8080/api")

# 认证配置（3种方式，优先级：API Key > Username/Password > Access Token）
API_KEY = os.environ.get("AICHAT_API_KEY")
ACCESS_TOKEN = os.environ.get("AICHAT_ACCESS_TOKEN")
USERNAME = os.environ.get("AICHAT_USERNAME")
PASSWORD = os.environ.get("AICHAT_PASSWORD")

# Token缓存
_token_lock = threading.Lock()
_cached_token: Optional[str] = None
_token_expiry: float = 0


# ============== MCP Server ==============
app = Server("aichat-mcp")


def _refresh_token() -> Optional[str]:
    """刷新访问令牌（自动选择最优认证方式）"""
    global _cached_token, _token_expiry

    with _token_lock:
        # 缓存有效则直接返回
        if _cached_token and time.time() < _token_expiry - 60:
            return _cached_token

        # 方式1: API Key认证（推荐）
        if API_KEY:
            try:
                resp = requests.post(
                    f"{BASE_URL}/auth/login-by-api-key",
                    json={"apiKey": API_KEY},
                    timeout=10
                )
                resp.raise_for_status()
                data = resp.json()
                _cached_token = data.get("accessToken")
                _token_expiry = time.time() + (data.get("expiresIn", 1800) * 0.9)
                return _cached_token
            except Exception as e:
                print(f"[认证] API Key登录失败: {e}", file=sys.stderr)

        # 方式2: 用户名密码认证
        elif USERNAME and PASSWORD:
            try:
                resp = requests.post(
                    f"{BASE_URL}/auth/login",
                    json={"username": USERNAME, "password": PASSWORD},
                    timeout=10
                )
                resp.raise_for_status()
                data = resp.json()
                _cached_token = data.get("accessToken")
                _token_expiry = time.time() + (data.get("expiresIn", 1800) * 0.9)
                return _cached_token
            except Exception as e:
                print(f"[认证] 用户名密码登录失败: {e}", file=sys.stderr)

        # 方式3: 直接使用Access Token
        elif ACCESS_TOKEN:
            _cached_token = ACCESS_TOKEN
            _token_expiry = time.time() + 3600
            return _cached_token

        print("[认证] 未配置任何认证方式，请设置 AICHAT_API_KEY 或 AICHAT_USERNAME/AICHAT_PASSWORD", file=sys.stderr)
        return None


def _get_auth_header() -> dict:
    """获取认证头"""
    token = _refresh_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def make_request(method: str, endpoint: str, data: dict = None, require_auth: bool = True) -> Any:
    """发送请求到AIChat后端"""
    url = f"{BASE_URL}{endpoint}"
    headers = _get_auth_header() if require_auth else {}

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            resp = requests.post(url, json=data, headers=headers, timeout=30)
        elif method == "PUT":
            resp = requests.put(url, json=data, headers=headers, timeout=30)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=30)
        else:
            return {"error": f"不支持的请求方法: {method}"}

        resp.raise_for_status()
        return resp.json() if resp.content else {}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# ============== 工具列表 ==============
@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用的MCP工具"""
    return [
        # ========== 用户管理 ==========
        Tool(
            name="list_users",
            description="列出当前账户下的所有AI角色用户。返回用户ID、名称、显示名称、模型类型等信息。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="create_user",
            description="创建一个新的AI角色用户。需要指定用户名（唯一标识）、模型类型和角色设定。可选设置显示名称、角色提示词等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "用户名，系统内部唯一标识，如 newton, einstein, confucius"
                    },
                    "displayName": {
                        "type": "string",
                        "description": "显示名称，展示给用户看的名字，如 艾萨克·牛顿"
                    },
                    "modelType": {
                        "type": "string",
                        "description": "模型类型，决定AI用什么大模型，可选: QWEN(阿里通义), MINIMAX, GEMINI(谷歌), VOLCANO(字节)"
                    },
                    "rolePrompt": {
                        "type": "string",
                        "description": "角色设定prompt，描述AI角色的性格、背景、专业领域、说话风格等。例如：'你是艾萨克·牛顿，英国物理学家，以严厉和固执著称...'"
                    },
                    "isHuman": {
                        "type": "boolean",
                        "description": "是否是人类角色（默认为false）。设为true时该角色由真人控制而非AI。"
                    }
                },
                "required": ["name", "modelType"]
            }
        ),
        Tool(
            name="get_user",
            description="根据用户ID获取单个AI角色的详细信息，包括其角色设定、使用的模型等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "userId": {
                        "type": "number",
                        "description": "用户ID，从list_users或create_user响应中获取"
                    }
                },
                "required": ["userId"]
            }
        ),
        Tool(
            name="get_user_by_name",
            description="根据用户名（唯一标识）查找AI角色信息。如果用户不存在返回错误。",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "用户名（系统内部标识），如 newton, einstein"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="update_user",
            description="更新AI角色的信息。可以修改显示名称、角色设定、模型类型等。用于调整AI角色的性格、背景或切换使用的模型。",
            inputSchema={
                "type": "object",
                "properties": {
                    "userId": {
                        "type": "number",
                        "description": "用户ID，从list_users或create_user响应中获取"
                    },
                    "displayName": {
                        "type": "string",
                        "description": "显示名称，展示给用户看的名字，如 艾萨克·牛顿"
                    },
                    "rolePrompt": {
                        "type": "string",
                        "description": "角色设定prompt，描述AI角色的性格、背景、专业领域、说话风格等。"
                    },
                    "modelType": {
                        "type": "string",
                        "description": "模型类型，决定AI用什么大模型，可选: QWEN(阿里通义), MINIMAX, GEMINI(谷歌), VOLCANO(字节)"
                    }
                },
                "required": ["userId"]
            }
        ),

        # ========== 会话管理 ==========
        Tool(
            name="list_sessions",
            description="列出当前账户下的所有会话。按最后更新时间排序，最新修改的在前。每个会话包含ID、名称、主题、参与用户等信息。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="create_session",
            description="创建一个新的多AI对话会话。可以设置会话名称、主题、参与者、回复间隔等参数。",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "会话名称，如 '牛顿vs胡克万有引力之争'"
                    },
                    "sessionTheme": {
                        "type": "string",
                        "description": "会话主题/背景设定，描述对话发生的场景和目的。例如：'讨论谁更早发现万有引力定律'。"
                    },
                    "chatRules": {
                        "type": "string",
                        "description": "聊天规则，可选。例如：'每轮对话不超过50字'、'必须用中文回复'。"
                    },
                    "userConfig": {
                        "type": "string",
                        "description": "参与者用户ID列表，字符串格式如 '1,2,3'。需要先通过create_user创建用户。"
                    },
                    "replyInterval": {
                        "type": "number",
                        "description": "AI回复间隔，单位毫秒。太小可能导致API限流，建议2000-5000。默认2000。"
                    },
                    "maxHistoryMessages": {
                        "type": "number",
                        "description": "最大历史消息数，控制LLM的上下文大小。较大值提供更多上下文但消耗更多token。默认5。"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="get_session",
            description="获取会话的详细信息，包括所有消息历史、参与者列表、会话状态等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sessionId": {
                        "type": "number",
                        "description": "会话ID，从list_sessions响应中获取"
                    }
                },
                "required": ["sessionId"]
            }
        ),
        Tool(
            name="delete_session",
            description="删除一个会话及其所有消息历史。此操作不可恢复，请确认后再执行。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sessionId": {
                        "type": "number",
                        "description": "要删除的会话ID"
                    }
                },
                "required": ["sessionId"]
            }
        ),
        Tool(
            name="clear_messages",
            description="清空会话的所有消息历史，但保留会话本身（名称、主题、参与者等不变）。用于开始新的对话话题。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sessionId": {
                        "type": "number",
                        "description": "会话ID"
                    }
                },
                "required": ["sessionId"]
            }
        ),
        Tool(
            name="update_session",
            description="更新会话的配置信息。可以修改会话名称、主题、聊天规则、参与者等。用于调整会话的设置和参与者。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sessionId": {
                        "type": "number",
                        "description": "会话ID，从list_sessions或create_session响应中获取"
                    },
                    "name": {
                        "type": "string",
                        "description": "会话名称，如 '牛顿vs胡克万有引力之争'"
                    },
                    "sessionTheme": {
                        "type": "string",
                        "description": "会话主题/背景设定，描述对话发生的场景和目的。"
                    },
                    "chatRules": {
                        "type": "string",
                        "description": "聊天规则，如 '每轮对话不超过50字'、'必须用中文回复'。"
                    },
                    "userConfig": {
                        "type": "string",
                        "description": "参与者用户ID列表，字符串格式如 '1,2,3'。"
                    },
                    "replyInterval": {
                        "type": "number",
                        "description": "AI回复间隔，单位毫秒，建议2000-5000。"
                    }
                },
                "required": ["sessionId"]
            }
        ),

        # ========== 对话控制 ==========
        Tool(
            name="start_chat",
            description="启动会话的自动对话模式。已配置的AI角色会按照顺序轮流自动回复，形成多AI群聊效果。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sessionId": {
                        "type": "number",
                        "description": "会话ID，需要确保会话已有参与者"
                    }
                },
                "required": ["sessionId"]
            }
        ),
        Tool(
            name="stop_chat",
            description="停止会话的自动对话模式。对话会暂停，AI不再自动回复。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sessionId": {
                        "type": "number",
                        "description": "会话ID"
                    }
                },
                "required": ["sessionId"]
            }
        ),

        # ========== 工具 ==========
        Tool(
            name="search_famous_debates",
            description="搜索预设的历史著名学术论战和争论。可用于获取创建历史人物对话的素材和背景信息。返回论战名称、参与人物、时间、背景描述等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，可以是论战名称、参与者名字或领域关键词。例如：'物理'、'牛顿'、'量子力学'。"
                    },
                    "limit": {
                        "type": "number",
                        "description": "返回结果数量上限，默认5条。"
                    }
                },
                "required": ["query"]
            }
        ),

        # ========== 账户管理 ==========
        Tool(
            name="update_account_role",
            description="修改用户的账户角色（需要管理员权限）。可以将普通用户升级为管理员，或将管理员降级为普通用户。",
            inputSchema={
                "type": "object",
                "properties": {
                    "accountId": {
                        "type": "number",
                        "description": "账户ID，从list_accounts或管理员面板获取"
                    },
                    "role": {
                        "type": "string",
                        "description": "新角色，可选值: USER（普通用户）, ADMIN（管理员）"
                    }
                },
                "required": ["accountId", "role"]
            }
        ),

        # ========== 消息控制 ==========
        Tool(
            name="send_message",
            description="向会话发送一条消息，获取指定AI角色的回复。这用于手动触发单次对话，而非自动群聊。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sessionId": {
                        "type": "number",
                        "description": "会话ID"
                    },
                    "content": {
                        "type": "string",
                        "description": "消息内容，要发送给AI的文字"
                    },
                    "userId": {
                        "type": "number",
                        "description": "发送消息的用户ID（AI角色），从list_users获取。如果不传则使用会话中第一个参与者。"
                    },
                    "modelType": {
                        "type": "string",
                        "description": "使用的模型类型，可选: QWEN, MINIMAX, GEMINI, VOLCANO, OPENAI。如果不传则使用用户默认模型。"
                    }
                },
                "required": ["sessionId", "content"]
            }
        )
    ]


# ============== 工具实现 ==============
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """执行MCP工具调用"""
    result = None

    try:
        if name == "list_users":
            result = make_request("GET", "/users")

        elif name == "create_user":
            result = make_request("POST", "/users", arguments)

        elif name == "get_user":
            user_id = arguments.get("userId")
            result = make_request("GET", f"/users/{user_id}")

        elif name == "get_user_by_name":
            user_name = arguments.get("name")
            result = make_request("GET", f"/users/by-name/{user_name}")

        elif name == "update_user":
            user_id = arguments.get("userId")
            # 只发送需要更新的字段
            update_data = {}
            if "displayName" in arguments:
                update_data["displayName"] = arguments["displayName"]
            if "rolePrompt" in arguments:
                update_data["rolePrompt"] = arguments["rolePrompt"]
            if "modelType" in arguments:
                update_data["modelType"] = arguments["modelType"]
            result = make_request("PUT", f"/users/{user_id}", update_data)

        elif name == "list_sessions":
            result = make_request("GET", "/sessions")

        elif name == "create_session":
            result = make_request("POST", "/sessions", arguments)

        elif name == "get_session":
            session_id = arguments.get("sessionId")
            result = make_request("GET", f"/sessions/{session_id}")

        elif name == "delete_session":
            session_id = arguments.get("sessionId")
            result = make_request("DELETE", f"/sessions/{session_id}")

        elif name == "clear_messages":
            session_id = arguments.get("sessionId")
            result = make_request("DELETE", f"/sessions/{session_id}/messages")

        elif name == "update_session":
            session_id = arguments.get("sessionId")
            # 只发送需要更新的字段
            update_data = {}
            if "name" in arguments:
                update_data["name"] = arguments["name"]
            if "sessionTheme" in arguments:
                update_data["sessionTheme"] = arguments["sessionTheme"]
            if "chatRules" in arguments:
                update_data["chatRules"] = arguments["chatRules"]
            if "userConfig" in arguments:
                update_data["userConfig"] = arguments["userConfig"]
            if "replyInterval" in arguments:
                update_data["replyInterval"] = arguments["replyInterval"]
            result = make_request("PUT", f"/sessions/{session_id}", update_data)

        elif name == "start_chat":
            session_id = arguments.get("sessionId")
            result = make_request("POST", f"/sessions/{session_id}/start")

        elif name == "stop_chat":
            session_id = arguments.get("sessionId")
            result = make_request("POST", f"/sessions/{session_id}/stop")

        elif name == "search_famous_debates":
            result = search_famous_debates(arguments.get("query", ""), arguments.get("limit", 5))

        elif name == "update_account_role":
            account_id = arguments.get("accountId")
            role = arguments.get("role")
            if role not in ["USER", "ADMIN"]:
                result = {"error": "role必须是USER或ADMIN"}
            else:
                update_data = {"role": role}
                result = make_request("PUT", f"/admin/accounts/{account_id}", update_data)

        elif name == "send_message":
            session_id = arguments.get("sessionId")
            content = arguments.get("content")
            user_id = arguments.get("userId")
            model_type = arguments.get("modelType")

            # 构建请求数据
            msg_data = {"content": content}
            if user_id:
                msg_data["userId"] = user_id
            if model_type:
                msg_data["modelType"] = model_type

            result = make_request("POST", f"/sessions/{session_id}/send", msg_data)

        else:
            result = {"error": f"未知工具: {name}"}

    except Exception as e:
        result = {"error": str(e)}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


def search_famous_debates(query: str, limit: int = 5) -> dict:
    """搜索历史著名论战（内置知识库）"""
    debates = [
        {
            "id": 1,
            "name": "牛顿 vs 胡克 - 万有引力优先权之争",
            "participants": ["牛顿", "胡克"],
            "time": "1680年代",
            "description": "关于万有引力定律发明权的著名争论，胡克声称自己先发现了引力与距离平方成反比的规律。",
            "background": "胡克在1679年给牛顿写信提出了引力与距离平方成反比的想法，牛顿在1687年《自然哲学的数学原理》中发表了万有引力定律。两人因此发生了著名的优先权争论。"
        },
        {
            "id": 2,
            "name": "爱因斯坦 vs 玻尔 - 量子力学完备性争论",
            "participants": ["爱因斯坦", "玻尔"],
            "time": "1927-1935",
            "description": "关于量子力学完备性和测不准原理的世纪辩论，持续了数十年。",
            "background": "爱因斯坦不相信'上帝掷骰子'，认为量子力学是不完备的。玻尔则坚持量子力学的哥本哈根解释。这场辩论产生了著名的EPR悖论。"
        },
        {
            "id": 3,
            "name": "达尔文 vs 欧文 - 进化论与创世论",
            "participants": ["达尔文", "欧文"],
            "time": "1860年代",
            "description": "关于物种起源和进化论的著名辩论，牛津大学1860年辩论是其高潮。",
            "background": "欧文是英国皇家学会会长，坚决反对达尔文的进化论。这场辩论是科学史上的重要里程碑。"
        },
        {
            "id": 4,
            "name": "莱布尼茨 vs 牛顿 - 微积分发明权之争",
            "participants": ["莱布尼茨", "牛顿"],
            "time": "1700年代",
            "description": "关于微积分发明权的著名争论，两位数学巨匠的追随者互相指责对方抄袭。",
            "background": "牛顿声称自己先发明了微积分，但莱布尼茨先发表了论文。两国数学家互相攻击，损害了英德两国数学界的交流。"
        },
        {
            "id": 5,
            "name": "托马斯·赫胥黎 vs 威尔伯福斯 - 达尔文主义辩论",
            "participants": ["赫胥黎", "威尔伯福斯"],
            "time": "1860年",
            "description": "牛津大学著名的进化论辩论，赫胥黎被称为'达尔文的斗牛犬'。",
            "background": "1860年英国科学协会牛津会议上，主教威尔伯福斯攻击进化论，赫胥黎进行了有力反驳。这是科学vs宗教的经典对决。"
        },
        {
            "id": 6,
            "name": "薛定谔 vs 爱因斯坦 - 量子物理哲学争论",
            "participants": ["薛定谔", "爱因斯坦"],
            "time": "1935年",
            "description": "关于量子力学诠释的哲学争论，产生了著名的薛定谔猫思想实验。",
            "background": "薛定谔和爱因斯坦都对量子力学的概率解释不满意。薛定谔提出了'薛定谔的猫'思想实验来质疑量子力学的完备性。"
        },
        {
            "id": 7,
            "name": "费曼 vs 狄拉克 - 量子电动力学诠释",
            "participants": ["费曼", "狄拉克"],
            "time": "1940年代",
            "description": "关于量子电动力学(QED)和路径积分的争论。",
            "background": "费曼发展了独特的路径积分方法，与狄拉克等人的诠释产生了激烈讨论。"
        },
        {
            "id": 8,
            "name": "乔姆斯基 vs 斯金纳 - 语言学与行为主义",
            "participants": ["乔姆斯基", "斯金纳"],
            "time": "1957年",
            "description": "关于语言习得和认知的著名争论，彻底改变了语言学方向。",
            "background": "乔姆斯基批评斯金纳的《言语行为》，认为语言能力是先天的，行为主义无法解释语言习得。这场辩论奠定了认知语言学的基础。"
        },
        {
            "id": 9,
            "name": "皮亚杰 vs 维果茨基 - 发展心理学",
            "participants": ["皮亚杰", "维果茨基"],
            "time": "1930-1960年代",
            "description": "关于儿童认知发展的两种理论体系的争论。",
            "background": "皮亚杰认为认知发展是阶段性的，而维果茨基强调社会文化因素。两种理论至今仍影响着教育心理学。"
        },
        {
            "id": 10,
            "name": "杨振宁 vs 其他物理学家 - 宇称不守恒",
            "participants": ["杨振宁", "李政道"],
            "time": "1956-1957年",
            "description": "关于弱相互作用中宇称不守恒的发现之争，两位中国物理学家因此获得诺贝尔奖。",
            "background": "杨振宁和李政道提出弱相互作用中宇称不守恒的假设，被吴健雄实验证实。这打碎了物理学中的对称性信仰。"
        },
        {
            "id": 11,
            "name": "玻尔 vs 爱因斯坦 - 光本质争论",
            "participants": ["玻尔", "爱因斯坦"],
            "time": "1920-1930年代",
            "description": "关于光的波粒二象性的著名争论，涉及量子力学的基础。",
            "background": "爱因斯坦坚持光的粒子说，玻尔则用互补原理解释光的波粒二象性。两人的争论深刻影响了量子力学的发展。"
        },
        {
            "id": 12,
            "name": "苏格拉底 vs 智者派 - 哲学方法论",
            "participants": ["苏格拉底", "智者派"],
            "time": "公元前5世纪",
            "description": "古希腊关于真理和辩论方法的哲学争论。",
            "background": "智者派主张相对主义和修辞术，苏格拉底则坚持真理和辩证法。这场争论奠定了西方哲学的方法论基础。"
        }
    ]

    # 搜索过滤
    if query:
        query_lower = query.lower()
        filtered = [
            d for d in debates
            if query_lower in d["name"].lower()
            or query_lower in d["description"].lower()
            or query_lower in d["background"].lower()
            or any(query_lower in p.lower() for p in d["participants"])
        ]
    else:
        filtered = debates

    return {
        "total": len(filtered),
        "limit": limit,
        "debates": filtered[:limit]
    }


# ============== 启动服务 ==============
async def main():
    """启动MCP Server"""
    print("=" * 50, file=sys.stderr)
    print("AIChat MCP Server 启动中...", file=sys.stderr)
    print(f"后端地址: {BASE_URL}", file=sys.stderr)

    if API_KEY:
        print("认证方式: API Key", file=sys.stderr)
    elif USERNAME:
        print("认证方式: 用户名密码", file=sys.stderr)
    elif ACCESS_TOKEN:
        print("认证方式: Access Token", file=sys.stderr)
    else:
        print("警告: 未配置任何认证方式!", file=sys.stderr)

    print("=" * 50, file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
