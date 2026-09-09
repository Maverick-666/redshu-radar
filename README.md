# 红薯雷达

运行在 macOS 本地的小红书虚拟资料选品监控工具。

## 开发环境

```bash
export UV_PROJECT_ENVIRONMENT=venv
uv sync --group dev
uv run pytest -q
uv run redshu-radar --version
```

项目固定使用 Python 3.12，不使用 macOS 自带的 Python 3.9。
这里显式使用非隐藏的 `venv` 目录，避免当前 macOS 将默认 `.venv` 内的 editable 路径标记为隐藏。
