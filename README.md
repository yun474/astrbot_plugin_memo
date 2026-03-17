# astrbot_plugin_memo

为 AstrBot LLM 提供持久化备忘录能力，以两个 **Tool** 的形式注入给大模型：

| Tool | 说明 |
|------|------|
| `memo_read` | 读取当前上下文的全部备忘条目 |
| `memo_write` | 向备忘录追加一条新记录 |

## 安装

将本目录放入 AstrBot 的 `addons/plugins/` 下，重启或热重载即可。

## 配置项

在 AstrBot 管理面板 → 插件配置中调整，或直接编辑 `data/plugin_memo/` 目录。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `split_session` | bool | `true` | 按会话隔离（群聊/私聊各自独立） |
| `split_user` | bool | `false` | 按用户隔离（每人独立备忘录） |
| `max_entries` | int | `50` | 单个备忘录最大条目数，超出时删除最旧条目 |

两个开关可同时开启，存储 key 格式：
- 均关闭 → `global`
- 仅 session → `s_<session_id>`
- 仅 user → `u_<user_id>`
- 均开启 → `s_<session_id>__u_<user_id>`

## 管理员指令

| 指令 | 说明 |
|------|------|
| `/memo_list` | 列出当前上下文备忘录 |
| `/memo_clear` | 清空当前上下文备忘录 |
| `/memo_del <序号>` | 删除指定序号的条目（从 1 开始） |

## 数据存储

所有数据存储于 `data/plugin_memo/*.json`，更新或卸载插件不会丢失。
