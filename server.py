"""
AIChat MCP Server
将AIChat的REST API封装为MCP工具，供Claude等AI调用

使用方式:
1. 安装依赖: pip install -r requirements.txt
2. 启动服务: python server.py
3. 配置AI客户端连接到 stdio

AI可用工具:
- create_user: 创建AI角色用户
- create_session: 创建新会话
- send_message: 发送消息
- start_chat: 启动自动对话
- stop_chat: 停止对话
- list_users: 列出所有用户
- list_sessions: 列出所有会话
- get_session: 获取会话详情
- delete_session: 删除会话
- clear_messages: 清空会话消息
"""

import asyncio
import json
import os
import sys
from typing import Any

import requests
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server


# ============== 配置 ==============
# AIChat后端API地址
BASE_URL = os.environ.get("AICHAT_BASE_URL", "http://localhost:8080/api")

# ============== MCP Server ==============
app = Server("aichat-mcp")


def make_request(method: str, endpoint: str, data: dict = None) -> Any:
    """发送请求到AIChat后端"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        elif method == "PUT":
            response = requests.put(url, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, timeout=30)
        else:
            return {"error": f"Unsupported method: {method}"}

        response.raise_for_status()
        return response.json() if response.content else {}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# ============== 工具列表 ==============
@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用的工具"""
    return [
        Tool(
            name="list_users",
            description="列出系统中所有的AI角色用户。返回用户ID、名称、显示名称、使用的模型等信息。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="create_user",
            description="创建一个新的AI角色用户。可以设置用户名、显示名称、使用的模型和角色提示词。",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "用户名（系统内部标识），如 newton, einstein"
                    },
                    "displayName": {
                        "type": "string",
                        "description": "显示名称，如 艾萨克·牛顿"
                    },
                    "modelType": {
                        "type": "string",
                        "description": "模型类型，可选值: OPENAI, QWEN, MINIMAX, GEMINI, VOLCANO"
                    },
                    "rolePrompt": {
                        "type": "string",
                        "description": "角色设定prompt，描述这个AI角色的性格、背景、说话风格等"
                    },
                    "isHuman": {
                        "type": "boolean",
                        "description": "是否是人类用户（默认为false）"
                    }
                },
                "required": ["name", "modelType"]
            }
        ),
        Tool(
            name="get_user",
            description="根据ID获取单个用户的详细信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "userId": {
                        "type": "number",
                        "description": "用户ID"
                    }
                },
                "required": ["userId"]
            }
        ),
        Tool(
            name="list_sessions",
            description="列出系统中所有的会话。按更新时间排序，最新的在前。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="create_session",
            description="创建一个新的会话。可以设置会话名称、主题、参与用户等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "会话名称，如 '牛顿vs胡克论战'"
                    },
                    "sessionTheme": {
                        "type": "string",
                        "description": "会话主题/背景设定，描述这个对话的背景和目的"
                    },
                    "chatRules": {
                        "type": "string",
                        "description": "聊天规则，可选，设置对话的基本规则"
                    },
                    "userConfig": {
                        "type": "string",
                        "description": "参与用户配置，JSON格式的用户ID列表，如 '[1,2,3]'"
                    },
                    "replyInterval": {
                        "type": "number",
                        "description": "回复间隔（毫秒），默认2000"
                    },
                    "maxHistoryMessages": {
                        "type": "number",
                        "description": "最大历史消息数，控制LLM上下文大小，默认5"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="get_session",
            description="获取会话详情，包括所有消息历史",
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
            name="send_message",
            description="向会话发送一条消息。可以指定发送者和使用的模型。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sessionId": {
                        "type": "number",
                        "description": "会话ID"
                    },
                    "content": {
                        "type": "string",
                        "description": "消息内容"
                    },
                    "modelType": {
                        "type": "string",
                        "description": "模型类型: OPENAI, QWEN, MINIMAX, GEMINI, VOLCANO"
                    },
                    "userId": {
                        "type": "number",
                        "description": "发送者用户ID（可选）"
                    }
                },
                "required": ["sessionId", "content", "modelType"]
            }
        ),
        Tool(
            name="start_chat",
            description="启动会话的自动对话模式。多个AI角色会自动轮流回复。",
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
            name="stop_chat",
            description="停止会话的自动对话模式",
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
            name="delete_session",
            description="删除一个会话及其所有消息",
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
            name="clear_messages",
            description="清空会话的所有消息，但保留会话",
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
            name="search_famous_debates",
            description="搜索历史上著名的学术论战和争论。可用于创建历史人物对话。返回论战名称、参与者、背景等信息。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如 '物理', '哲学', '数学'"
                    },
                    "limit": {
                        "type": "number",
                        "description": "返回结果数量，默认5"
                    }
                },
                "required": ["query"]
            }
        )
    ]


# ============== 工具实现 ==============
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """执行工具调用"""
    result = None

    try:
        if name == "list_users":
            result = make_request("GET", "/users")

        elif name == "create_user":
            result = make_request("POST", "/users", arguments)

        elif name == "get_user":
            user_id = arguments.get("userId")
            result = make_request("GET", f"/users/{user_id}")

        elif name == "list_sessions":
            result = make_request("GET", "/sessions")

        elif name == "create_session":
            result = make_request("POST", "/sessions", arguments)

        elif name == "get_session":
            session_id = arguments.get("sessionId")
            result = make_request("GET", f"/sessions/{session_id}")

        elif name == "send_message":
            session_id = arguments.pop("sessionId")
            # 构建请求体
            payload = {
                "content": arguments.get("content"),
                "modelType": arguments.get("modelType"),
            }
            if "userId" in arguments:
                payload["userId"] = arguments.get("userId")
            result = make_request("POST", f"/sessions/{session_id}/send", payload)

        elif name == "start_chat":
            session_id = arguments.get("sessionId")
            result = make_request("POST", f"/sessions/{session_id}/start")

        elif name == "stop_chat":
            session_id = arguments.get("sessionId")
            result = make_request("POST", f"/sessions/{session_id}/stop")

        elif name == "delete_session":
            session_id = arguments.get("sessionId")
            result = make_request("DELETE", f"/sessions/{session_id}")

        elif name == "clear_messages":
            session_id = arguments.get("sessionId")
            result = make_request("DELETE", f"/sessions/{session_id}/messages")

        elif name == "search_famous_debates":
            # 这是一个特殊工具，返回预设的历史著名论战列表
            result = search_famous_debates(arguments.get("query", ""), arguments.get("limit", 5))

        else:
            result = {"error": f"Unknown tool: {name}"}

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
            "background": "欧文是英国皇家学会会长，坚决反对达尔文的进化论。这场辩论科学史上的重要里程碑。"
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
            "background": "薛定谔和爱因斯坦都對量子力学的概率解释不满意。薛定谔提出了'薛定谔的猫'思想实验来质疑量子力学的完备性。"
        },
        {
            "id": 7,
            "name": "费曼 vs 其他物理学家 - 量子电动力学诠释",
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
            "name": "中医 vs 西医 - 现代医学争论",
            "participants": ["现代医学派", "传统医学派"],
            "time": "近现代",
            "description": "关于中医有效性和科学性的持续争论。",
            "background": "这场争论涉及阴阳五行vs现代医学、随机双盲试验、中药安全性等众多议题。"
        }
    ]

    # 过滤
    if query:
        query_lower = query.lower()
        filtered = [d for d in debates if query_lower in d["name"].lower() or
                   query_lower in d["description"].lower() or
                   any(query_lower in p.lower() for p in d["participants"])]
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
    print("=" * 50, file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
