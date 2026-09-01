# AI Log — Deliverable #4

> Ghi lại toàn bộ prompt nhóm gửi cho AI trong quá trình làm dự án, và đẩy lên server
> chấm điểm của BTC.

## Log nằm ở đâu

| Đường dẫn | Nội dung |
|---|---|
| `.ai-log/session.jsonl` | Log của phiên hiện tại, mỗi dòng 1 JSON |
| `.ai-log/archive/YYYY-MM-DD.jsonl` | Log đã xoay vòng theo ngày |

**Nội dung log không được commit** (`.gitignore`: `.ai-log/*.jsonl`, `.ai-log/archive/`) —
prompt thường chứa đoạn code, dữ liệu và đôi khi cả chuỗi kết nối. Git chỉ giữ cấu trúc
thư mục (`.ai-log/.gitkeep`); bản chấm điểm nằm trên server BTC, được đẩy lên bằng
`scripts/submit_log.py`.

Tính đến 01/09/2026: **10.732 entry**, từ 28/07/2026 đến 01/09/2026, gồm 2 nguồn —
`claude` (10.517) và `antigravity` (215).

## Cơ chế ghi

| Công cụ | Cách ghi |
|---|---|
| Claude Code | Hook `UserPromptSubmit` / `PostToolUse` / `Stop` trong [`.claude/settings.json`](../.claude/settings.json) gọi [`scripts/log_hook.py`](../scripts/log_hook.py) |
| Codex / Cursor / Gemini CLI / Copilot | Hook tương ứng trong `.codex/hooks.json`, `.cursor/hooks.json`, `.gemini/settings.json`, `.github/hooks/hooks.json` |
| Antigravity IDE | Pre-push hook chạy [`scripts/log_antigravity.py`](../scripts/log_antigravity.py) `--auto`, đọc thẳng transcript trên đĩa |
| Tool web không có hook (ChatGPT, Gemini Web…) | Ghi tay bằng [`scripts/log_manual.py`](../scripts/log_manual.py) — xem [`.agents/workflows/log.md`](../.agents/workflows/log.md) |

Quy ước cho agent khi làm việc trong repo này: **không tự gọi script log**, mọi thứ đã tự
động — xem [`.agents/rules/ai-log-hook.md`](../.agents/rules/ai-log-hook.md).

## Cài đặt sau khi clone

```bash
# Linux / macOS / Git Bash
bash scripts/setup_hooks.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```

Cần 2 biến trong `.env` (key riêng lấy từ link mời của BTC):

```
AI_LOG_SERVER=https://ai-logs.note.transformerlabs.ai/api/ingest
AI_LOG_API_KEY=...
```

## Gửi lên server BTC

Pre-push hook (cài ở bước trên) chạy `log_antigravity.py --auto` rồi
[`scripts/submit_log.py`](../scripts/submit_log.py) mỗi lần `git push`. Hook cố tình
**không bao giờ chặn push** (`|| true`, `exit 0`) — nên phải đọc output của lần push: nếu
thấy submit lỗi thì sửa rồi chạy tay `bash scripts/_pyrun.sh scripts/submit_log.py`, đừng
để trôi vì phần log đó không tự gửi lại.
