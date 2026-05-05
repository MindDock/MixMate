# MixMate - AI自动视频剪辑系统

> 先理解素材，再操刀剪辑

MixMate 是一个 AI 驱动的自动视频剪辑系统。它先通过计算机视觉和音频分析深度理解你的素材，再根据选定风格自动生成专业剪辑。

## ✨ 特性

- **Timeline 智能识别** — 自动检测镜头分割、运动类型、音频节拍、内容标签
- **6 种剪辑风格** — 抖音快闪、电影感、Vlog轻快、运动燃剪、氛围慢调、MV卡点
- **AI 视觉理解** — 支持本地 Ollama 视觉模型（moondream/llava），自动回退到规则引擎
- **实时进度面板** — 分析过程中实时展示每个视频的处理步骤和状态
- **专业分析面板** — 缩略图预览、视频播放、运动/质量/稳定/亮度/音频指标可视化
- **Web UI + CLI** — 浏览器操作或命令行批量处理

## 🚀 快速开始

### 环境要求

- Python 3.9+
- FFmpeg（视频处理）
- Ollama（可选，AI 视觉理解）

### 安装

```bash
git clone https://github.com/MindDock/MixMate.git
cd MixMate
pip install -r requirements.txt
```

### 安装 FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg
```

### 安装 Ollama 视觉模型（可选）

```bash
# 安装 Ollama
brew install ollama

# 启动服务
brew services start ollama

# 拉取轻量视觉模型（1.7GB，推荐 M 系列芯片）
ollama pull moondream:v2

# 或拉取更大但更准确的模型（4.7GB）
ollama pull llava:7b
```

> 不安装 Ollama 也能用，系统会自动回退到基于传统 CV 算法的规则引擎。

### 启动 Web UI

```bash
./start.sh

# 或指定端口
./start.sh 9090
```

打开浏览器访问 http://localhost:8088

### 停止服务

```bash
./stop.sh
```

## 📖 使用方式

### Web UI

1. **上传素材** — 拖拽或选择视频文件上传
2. **Timeline 识别** — 点击「开始 Timeline 识别」，实时查看分析进度
3. **查看分析结果** — 浏览每个镜头的详细信息（运动、质量、稳定、亮度、音频指标）
4. **选择剪辑风格** — 选择想要的剪辑风格
5. **生成视频** — 一键生成剪辑成品

### 命令行

```bash
# 查看可用风格
python -m mixmate.cli styles

# 分析素材
python -m mixmate.cli analyze video1.mp4 video2.mp4

# 一键生成（分析+剪辑+渲染）
python -m mixmate.cli auto video1.mp4 --style tiktok_flash --count 3

# 批量多风格
python -m mixmate.cli auto video1.mp4 --style tiktok_flash,cinematic,vlog_light

# 启动 Web UI
python -m mixmate.cli web --port 8088
```

## 🎨 剪辑风格

| 风格 | 说明 | 目标时长 | 画幅 |
|------|------|----------|------|
| `tiktok_flash` | 抖音快闪，快节奏卡点 | 15s | 9:16 |
| `cinematic` | 电影感，慢节奏宽画幅 | 30s | 16:9 |
| `vlog_light` | Vlog轻快，自然流畅 | 30s | 9:16 |
| `sports_hype` | 运动燃剪，速度感拉满 | 20s | 9:16 |
| `chill_aesthetic` | 氛围慢调，风景/日常 | 30s | 9:16 |
| `music_video` | MV卡点，严格卡点 | 30s | 9:16 |

## 🏗️ 项目结构

```
MixMate/
├── mixmate/
│   ├── ai/                  # AI Provider 层
│   │   ├── base.py          # 基类定义
│   │   ├── vision.py        # 视觉理解（Ollama/OpenAI/规则引擎）
│   │   ├── speech.py        # 语音识别
│   │   ├── narrative.py     # 叙事规划
│   │   └── providers.py     # Provider 工厂 + 配置管理
│   ├── analyzer/            # 素材分析引擎
│   │   ├── shot_detector.py # 镜头分割
│   │   ├── motion_analyzer.py # 运动分析
│   │   ├── audio_analyzer.py  # 音频/节拍分析
│   │   ├── content_tagger.py  # 内容标签
│   │   └── timeline.py      # Timeline 分析器（整合）
│   ├── editor/              # 剪辑引擎
│   │   ├── auto_editor.py   # 自动剪辑
│   │   ├── cut_engine.py    # 剪切引擎
│   │   ├── effect_engine.py # 特效引擎
│   │   ├── style_profiles.py # 风格配置
│   │   └── subtitle_engine.py # 字幕引擎
│   ├── renderer/            # 渲染引擎
│   │   ├── ffmpeg_wrapper.py  # FFmpeg 封装
│   │   └── batch_renderer.py  # 批量渲染
│   ├── web/                 # Web UI
│   │   ├── app.py           # Flask 服务
│   │   ├── templates/       # HTML 模板
│   │   └── static/          # CSS/JS 静态资源
│   ├── models.py            # 数据模型
│   ├── config.py            # 剪辑风格配置
│   └── cli.py               # 命令行入口
├── start.sh                 # 启动脚本
├── stop.sh                  # 停止脚本
├── requirements.txt         # Python 依赖
└── setup.py                 # 安装配置
```

## ⚙️ AI 配置

Web UI 右上角齿轮图标可打开 AI 配置面板：

- **视觉理解** — 选择 `local`（Ollama）或 `openai`（需 API Key）
- **语音识别** — 选择 `simple`（能量检测）或 `whisper_local`
- **叙事规划** — 选择 `rule_based`（规则引擎）或 `openai`

配置保存在 `mixmate/ai_config.json`。

## 🔧 技术栈

- **后端** — Python, Flask, OpenCV, librosa, scipy, FFmpeg
- **前端** — 原生 JavaScript, CSS（暗色主题）
- **AI** — Ollama（moondream/llava）, OpenAI API（可选）

## 📄 License

MIT License
