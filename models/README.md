# models

这里预留本地模型目录。

当前版本默认：

- OpenAI `gpt-5.5` 作为首选 LLM。
- MiniMax 作为备用 LLM。
- FunASR 作为本地自动转写模型，首次运行时会下载到 `models/modelscope/`。
- 没有 LLM API key 时使用 deterministic fallback，方便测试和演示。

不建议把 FunASR 或其他大模型文件直接提交到 GitHub。Windows 打包分发时，可以把下载后的 `models/` 目录和 `runtime/` 一起打包。
