# giscus 能力核对

依据 giscus 官方仓库、配置页与 GitHub 文档核对，核对日期：2026-10-11。

## 结论

1. **GitHub Pages 纯静态页面可以嵌入 giscus。** 页面放置 giscus 提供的 `<script src="https://giscus.app/client.js" ...>` 即可；评论界面由脚本创建 iframe 加载。静态页面无需自己的后端。
2. **浏览器端会启动查询流程，但不会直接向 GitHub API 查询。** 页面脚本建立 giscus iframe；iframe 请求 giscus 服务端 API，由服务端使用 GitHub GraphQL API 搜索/读取 Discussions。评论、回复等写入也经 giscus 服务端处理。
3. **访客登录 GitHub 并授权 giscus App 后，可以发表评论和回复。** 授权让 giscus 代表访客发言。仅登录但未完成授权不能通过 giscus 写入。目标仓库还必须公开、启用 Discussions，并安装 giscus App。
4. **不需要 GitHub Actions 来构建评论区。** giscus 在页面访问时运行；Actions 仍可按站点自身需要发布静态文件，但与 giscus 评论加载和创建无关。
5. **Discussion 创建与映射限制：**
   - 对可按页面信息或 `specific` 术语搜索的映射，找不到匹配 Discussion 时，giscus 会在用户首次评论或提交 reaction 时自动创建；不是页面构建时创建。
   - 建议选用类型为 **Announcements** 的分类。GitHub 的该类分类限制新 Discussion 由仓库维护者或具备相应权限的应用（如 giscus）创建；普通访客仍可在已存在的 Discussion 中评论。
   - `data-mapping="specific"` 是按指定术语查找标题包含该术语的 Discussion，仍可自动创建；它不同于 `data-mapping="number"`。按编号加载现有 Discussion 的 `number` 映射不支持自动创建，也不支持分类筛选和 strict 选项。
   - `data-strict="1"` 用于避免 GitHub 标题模糊搜索导致的错配：giscus 改为计算 Discussion 标题的 SHA-1，并在 Discussion 正文中搜索该值。启用前，既有 Discussion 正文须补入对应 SHA-1；此后由 giscus 新建的 Discussion 会自动包含它。它是严格匹配开关，不是 `data-mapping` 的取值。

## 官方来源

- [giscus README：工作方式、搜索、自动创建、访客授权](https://github.com/giscus/giscus#how-it-works)
- [giscus 配置页：生成嵌入脚本、仓库条件、映射与分类说明](https://giscus.app/)
- [giscus 客户端脚本：读取页面映射并创建 iframe](https://github.com/giscus/giscus/blob/main/client.ts)
- [giscus 组件：未找到时允许创建，回复框由用户令牌控制](https://github.com/giscus/giscus/blob/main/components/Giscus.tsx)
- [giscus 服务端 Discussion 查询：调用 GitHub GraphQL](https://github.com/giscus/giscus/blob/main/services/github/getDiscussion.ts)
- [giscus 服务端 API：查询与创建 Discussion](https://github.com/giscus/giscus/blob/main/pages/api/discussions/index.ts)
- [giscus 简体中文配置文案：仓库要求、Announcements 建议、number 限制](https://github.com/giscus/giscus/blob/main/locales/zh-CN/config.json)
- [giscus 高级用法：`data-strict` 的 SHA-1 规则和既有 Discussion 迁移要求](https://github.com/giscus/giscus/blob/main/ADVANCED-USAGE.md#data-strict)
- [GitHub 文档：Discussion 分类](https://docs.github.com/en/discussions/managing-discussions-for-your-community/managing-categories-for-discussions)
- [GitHub 文档：代表用户使用 GitHub App 认证](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-with-a-github-app-on-behalf-of-a-user)
