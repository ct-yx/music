# 音乐制作流程

这份说明用于新增音乐内容。它不是代码模板；每首曲子使用自己的制作脚本和提示词，网页通过数据文件自动读取。

## 一、一次制作的生命周期

```text
确定概念与约束
  → 编写完整提示词 prompt.md
  → 使用 music21 / MuseScore 生成和导出文件
  → 检查 MusicXML、曲谱、MIDI、音频和小节结构
  → 编写 meta.json
  → 将 slug 加入 content/music/index.json
  → 用本地 HTTP 服务预览
  → 提交并部署到 GitHub Pages
```

### 1. 确定曲目参数

先确定标题、英文副标题、调性、速度、小节数、段落、配器和目标时长。提示词中同时写清楚：

- 情绪和结构弧线；
- 每个段落的起止小节或时间；
- 核心动机、和声和配器进入/退出顺序；
- 力度、音域、节奏密度和必须避免的写法；
- 输出文件名和完成后的自检项目。

### 2. 保存制作提示词

把当时使用的完整提示词保存为曲目目录内的 `prompt.md`。后续修改提示词也追加在同一文件中，保留制作过程，而不是只保留最后结果。

### 3. 生成和导出

将生成脚本放入曲目目录，通常命名为 `generate.py`。脚本集中放置可修改参数，并输出同一目录内的文件：

```text
<slug>.musicxml   MusicXML 源文件
<slug>.mscz       MuseScore 工程
<slug>.mid        MIDI
<slug>.pdf        总谱
<slug>.mp3        试听音频
generate.py       生成脚本
prompt.md         完整提示词
```

建议先生成 MusicXML，再用 MuseScore 导出其余格式。导出后至少检查：文件非空、MusicXML 可解析、总小节数和拍号正确、音频可以播放、PDF 和 MIDI 能打开。

## 二、新增曲目的目录结构

假设新曲目的 slug 是 `quiet-tide`：

```text
content/music/
├── index.json
└── quiet-tide/
    ├── meta.json
    ├── prompt.md
    ├── generate.py
    ├── quiet_tide.musicxml
    ├── quiet_tide.mscz
    ├── quiet_tide.mid
    ├── quiet_tide.pdf
    └── quiet_tide.mp3
```

可以先复制现有曲目目录作为素材起点，再删除旧曲目的输出文件并替换为新文件；复制后必须修改 `meta.json`、`prompt.md` 和 `generate.py` 中仍指向旧曲目的内容。

创建目录的命令示例：

```bash
slug="quiet-tide"
mkdir -p "content/music/$slug"
touch "content/music/$slug/meta.json"
touch "content/music/$slug/prompt.md"
touch "content/music/$slug/generate.py"
```

## 三、填写 `meta.json`

页面由 `meta.json` 驱动。最小可用结构如下，文件名都相对于曲目目录：

```json
{
  "title": "静潮",
  "subtitle": "Quiet Tide",
  "date": "2026-10-18",
  "description": "一句话介绍这首曲子。",
  "key": "D 大调",
  "tempo": "♩=72",
  "bars": 32,
  "duration": 120,
  "instruments": ["钢琴"],
  "credits": {"direction": "ctyx", "generation": "Codex + MuseScore"},
  "sections": [
    {"name": "潮起", "start": 0, "end": 60, "color": "rain"},
    {"name": "潮落", "start": 60, "end": 120, "color": "dew"}
  ],
  "envelope": [0.2, 0.4, 0.7, 0.3],
  "files": {
    "audio": "quiet_tide.mp3",
    "score": "quiet_tide.pdf",
    "musicxml": "quiet_tide.musicxml",
    "midi": "quiet_tide.mid",
    "mscz": "quiet_tide.mscz",
    "script": "generate.py",
    "prompt": "prompt.md"
  },
  "versions": [],
  "license": "CC BY-NC 4.0"
}
```

注意事项：

- `sections[].start` 和 `sections[].end` 使用秒；数量和名称可以自由变化。
- `envelope` 最好每小节一个值，取值范围为 `0` 到 `1`，用于首页曲线和播放器时间轴。
- `versions` 中的 `input`、`output`、`total` 可以写 `null`；页面会显示为“—”，缺失字段不会显示 `undefined`。
- `files` 中只填写实际存在的文件。缺失文件不会阻止其他内容显示。
- `sizes` 可选，用字节数填写文件大小；不填写时页面隐藏大小。
- `palette.light` 和 `palette.dark` 可选，用于只给这一首曲子覆盖全局主题色。

生成 `bars`、`duration`、小节起始时间和 `envelope` 建议值时，可以运行：

```bash
python tools/make_meta.py content/music/quiet-tide/quiet_tide.musicxml
```

这个工具只输出建议，不覆盖手写的 `meta.json`。

## 四、登记曲目

在 `content/music/index.json` 数组中加入一行：

```json
[
  {"slug": "dawn-after-rain"},
  {"slug": "quiet-tide"}
]
```

页面按数组倒序展示，所以把新曲目追加到数组末尾即可。slug 必须与目录名完全一致。

## 五、网页是否需要修改

新增一首音乐时，不需要修改 `index.html`、`assets/app.js` 或 `assets/style.css`。网页会依次：

1. 从 `site.json` 找到 `music` 集合；
2. 读取 `content/music/index.json`；
3. 按 slug 读取对应目录的 `meta.json`；
4. 根据 `files`、`sections`、`envelope` 和其他字段生成页面。

只有下列情况才需要改网页代码：

- 增加一种新的内容类型，并需要新的渲染器；
- 增加现有数据规范没有表达的新交互；
- 修改所有曲目共同的布局或主题行为。

增加文章时也不改页面代码：在 `site.json.collections` 保留或新增集合配置，在 `content/writing/index.json` 登记 slug，再按文章规范放置 `meta.json` 和 `index.md`。

## 六、预览与提交前检查

必须通过 HTTP 服务预览，因为直接用 `file://` 打开会阻止 JSON 和提示词的 `fetch`：

```bash
python -m http.server
```

然后访问 <http://localhost:8000/>，检查：

- 首页出现新曲目，标题、日期、时长和响度曲线正确；
- `#/music/<slug>` 可以播放音频，段落跳转和键盘控制正常；
- 曲谱按钮、下载链接和完整提示词折叠区正常；
- 缺失字段不会出现 `undefined`，缺失文件不会造成白屏；
- 亮色、深色和单曲调色板覆盖都正常；
- 错误 slug 显示明确的返回首页链接。

提交前可运行：

```bash
node --check assets/app.js
python -m compileall -q tools
python -m json.tool site.json >/dev/null
python -m json.tool content/music/index.json >/dev/null
git diff --check
```

完成后将新目录、索引和说明文件提交并推送到 `main`；GitHub Pages 会按仓库当前配置自动发布。
