# Douyin Style Profiler

对标账号风格分析工具。输入抖音博主主页分享链接，采集 TopN 视频卡片；也可以输入已有转写稿，生成结构化风格档案。

## 能做什么

- 用 Playwright 打开抖音并保存登录 Cookie。
- 采集对标账号主页 TopN 视频链接和卡片文本。
- 根据视频标题/转写稿生成 10 个风格模块。
- 输出：
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
python -m playwright install chromium
cp .env.example .env
```

保存 Cookie：

```bash
python -m douyin_style_profiler login
```

采集主页 TopN：

```bash
python -m douyin_style_profiler collect --profile-url "https://v.douyin.com/xxxx/" --top-n 10
```

用采集结果生成风格档案：

```bash
python -m douyin_style_profiler analyze --input outputs/profile_videos.json --nickname "对标账号" --llm
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
run_windows.bat collect --profile-url "https://v.douyin.com/xxxx/" --top-n 10
run_windows.bat analyze --input outputs\profile_videos.json --nickname 对标账号 --llm
```

## 合规说明

本项目只提供个人授权场景下的浏览器自动化和风格分析能力，不内置任何 Cookie、账号凭证或真实博主数据。使用者需要确保自己对采集和分析的数据拥有合法使用权限。

## 参考

Cookie 获取流程参考了公开项目 `jiji262/douyin-downloader` 的使用体验：通过 Playwright 打开浏览器，用户登录后保存 Cookie 到本地配置。

