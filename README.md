# AIChat MCP Server

将 AIChat 服务封装为 MCP (Model Context Protocol) 服务器，供 Claude、Cursor 等 AI 客户端调用。

## 功能

AI 可以通过 MCP 工具调用你的 AIChat 服务：

- 创建AI角色用户
- 创建和管理会话
- 发送消息
- 启动/停止自动对话
- 搜索历史著名论战

## 快速开始

### 1. 安装依赖

```bash
cd AIChat-MCP
pip install -r requirements.txt
```

### 2. 启动 MCP Server

```bash
python server.py
```

### 3. 配置 MCP 客户端

#### 方式A: 使用 mcporter (推荐)

将配置添加到 `C:\Users\renji\.mcporter\mcporter.json`:

```json
{
  "mcpServers": {
    "aichat": {
      "command": "python",
      "args": ["D:/AI Project/AIChat/AIChat-MCP/server.py"],
      "env": {
        "AICHAT_BASE_URL": "http://localhost:8080/api"
      }
    }
  }
}
```

验证配置：
```bash
mcporter list aichat
```

#### 方式B: Claude Desktop

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aichat": {
      "command": "python",
      "args": ["D:/AI Project/AIChat/AIChat-MCP/server.py"],
      "env": {
        "AICHAT_BASE_URL": "http://localhost:8080/api"
      }
    }
  }
}
```

#### Cursor IDE

在设置中添加 MCP Server 配置。

## 可用工具

| 工具 | 说明 |
|------|------|
| `list_users` | 列出所有AI角色用户 |
| `create_user` | 创建新的AI角色 |
| `get_user` | 获取用户详情 |
| `list_sessions` | 列出所有会话 |
| `create_session` | 创建新会话 |
| `get_session` | 获取会话详情和消息 |
| `send_message` | 发送消息 |
| `start_chat` | 启动自动对话 |
| `stop_chat` | 停止对话 |
| `delete_session` | 删除会话 |
| `clear_messages` | 清空消息 |
| `search_famous_debates` | 搜索历史著名论战 |

## 使用示例

### 命令行测试

```bash
# 列出所有工具
mcporter list aichat

# 列出用户
mcporter call aichat.list_users

# 搜索历史论战
mcporter call aichat.search_famous_debates "query=物理"

# 创建用户
mcporter call aichat.create_user name:=牛顿 modelType:=OPENAI rolePrompt:=你是艾萨克·牛顿

# 创建会话
mcporter call aichat.create_session name:=牛顿vs胡克 sessionTheme:=关于万有引力优先权的争论

# 获取会话详情
mcporter call aichat.get_session sessionId:=1
```

### 让 AI 创建历史人物对话

```
用户: 帮我创建一个关于牛顿和胡克万有引力争论的对话
```

AI 会自动:
1. 调用 `search_famous_debates` 搜索相关论战
2. 调用 `create_user` 创建"牛顿"用户
3. 调用 `create_user` 创建"胡克"用户
4. 调用 `create_session` 创建会话
5. 调用 `start_chat` 启动自动对话

### 搜索历史论战

```
用户: 找出物理学上著名的论战
```

AI 会调用 `search_famous_debates` 返回预设的历史著名论战列表。

## 配置

### 修改后端地址

```bash
# 方式1: 环境变量
set AICHAT_BASE_URL=http://localhost:8080/api
python server.py

# 方式2: 直接修改 server.py 中的 BASE_URL
BASE_URL = "http://your-server:8080/api"
```

## 项目结构

```
AIChat-MCP/
├── server.py         # MCP Server 主程序
├── requirements.txt  # Python 依赖
└── README.md         # 说明文档
```

## 依赖

- Python 3.8+
- mcp >= 1.0.0
- requests >= 2.31.0
