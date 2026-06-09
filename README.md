# Douyin Style Profiler

对标账号风格分析工具。输入抖音博主主页分享链接，按楼大壮项目同款流程采集 Top10 高赞视频、下载视频、抽取音频、自动转写，再生成结构化风格档案。也可以输入已有转写稿直接分析。

## 能做什么

- 用 Playwright 打开抖音并保存登录 Cookie。
- 复用楼大壮项目下载层：`DouyinAPIClient + X-Bogus + Top10 + 视频下载 + ffmpeg 抽音频`。
- 用 FunASR 自动转写音频，模型默认下载到项目目录的 `models/`。
- 根据视频标题/转写稿生成 10 个风格模块。
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

## 快速开始：开发者模式

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-transcribe.txt
python -m playwright install chromium
cp .env.example .env
```

保存 Cookie：

```bash
python -m douyin_style_profiler login
```

完整流程：采集 Top10、下载、抽音频、转写、生成风格档案：

```bash
python -m douyin_style_profiler run --profile-url "https://v.douyin.com/xxxx/" --top-n 10 --llm
```

如果只想排查下载层：

```bash
python -m douyin_style_profiler download --profile-url "https://v.douyin.com/xxxx/" --top-n 10 --keep-video
```

如果已经下载好了音频，只跑转写：

```bash
python -m douyin_style_profiler transcribe --input outputs/profile_media/profile_videos.json --output outputs/profile_media/transcripts.json
```

如果只想用旧的轻量模式，不下载视频、不转写：

```bash
python -m douyin_style_profiler run --profile-url "https://v.douyin.com/xxxx/" --metadata-only
```

也可以直接用已有转写稿跑：

```bash
python -m douyin_style_profiler analyze --input examples/transcripts.json --nickname "示例账号"
```

## 快速开始：Windows 无 Python 环境

第一步，双击或运行：

```powershell
tools\bootstrap_windows.ps1
```

它会把 Python embeddable、依赖和 Playwright Chromium 安装到项目目录的 `runtime/` 里。

之后运行：

```bat
run_windows.bat analyze --input examples\transcripts.json --nickname 示例账号
```

或：

```bat
run_windows.bat login
run_windows.bat run --profile-url "https://v.douyin.com/xxxx/" --top-n 10 --llm
```

第一次转写时，FunASR 会把模型下载到 `models\modelscope\`。这一步会比较久，但之后会复用本地模型。

## 文件目录

```text
runtime/                 项目内 Python、Playwright 浏览器和 ffmpeg
models/                  FunASR/ModelScope 模型缓存
outputs/                 采集、下载、转写和风格报告输出
src/douyin/              楼大壮项目同款抖音下载 vendor 层
src/douyin_style_profiler 工具本体
```

## 合规说明

本项目只提供个人授权场景下的浏览器自动化、视频下载、音频转写和风格分析能力，不内置任何 Cookie、账号凭证或真实博主数据。使用者需要确保自己对采集、下载、转写和分析的数据拥有合法使用权限。

## 参考

Cookie 获取流程参考了公开项目 `jiji262/douyin-downloader` 的使用体验：通过 Playwright 打开浏览器，用户登录后保存 Cookie 到本地配置。

下载层复用了楼大壮项目中基于公开下载项目思路整理的 Douyin API / X-Bogus vendor 代码。`src/douyin/utils/xbogus.py` 等文件保留了原 Apache License 头部；如果你发布到 GitHub，建议保留相关许可证说明。
