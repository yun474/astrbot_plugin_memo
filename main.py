"""astrbot_plugin_memo

为 AstrBot 提供持久化备忘录/记忆功能，以两个 LLM Tool 的形式注入：
- memo_read : 读取备忘录
- memo_write: 写入备忘录

支持分会话 / 分用户 两个维度的隔离，可在插件配置中独立开关。
"""

import json
import os
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

DATA_DIR = os.path.join("data", "plugin_memo")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _memo_path(key: str) -> str:
    safe = key.replace("/", "_").replace("\\", "_")
    return os.path.join(DATA_DIR, f"{safe}.json")


def _load(key: str) -> dict:
    path = _memo_path(key)
    if not os.path.exists(path):
        return {"entries": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[memo] 读取文件失败 {path}: {e}")
        return {"entries": []}


def _save(key: str, data: dict):
    _ensure_dir()
    path = _memo_path(key)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[memo] 写入文件失败 {path}: {e}")


def _build_key(event: AstrMessageEvent, split_session: bool, split_user: bool) -> str:
    parts = []
    if split_session:
        session_id = getattr(event.message_obj, "session_id", None) or "unknown_session"
        parts.append(f"s_{session_id}")
    if split_user:
        sender = getattr(event.message_obj, "sender", None)
        user_id = getattr(sender, "user_id", "unknown_user") if sender else "unknown_user"
        parts.append(f"u_{user_id}")
    return "__".join(parts) if parts else "global"


@register(
    "astrbot_plugin_memo",
    "Cloud",
    "为 LLM 提供持久化备忘录 Tools（memo_read / memo_write），支持分会话/分用户隔离",
    "1.0.1",
    "https://github.com/yun474",
)
class MemoPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        _ensure_dir()
        # 不在此处缓存配置，每次操作动态读取以响应配置变更
        logger.info("[memo] 插件初始化完成")

    def _get_cfg(self) -> tuple[bool, bool, int]:
        """动态读取配置，确保配置变更后立即生效，无需重启。"""
        cfg = self.context.get_config()
        return (
            bool(cfg.get("split_session", True)),
            bool(cfg.get("split_user", False)),
            int(cfg.get("max_entries", 50)),
        )

    @filter.llm_tool(name="memo_read")
    async def memo_read(self, event: AstrMessageEvent):
        '''读取当前上下文的持久化备忘录，返回所有已保存的条目。当用户询问你是否记得某件事、或需要回顾历史信息时调用。

        Args:
        '''
        split_session, split_user, _ = self._get_cfg()
        key = _build_key(event, split_session, split_user)
        data = _load(key)
        entries = data.get("entries", [])
        if not entries:
            yield event.plain_result("备忘录为空，尚无任何记录。")
            return
        lines = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(entries))
        yield event.plain_result(f"备忘录共 {len(entries)} 条：\n{lines}")

    @filter.llm_tool(name="memo_write")
    async def memo_write(self, event: AstrMessageEvent, content: str):
        '''向持久化备忘录中写入一条新记录。当用户要求你记住某件事、或对话中出现值得长期保留的信息时调用。

        Args:
            content(string): 要写入的内容，简洁清晰地描述需要记住的事项。
        '''
        content = content.strip()
        if not content:
            yield event.plain_result("写入失败：内容不能为空。")
            return

        split_session, split_user, max_entries = self._get_cfg()
        key = _build_key(event, split_session, split_user)
        data = _load(key)
        entries: list = data.get("entries", [])
        entries.append(content)

        if len(entries) > max_entries:
            removed = len(entries) - max_entries
            entries = entries[-max_entries:]
            logger.info(f"[memo] key={key} 超出上限，已删除最旧 {removed} 条。")

        data["entries"] = entries
        _save(key, data)
        yield event.plain_result(f"已记录：{content}（当前共 {len(entries)} 条）")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("memo_list")
    async def cmd_list(self, event: AstrMessageEvent):
        """列出当前上下文备忘录（管理员指令）"""
        split_session, split_user, _ = self._get_cfg()
        key = _build_key(event, split_session, split_user)
        data = _load(key)
        entries = data.get("entries", [])
        if not entries:
            yield event.plain_result("备忘录为空。")
            return
        lines = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(entries))
        yield event.plain_result(f"📋 备忘录（key: {key}）：\n{lines}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("memo_clear")
    async def cmd_clear(self, event: AstrMessageEvent):
        """清空当前上下文备忘录（管理员指令）"""
        split_session, split_user, _ = self._get_cfg()
        key = _build_key(event, split_session, split_user)
        _save(key, {"entries": []})
        yield event.plain_result(f"✅ 已清空备忘录（key: {key}）。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("memo_del")
    async def cmd_del(self, event: AstrMessageEvent, index: int):
        """删除备忘录中指定序号的条目，序号从 1 开始（管理员指令）"""
        split_session, split_user, _ = self._get_cfg()
        key = _build_key(event, split_session, split_user)
        data = _load(key)
        entries = data.get("entries", [])
        if index < 1 or index > len(entries):
            yield event.plain_result(f"序号 {index} 超出范围（共 {len(entries)} 条）。")
            return
        removed = entries.pop(index - 1)
        data["entries"] = entries
        _save(key, data)
        yield event.plain_result(f"✅ 已删除第 {index} 条：{removed}")

    async def terminate(self):
        logger.info("[memo] 插件已卸载。")
