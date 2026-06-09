# Douyin Style Profiler

对标账号风格分析工具。输入抖音博主主页分享链接，按楼大壮项目同款流程采集 Top10 高赞视频、下载视频、抽取音频、自动转写，再生成结构化风格档案。

这个项目默认面向会配置 Python 环境的 GitHub 用户。项目不内置 Python、浏览器运行时或虚拟环境；所有依赖都写在 `requirements.txt` 里。

## 能做什么

- 用 Playwright 打开抖音并保存登录 Cookie。
- 复用楼大壮项目下载层：`DouyinAPIClient + X-Bogus + Top10 + 视频下载 + ffmpeg 抽音频`。
- 用 FunASR 自动转写音频，模型默认下载到 `models/`。
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

- Python 3.10+
- ffmpeg
- 能正常访问抖音网页

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

`.env` 中可以配置：

```text
OPENAI_API_KEY=
MINIMAX_API_KEY=
```

规则：

- 有 `OPENAI_API_KEY` 时优先使用 OpenAI `gpt-5.5`。
- 没有 OpenAI key 时使用 MiniMax。
- 两个 key 都没有时，仍可用 deterministic fallback 生成基础风格档案，方便测试流程。

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

FunASR 首次转写时会下载模型，默认缓存到 `models/modelscope/`。模型文件不建议提交到 GitHub。

## 项目结构

```text
src/douyin/                  楼大壮项目同款抖音下载 vendor 层
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

## 参考

Cookie 获取流程参考了公开项目 `jiji262/douyin-downloader` 的使用体验：通过 Playwright 打开浏览器，用户登录后保存 Cookie 到本地配置。

下载层复用了楼大壮项目中基于公开下载项目思路整理的 Douyin API / X-Bogus vendor 代码。`src/douyin/utils/xbogus.py` 等文件保留了原 Apache License 头部；如果你发布到 GitHub，建议保留相关许可证说明。
