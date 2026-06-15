# models

这里预留本地模型目录。

当前项目不内置任何 LLM API key，也不指定某个付费模型作为默认优先级。需要使用 LLM 精细分析时，请由使用者在 `.env` 或命令行参数中自行配置：

- `LLM_PROVIDER`
- `LLM_MODEL`
- `LLM_API_KEY`
- `LLM_BASE_URL`

FunASR 和 CT-Transformer 标点模型用于本地音频转写与后处理。程序会优先搜索用户已有的 ModelScope 缓存；找不到时，才会按配置下载到本地缓存目录。

不建议把 FunASR 或其他大模型文件直接提交到 GitHub。需要离线使用时，可以由使用者自行提前下载模型，并通过 `.env` 中的 `MODELSCOPE_CACHE` 或 `FUNASR_PUNC_MODEL_DIR` 指向本地路径。
