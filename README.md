# Douyin Style Profiler

对标账号风格分析工具。输入抖音博主主页分享链接，采集 Top10 高赞视频、下载视频、抽取音频、自动转写，再生成结构化风格档案。

这个项目默认面向会配置 Python 环境的 GitHub 用户。推荐使用 Python 3.10+，优先 Python 3.10 / 3.11 / 3.12。项目不内置 Python、浏览器运行时或虚拟环境；所有依赖都写在 `requirements.txt` 里。

## 能做什么

- 用 Playwright 打开抖音并保存登录 Cookie。
- 内置抖音下载层：`DouyinAPIClient + X-Bogus + Top10 + 视频下载 + ffmpeg 抽音频`。
- 用 FunASR 自动转写音频，并做本地标点恢复和繁体转简体。
- 根据转写稿生成 10 个风格模块。
- 输出：
  - `profile_videos.json`
  - `transcripts.json`
  - `style_profile.json`
  - `style_report.md`
  - `style_prompt.txt`

## 10 个风格模块

1. 开头钩子
2. 内容结构
3. 表达方式
4. 互动引导
5. 选题方式
6. 整体语气
7. 情绪曲线
8. 用户心理
9. 标志性表达
10. 生成建议

## 环境要求

- Python 3.10+，推荐 Python 3.10 / 3.11 / 3.12
- ffmpeg
- 能正常访问抖音网页
- FunASR 转写模型和 CT-Transformer 标点模型，默认使用 ModelScope 本地缓存

ffmpeg 需要能在命令行里直接执行：

```bash
ffmpeg -version
```

## 安装

```bash
git clone <your-repo-url>
cd douyin-style-profiler
pip install -r requirements.txt
pip install -e .
python -m playwright install chromium
cp .env.example .env
```

如果你不想安装成可编辑包，也可以直接用：

```bash
PYTHONPATH=src python -m douyin_style_profiler --help
```

## 配置 LLM

LLM 的模型和 API key 由使用者自己提供，项目不内置任何 key，也不绑定某一个平台。

`.env` 中填写：

```text
LLM_PROVIDER=
LLM_MODEL=
LLM_API_KEY=
LLM_BASE_URL=
```

支持的 `LLM_PROVIDER`：

| Provider | 说明 |
| --- | --- |
| `openai` | OpenAI 官方 API |
| `deepseek` | DeepSeek |
| `qwen` | 通义千问 DashScope OpenAI-compatible 模式 |
| `kimi` / `moonshot` | Moonshot / Kimi |
| `zhipu` | 智谱 BigModel |
| `minimax` | MiniMax |
| `anthropic` | Claude Messages API |
| `gemini` | Gemini GenerateContent API |
| `openai-compatible` | 任意兼容 `/v1/chat/completions` 的平台或私有网关 |

示例：

```text
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
LLM_API_KEY=你的key
```

自定义 OpenAI-compatible 网关：

```text
LLM_PROVIDER=openai-compatible
LLM_MODEL=你的模型名
LLM_API_KEY=你的key
LLM_BASE_URL=https://api.example.com
```

如果不传 `--llm`，工具会使用 deterministic fallback 生成基础风格档案，方便先测试流程。

## 转写后处理

视频转写完成后会统一经过三步处理：

1. 去掉 FunASR 逐字输出里的空格。
2. 使用本地 CT-Transformer 标点模型恢复中文标点。
3. 使用 OpenCC 做繁体转简体。

标点模型会先搜索用户环境里已有的 ModelScope 缓存，常见位置包括：

```text
~/.cache/modelscope/hub/models/iic/punc_ct-transformer_cn-en-common-vocab471067-large
%USERPROFILE%\.cache\modelscope\hub\models\iic\punc_ct-transformer_cn-en-common-vocab471067-large
/mnt/c/Users/<你的Windows用户名>/.cache/modelscope/hub/models/iic/punc_ct-transformer_cn-en-common-vocab471067-large
models/modelscope/hub/models/iic/punc_ct-transformer_cn-en-common-vocab471067-large
```

如果你的模型放在其他位置，可以设置：

```bash
export FUNASR_PUNC_MODEL_DIR=/path/to/punc_ct-transformer_cn-en-common-vocab471067-large
```

## 使用

第一步，保存抖音 Cookie：

```bash
python -m douyin_style_profiler login
```

第二步，跑完整流程：

```bash
python -m douyin_style_profiler run --profile-url "https://v.douyin.com/xxxx/" --top-n 10 --llm
```

这个命令会执行：

```text
主页链接 -> Top10 视频采集 -> 视频下载 -> 音频抽取 -> FunASR 转写 -> 风格分析 -> 输出报告
```

如果只想排查下载层：

```bash
python -m douyin_style_profiler download --profile-url "https://v.douyin.com/xxxx/" --top-n 10 --keep-video
```

如果已经下载好了音频，只跑转写：

```bash
python -m douyin_style_profiler transcribe --input outputs/profile_media/profile_videos.json --output outputs/profile_media/transcripts.json
```

如果已经有转写稿，只做风格分析：

```bash
python -m douyin_style_profiler analyze --input examples/transcripts.json --nickname "示例账号" --llm
```

也可以不改 `.env`，直接在命令行指定 LLM：

```bash
python -m douyin_style_profiler analyze \
  --input examples/transcripts.json \
  --nickname "示例账号" \
  --llm \
  --llm-provider deepseek \
  --llm-model deepseek-chat \
  --llm-api-key "你的key"
```

如果只想采集主页卡片文本，不下载视频、不转写：

```bash
python -m douyin_style_profiler run --profile-url "https://v.douyin.com/xxxx/" --metadata-only
```

## 输出目录

默认输出在 `outputs/`：

```text
outputs/
  profile_videos.json
  transcripts.json
  style_profile.json
  style_report.md
  style_prompt.txt
```

FunASR 首次转写前会先搜索用户已有的 ModelScope 缓存，例如 `~/.cache/modelscope/`、`~/.modelscope/`、Windows 原生的 `%USERPROFILE%\.cache\modelscope\`、WSL 里的 `/mnt/c/Users/<用户名>/.cache/modelscope/`，以及项目内 `models/modelscope/`。只有找不到可用模型时，才会下载到项目内 `models/modelscope/`。模型文件不建议提交到 GitHub。

## 项目结构

```text
src/douyin/                  抖音下载 vendor 层
src/douyin_style_profiler/   工具本体
examples/                    示例转写输入
tests/                       单元测试
models/                      本地模型缓存目录
outputs/                     运行输出目录
```

## 测试

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

## 合规说明

本项目只提供个人授权场景下的浏览器自动化、视频下载、音频转写和风格分析能力，不内置任何 Cookie、账号凭证或真实博主数据。使用者需要确保自己对采集、下载、转写和分析的数据拥有合法使用权限。

## 第三方声明

Cookie 获取流程参考了公开项目 `jiji262/douyin-downloader` 的使用体验：通过 Playwright 打开浏览器，用户自行登录后保存 Cookie 到本地配置。

`src/douyin/` 下的部分下载层 vendor 代码包含第三方实现思路或许可证头部。请在使用、修改和分发本项目时保留相关源文件中的版权和许可证声明。
