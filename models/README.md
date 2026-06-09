# models

这里预留本地模型目录。

当前版本默认：

- OpenAI `gpt-5.5` 作为首选 LLM。
- MiniMax 作为备用 LLM。
- FunASR 作为本地自动转写模型，首次运行时会下载到 `models/modelscope/`。
- 没有 LLM API key 时使用 deterministic fallback，方便测试和演示。

不建议把 FunASR 或其他大模型文件直接提交到 GitHub。首次运行转写时，模型会自动下载到本地缓存目录；需要离线使用时，可以由使用者自行提前下载模型。
