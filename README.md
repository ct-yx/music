# ctyx 的曲子

一个纯静态的音乐与写作作品集。页面使用 HTML、CSS 和原生 JavaScript，不需要安装依赖或运行构建；可直接部署到 GitHub Pages 的 `main` 分支根目录。

## 目录结构

```text
.
├── index.html
├── assets/                 # 页面样式和脚本
├── site.json               # 站点、集合、评论和评分配置
├── content/
│   ├── music/
│   │   ├── index.json      # 音乐集合索引
│   │   └── <slug>/          # 每首曲子的 meta.json 和素材
│   └── writing/             # 文章集合（当前筹备中）
├── data/ratings.json        # 汇总后的评分数据
├── tools/
└── .github/workflows/
```

## 新增内容

完整的音乐制作生命周期、曲目目录结构、`meta.json` 填写方式和预览检查见：[音乐制作流程](docs/music-production.md)。

### 新增音乐

1. 在 `content/music/` 下新建一个 slug 文件夹，加入曲目文件与 `meta.json`。
2. 在 `content/music/index.json` 数组末尾加入 `{"slug":"你的-slug"}`。页面按数组倒序展示，因此新曲目会排在前面。
3. 所有曲目页面均由 `meta.json` 驱动，不需要修改页面代码。字段可缺省；缺失的行会隐藏。`files` 中的文件名必须是内容目录内的相对路径。

### 新增文章

在 `content/writing/<slug>/` 中添加 `meta.json` 和正文 Markdown 文件，并把 slug 追加到 `content/writing/index.json`。文章元数据至少包含 `title`、`date`、`description`、`tags`、`license`、`body`。渲染器支持标题、段落、列表、引用、行内代码、代码块、粗体、斜体、链接和相对图片。

## 授权范围

| 协议 | 覆盖文件 | 用途 |
| --- | --- | --- |
| MIT | `index.html`、`assets/`、`tools/`、`content/music/*/generate.py` | 站点代码与生成工具 |
| CC BY-NC 4.0 | `content/` 下的音乐、曲谱、音频、文章、提示词及其他创作内容 | 署名、非商业使用 |

CC BY-NC 4.0 官方文本：[creativecommons.org/licenses/by-nc/4.0](https://creativecommons.org/licenses/by-nc/4.0/)。每个内容目录的 `meta.json` 可单独标明协议；缺失时使用 `site.json.defaultLicense`。

## 本地预览

在仓库根目录运行：

```bash
python -m http.server
```

然后打开 <http://localhost:8000/>。直接双击 `index.html` 以 `file://` 打开时，浏览器会阻止页面 `fetch` JSON、曲目数据和提示词；页面会显示对应错误提示。

## 部署到 GitHub Pages

1. 将仓库内容推送到 GitHub。
2. 打开仓库 **Settings → Pages**。
3. 选择 **Deploy from a branch**。
4. 选择 **main / (root)** 并保存。

站点使用相对路径，支持 `https://<user>.github.io/<repo>/` 子路径部署。当前仓库地址已填入 `site.json` 的 `repo`；评论和评分仍需要另外填写 giscus 的仓库 ID 与分类 ID。

## 启用评论

1. 将仓库设为公开，在 **Settings → Features** 开启 **Discussions**。
2. 新建一个讨论分类，类型选 **Announcement**。这个类型限制新讨论主题由维护者和 giscus 创建；访客仍可在页面中登录 GitHub，通过 giscus 评论框发表回复。
3. 安装 giscus GitHub App 并授权此仓库。
4. 在 [giscus.app](https://giscus.app/) 选择仓库和分类，取得 `repoId`、`categoryId`。
5. 把 `repo`、`repoId`、`category`、`categoryId` 填入 `site.json` 的 `comments`，然后提交推送。

只有配置完整后内容页才显示评论入口；点击“查看评论”时才会从 `giscus.app` 加载脚本。浏览器会加载 giscus 的 iframe，giscus 服务端通过 GitHub GraphQL 查询和写入对应的 Discussions；访客登录 GitHub 并授权 giscus 后，可以直接提交评论和回复。首页和集合页不加载评论脚本。评论功能不依赖本仓库的 GitHub Actions；Actions 仅用于下面的评分汇总。实现机制见 [giscus 官方说明](https://github.com/giscus/giscus#how-it-works) 和 [能力核对记录](docs/giscus-capability.md)。

## 启用评分

1. 在 Discussions 新建 `Ratings` 分类，类型选 **Announcement**。
2. 在 [giscus.app](https://giscus.app/) 选择仓库和 `Ratings` 分类，取得 `categoryId`，填入 `site.json` 的 `comments.ratings`。
3. 打开 **Settings → Actions → General → Workflow permissions**，选择 **Read and write permissions**。
4. 手动运行一次 `ratings` 工作流，确认 `data/ratings.json` 可以被更新。

评分讨论标题按 `rating/<collection>/<slug>` 匹配。评论第一行只接受 `0`–`5` 整数，可写成 `评分：4`、`4/5` 或 `4分`；每个账号仅统计其最后更新的一条有效评分，仓库所有者和 `excludeAuthors` 中的账号会被忽略。

- 评分汇总最多延迟数分钟，另有每 6 小时一次的定期同步。
- 评分公开可见；“一账号一票”不防止小号。
- 垃圾评分可直接在 Discussions 删除；下次汇总会自动移除。

工作流只使用 GitHub 内置的 `GITHUB_TOKEN` 和官方 `actions/checkout`。

## MusicXML 建议工具

`tools/make_meta.py` 需要本地安装 `music21`。它只打印 `bars`、`duration`、`measureStarts` 和 `envelope` 建议，不会覆盖 `meta.json`：

```bash
python -m pip install music21
python tools/make_meta.py content/music/dawn-after-rain/dawn_after_rain.musicxml
```

## 主题色配置

主题色分为全局默认值和单曲覆盖值：

- `site.json.theme.light` / `site.json.theme.dark` 定义页面底色、文字、边框、按钮和四个段落色的全局默认值。
- 音乐内容的 `meta.json.palette.light` / `meta.json.palette.dark` 可以只覆盖当前曲目的段落色。`sections[].color` 仍填写 `rain`、`clear`、`sunrise`、`dew` 等颜色键。
- 单曲没有提供某个颜色时，继承当前主题的全局值；切换浅色、深色或跟随系统时会同步刷新页面和时间轴。

例如：

```json
{
  "palette": {
    "light": { "rain": "#607789", "sunrise": "#e6b36b" },
    "dark": { "rain": "#536b76", "sunrise": "#aa8050" }
  }
}
```
