const SVG_NS = "http://www.w3.org/2000/svg";
const app = document.getElementById("app");
const OFFICIAL_LICENSE_URL = "https://creativecommons.org/licenses/by-nc/4.0/";
const state = {
  sitePromise: null,
  site: null,
  ratings: null,
  ratingsLoaded: false,
  themeMode: "system",
  routeSerial: 0,
  timelineId: 0,
  giscusLoads: new Set(),
  paletteTargets: new Map(),
  activeContentNode: null,
  activeContentMeta: null
};

const THEME_VARIABLES = {
  page: "--page",
  surface: "--surface",
  ink: "--ink",
  muted: "--muted",
  line: "--line",
  lineStrong: "--line-strong",
  focus: "--focus",
  link: "--link",
  buttonBg: "--button-bg",
  buttonInk: "--button-ink",
  trackBg: "--track-bg",
  barBg: "--bar-bg"
};

function configuredSectionKeys(site, meta) {
  const keys = new Set(["neutral"]);
  [site?.theme?.light, site?.theme?.dark, meta?.palette?.light, meta?.palette?.dark].forEach((branch) => {
    Object.keys(sectionThemeBranch(branch)).forEach((key) => {
      if (/^[a-z0-9_-]+$/i.test(key)) keys.add(key.toLowerCase());
    });
  });
  return keys;
}

function createElement(tagName, className, value) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (value !== undefined && value !== null) node.textContent = String(value);
  return node;
}

function appendText(parent, value) {
  if (value !== undefined && value !== null && String(value) !== "") {
    parent.append(document.createTextNode(String(value)));
  }
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function finiteNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatInteger(value) {
  const number = finiteNumber(value);
  if (number === null) return "—";
  try {
    return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(number);
  } catch {
    return String(Math.round(number));
  }
}

function formatDuration(value) {
  const number = finiteNumber(value);
  if (number === null || number < 0) return "";
  const seconds = Math.round(number);
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function formatDate(value) {
  if (typeof value !== "string" || !value.trim()) return "";
  return value.trim();
}

function decodePart(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function parseRoute() {
  const raw = window.location.hash.replace(/^#/, "").replace(/^\/+/, "");
  if (!raw) return { type: "home" };
  const parts = raw.split("/").filter(Boolean).map(decodePart);
  if (parts.length === 1) return { type: "collection", collectionId: parts[0] };
  if (parts.length === 2) return { type: "content", collectionId: parts[0], slug: parts[1] };
  return { type: "error", message: "这个地址无法识别。" };
}

async function fetchJson(path) {
  if (typeof path !== "string" || !path) throw new Error("缺少数据路径");
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`加载 ${path} 失败（${response.status}）`);
  return response.json();
}

async function fetchText(path) {
  if (typeof path !== "string" || !path) throw new Error("缺少文本路径");
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`加载 ${path} 失败（${response.status}）`);
  return response.text();
}

function getCollections(site) {
  return Array.isArray(site?.collections) ? site.collections.filter(isRecord) : [];
}

function findCollection(site, collectionId) {
  return getCollections(site).find((collection) => collection.id === collectionId) || null;
}

function updateSiteMetadata(site) {
  const title = typeof site?.title === "string" && site.title.trim() ? site.title.trim() : "个人作品集";
  const description = typeof site?.intro === "string" && site.intro.trim()
    ? site.intro.trim()
    : "音乐、文章与制作过程。";
  document.querySelector('meta[name="description"]')?.setAttribute("content", description);
  document.querySelector('meta[property="og:title"]')?.setAttribute("content", title);
  document.querySelector('meta[property="og:description"]')?.setAttribute("content", description);
}

function contentDirectory(collectionId, slug) {
  return `content/${encodeURIComponent(collectionId)}/${encodeURIComponent(slug)}`;
}

function safeContentRelativePath(value) {
  if (typeof value !== "string") return null;
  const path = value.trim();
  if (!path || path.startsWith("/") || path.includes("\\") || path.includes("\u0000")) return null;
  const parts = path.split("/");
  if (parts.some((part) => !part || part === "." || part === "..")) return null;
  return path;
}

function contentPath(collectionId, slug, fileName) {
  const safePath = safeContentRelativePath(fileName);
  return safePath
    ? `${contentDirectory(collectionId, slug)}/${safePath.split("/").map((part) => encodeURIComponent(part)).join("/")}`
    : null;
}

function collectionIndexPath(collectionId) {
  return `content/${encodeURIComponent(collectionId)}/index.json`;
}

function createAnchor(href, label, className) {
  const link = createElement("a", className, label);
  link.href = href;
  return link;
}

function renderError(main, title, message, includeHome = true) {
  const section = createElement("section", "error-page");
  section.append(createElement("h2", null, title));
  section.append(createElement("p", null, message));
  if (window.location.protocol === "file:") {
    section.append(createElement("p", null, "当前是 file:// 打开方式，浏览器会阻止页面读取 JSON。请在仓库根目录运行："));
    section.append(createElement("pre", null, "python -m http.server"));
  }
  if (includeHome) section.append(createAnchor("#/", "返回首页"));
  main.replaceChildren(section);
}

function buildShell(site, route) {
  app.replaceChildren();
  const header = createElement("header", "site-header");
  const homeLink = createAnchor("#/", site.title || "个人作品集");
  const heading = createElement("h1");
  heading.append(homeLink);
  header.append(heading);
  if (site.intro) header.append(createElement("p", "site-intro", site.intro));

  const nav = createElement("nav", "site-nav");
  nav.setAttribute("aria-label", "内容集合");
  getCollections(site).forEach((collection) => {
    const link = createAnchor(`#/${encodeURIComponent(collection.id)}`, collection.name || collection.id || "未命名集合");
    if (collection.status === "planned") link.setAttribute("aria-label", "筹备中");
    if (route.collectionId === collection.id) link.setAttribute("aria-current", "page");
    nav.append(link);
  });
  if (nav.childElementCount) header.append(nav);
  app.append(header);

  const main = createElement("main", "main-content");
  main.id = "main-content";
  app.append(main);
  renderFooter(site);
  return main;
}

function renderFooter(site) {
  const footer = createElement("footer", "site-footer");
  const links = createElement("div", "footer-links");
  const license = site.license || site.defaultLicense;
  if (license) links.append(createAnchor(OFFICIAL_LICENSE_URL, license));
  const repositoryUrl = getRepositoryUrl(site.repo);
  if (repositoryUrl) links.append(createAnchor(repositoryUrl, "GitHub 仓库"));
  if (links.childElementCount) footer.append(links);

  const switcher = createElement("div", "theme-switcher");
  switcher.append(createElement("span", "theme-label", "主题"));
  [
    ["light", "浅色"],
    ["dark", "深色"],
    ["system", "跟随系统"]
  ].forEach(([mode, label]) => {
    const button = createElement("button", "theme-button", label);
    button.type = "button";
    button.dataset.themeMode = mode;
    button.addEventListener("click", () => setTheme(mode));
    switcher.append(button);
  });
  footer.append(switcher);
  app.append(footer);
  updateThemeButtons();
}

function getRepositoryUrl(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const repository = value.trim();
  if (/^https:\/\//i.test(repository)) return repository;
  if (/^[^/]+\/[^/]+$/.test(repository)) return `https://github.com/${repository}`;
  return null;
}

function readStoredTheme() {
  try {
    const value = window.localStorage.getItem("ctyx-theme");
    return ["light", "dark", "system"].includes(value) ? value : "system";
  } catch {
    return "system";
  }
}

function actualTheme() {
  if (document.documentElement.dataset.theme === "dark") return "dark";
  if (document.documentElement.dataset.theme === "light") return "light";
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function validThemeValue(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const candidate = value.trim();
  if (window.CSS?.supports && !window.CSS.supports("color", candidate)) return null;
  return candidate;
}

function themeBranch(source, mode) {
  return isRecord(source?.[mode]) ? source[mode] : {};
}

function sectionThemeBranch(source) {
  if (!isRecord(source)) return {};
  return isRecord(source.sections) ? source.sections : source;
}

function applyThemeTokens(site) {
  const root = document.documentElement;
  const mode = actualTheme();
  const branch = themeBranch(site?.theme, mode);
  Object.entries(THEME_VARIABLES).forEach(([key, variable]) => {
    root.style.removeProperty(variable);
    const value = validThemeValue(branch[key]);
    if (value) root.style.setProperty(variable, value);
  });
  configuredSectionKeys(site).forEach((key) => root.style.removeProperty(`--section-${key}`));
  Object.entries(sectionThemeBranch(branch)).forEach(([key, value]) => {
    const safeKey = typeof key === "string" && /^[a-z0-9_-]+$/i.test(key) ? key.toLowerCase() : null;
    const color = validThemeValue(value);
    if (safeKey && color) root.style.setProperty(`--section-${safeKey}`, color);
  });
}

function resolvedSectionPalette(site, meta) {
  const mode = actualTheme();
  const global = sectionThemeBranch(themeBranch(site?.theme, mode));
  const local = sectionThemeBranch(themeBranch(meta?.palette, mode));
  return { ...global, ...local };
}

function applySectionPalette(node, site, meta) {
  if (!node) return;
  configuredSectionKeys(site, meta).forEach((key) => node.style.removeProperty(`--section-${key}`));
  const palette = resolvedSectionPalette(site, meta);
  Object.entries(palette).forEach(([key, value]) => {
    const safeKey = typeof key === "string" && /^[a-z0-9_-]+$/i.test(key) ? key.toLowerCase() : null;
    const color = validThemeValue(value);
    if (safeKey && color) node.style.setProperty(`--section-${safeKey}`, color);
  });
  state.paletteTargets.set(node, meta);
}

function refreshPaletteTargets() {
  state.paletteTargets.forEach((meta, node) => {
    if (node.isConnected) applySectionPalette(node, state.site, meta);
    else state.paletteTargets.delete(node);
  });
}

function setTheme(mode) {
  state.themeMode = ["light", "dark", "system"].includes(mode) ? mode : "system";
  if (state.themeMode === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = state.themeMode;
  try {
    window.localStorage.setItem("ctyx-theme", state.themeMode);
  } catch {
    // 隐私模式下无法写入时继续使用当前页面状态。
  }
  applyThemeTokens(state.site);
  refreshPaletteTargets();
  updateThemeButtons();
  syncGiscusTheme();
}

function updateThemeButtons() {
  document.querySelectorAll("[data-theme-mode]").forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.themeMode === state.themeMode ? "true" : "false");
  });
}

function syncGiscusTheme() {
  const theme = actualTheme();
  document.querySelectorAll("iframe.giscus-frame").forEach((frame) => {
    try {
      frame.contentWindow?.postMessage({ giscus: { setConfig: { theme } } }, "https://giscus.app");
    } catch {
      // iframe 尚未准备好时忽略，后续加载完成会再次同步。
    }
  });
}

function isCommentsConfigured(site) {
  const comments = site?.comments;
  return Boolean(comments && comments.provider === "giscus" && comments.repo && comments.repoId && comments.category && comments.categoryId);
}

function isRatingsConfigured(site) {
  const comments = site?.comments;
  const ratings = comments?.ratings;
  return Boolean(
    ratings && ratings.enabled !== false && comments.repo && comments.repoId && ratings.category && ratings.categoryId
  );
}

function ratingMinimum(site) {
  const value = finiteNumber(site?.comments?.ratings?.minCount);
  return value !== null && value >= 0 ? Math.round(value) : 3;
}

async function ensureRatings(site) {
  if (!isRatingsConfigured(site)) return null;
  if (state.ratingsLoaded) return state.ratings;
  state.ratingsLoaded = true;
  state.ratings = { items: {} };
  const dataPath = site.comments.ratings.dataPath || "data/ratings.json";
  try {
    const data = await fetchJson(dataPath);
    if (isRecord(data) && isRecord(data.items)) state.ratings = data;
  } catch {
    // 评分数据缺失时静默显示暂无评分。
  }
  return state.ratings;
}

function normalizedRating(site, collectionId, slug) {
  if (!state.ratings || !isRecord(state.ratings.items)) return null;
  const item = state.ratings.items[`${collectionId}/${slug}`];
  if (!isRecord(item)) return null;
  const rawCount = finiteNumber(item.count);
  const rawAverage = finiteNumber(item.average);
  const average = rawAverage !== null && rawAverage >= 0 && rawAverage <= 5 ? rawAverage : null;
  const distribution = Array.isArray(item.distribution)
    ? item.distribution.slice(0, 6).map((value) => {
      const number = finiteNumber(value);
      return number !== null && number >= 0 ? Math.floor(number) : 0;
    })
    : [];
  return {
    count: rawCount !== null && Number.isInteger(rawCount) && rawCount >= 0 ? rawCount : 0,
    average,
    distribution: Array.from({ length: 6 }, (_, index) => Math.max(0, distribution[index] || 0))
  };
}

function createRatingSummary(site, collectionId, slug, compact = false) {
  if (!isRatingsConfigured(site)) return null;
  const rating = normalizedRating(site, collectionId, slug) || { count: 0, average: null, distribution: [0, 0, 0, 0, 0, 0] };
  const minimum = ratingMinimum(site);
  if (compact && (rating.count < minimum || rating.average === null)) return null;
  const summary = createElement("div", compact ? "row-rating" : "rating-summary");
  const copy = createElement("span");
  if (compact) {
    copy.textContent = formatAverage(rating.average);
  } else if (rating.count === 0) {
    copy.textContent = "暂无评分";
  } else if (rating.count < minimum) {
    copy.textContent = `评分还不多，共 ${formatInteger(rating.count)} 人`;
  } else if (rating.average !== null) {
    const average = formatAverage(rating.average);
    copy.append(createElement("strong", null, `评分 ${average} / 5`));
    appendText(copy, `，${formatInteger(rating.count)} 人`);
  } else {
    copy.textContent = `评分还不多，共 ${formatInteger(rating.count)} 人`;
  }
  summary.append(copy);

  if (!compact && rating.count >= minimum) {
    const distribution = createElement("div", "distribution");
    distribution.setAttribute("aria-label", "0 到 5 分的评分分布");
    const max = Math.max(...rating.distribution, 1);
    rating.distribution.forEach((count) => {
      const bar = createElement("span", "distribution-bar");
      bar.style.height = `${Math.max(4, (count / max) * 100)}%`;
      bar.title = `${formatInteger(count)} 人`;
      distribution.append(bar);
    });
    summary.append(distribution);
  }
  return summary;
}

function formatAverage(value) {
  const number = finiteNumber(value);
  if (number === null || number < 0 || number > 5) return "";
  return number.toFixed(1);
}

async function loadCollectionEntries(collection) {
  const data = await fetchJson(collectionIndexPath(collection.id));
  if (!Array.isArray(data)) return [];
  return data.slice().reverse().filter((entry) => isRecord(entry) && typeof entry.slug === "string" && entry.slug.trim());
}

async function loadMeta(collectionId, slug) {
  return fetchJson(contentPath(collectionId, slug, "meta.json"));
}

function displayTitle(meta, slug) {
  return typeof meta?.title === "string" && meta.title.trim() ? meta.title.trim() : slug;
}

function createContentRow(collection, entry, meta, site) {
  const slug = entry.slug;
  const row = createAnchor(`#/${encodeURIComponent(collection.id)}/${encodeURIComponent(slug)}`, null, "content-row");
  const primary = createElement("div");
  primary.append(createElement("div", "row-title", displayTitle(meta, slug)));
  const metadata = createElement("div", "row-meta");
  const date = formatDate(meta?.date);
  if (date) metadata.append(createElement("time", null, date));
  const duration = formatDuration(meta?.duration);
  if (duration) metadata.append(createElement("span", null, duration));
  const rating = createRatingSummary(site, collection.id, slug, true);
  if (rating) metadata.append(rating);
  if (metadata.childElementCount) primary.append(metadata);
  if (Array.isArray(meta?.envelope) && meta.envelope.length) primary.append(createMiniEnvelope(meta, site));
  row.append(primary);
  return row;
}

function createMiniEnvelope(meta, site) {
  const svg = createElementNS("svg");
  svg.setAttribute("class", "row-graph");
  svg.setAttribute("viewBox", "0 0 1000 46");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "响度曲线");
  applySectionPalette(svg, site, meta);
  const envelope = meta.envelope.map((value) => Math.max(0, Math.min(1, finiteNumber(value) || 0)));
  const sections = normalizedSections(meta, finiteNumber(meta.duration) || 1);
  sections.forEach((section, index) => {
    const path = createElementNS("path");
    path.setAttribute("class", `timeline-segment ${sectionClass(section.color)}`);
    path.style.fill = `var(--section-${sectionKey(section.color)}, var(--section-neutral))`;
    path.setAttribute("d", areaPath(envelope, section, 1000, 46, finiteNumber(meta.duration) || 1));
    path.setAttribute("opacity", "0.82");
    svg.append(path);
  });
  return svg;
}

function createElementNS(tagName) {
  return document.createElementNS(SVG_NS, tagName);
}

function sectionClass(color) {
  const key = sectionKey(color);
  return `section-${key}`;
}

function sectionKey(color) {
  return typeof color === "string" && /^[a-z0-9_-]+$/i.test(color) ? color.toLowerCase() : "neutral";
}

function normalizedSections(meta, duration) {
  const raw = Array.isArray(meta?.sections) ? meta.sections : [];
  const sections = raw
    .filter(isRecord)
    .map((section) => ({
      name: typeof section.name === "string" && section.name.trim() ? section.name.trim() : "未命名段落",
      start: Math.max(0, finiteNumber(section.start) || 0),
      end: Math.max(0, finiteNumber(section.end) || 0),
      color: section.color
    }))
    .filter((section) => section.end > section.start)
    .sort((a, b) => a.start - b.start);
  if (sections.length) return sections;
  return [{ name: "全曲", start: 0, end: Math.max(duration, 1), color: "neutral" }];
}

function areaPath(envelope, section, width, height, trackDuration) {
  const duration = Math.max(finiteNumber(trackDuration) || 1, 1);
  const startRatio = Math.max(0, Math.min(1, section.start / duration));
  const endRatio = Math.max(startRatio, Math.min(1, section.end / duration));
  const first = Math.floor(startRatio * (envelope.length - 1));
  const last = Math.ceil(endRatio * (envelope.length - 1));
  const points = [];
  for (let index = first; index <= Math.max(first, last); index += 1) {
    const ratio = envelope.length <= 1 ? 0 : index / (envelope.length - 1);
    if (ratio < startRatio - 0.001 || ratio > endRatio + 0.001) continue;
    const x = ratio * width;
    const y = height - 4 - (envelope[index] || 0) * (height - 12);
    points.push([x, y]);
  }
  if (points.length < 2) {
    points.push([startRatio * width, height - 4], [endRatio * width, height - 4]);
  }
  const commands = [`M ${startRatio * width} ${height - 4}`];
  points.forEach(([x, y]) => commands.push(`L ${x} ${y}`));
  commands.push(`L ${endRatio * width} ${height - 4}`, "Z");
  return commands.join(" ");
}

async function renderHome(main, site, serial) {
  document.title = site.title || "个人作品集";
  await ensureRatings(site);
  if (serial !== state.routeSerial) return;
  const collections = getCollections(site);
  if (!collections.length) {
    main.append(createElement("p", "quiet", "还没有配置内容集合。"));
    return;
  }
  for (const collection of collections) {
    const block = createElement("section", "collection-block");
    const heading = createElement("div", "section-heading");
    const title = createElement("h2");
    title.append(createAnchor(`#/${encodeURIComponent(collection.id)}`, collection.name || collection.id || "未命名集合"));
    heading.append(title);
    block.append(heading);
    if (collection.description) block.append(createElement("p", "section-description", collection.description));
    if (collection.status === "planned") {
      block.append(createElement("p", "quiet", "还没有内容。"));
      main.append(block);
      continue;
    }
    const list = createElement("div", "content-list");
    try {
      const entries = (await loadCollectionEntries(collection)).slice(0, 5);
      const metas = await Promise.allSettled(entries.map((entry) => loadMeta(collection.id, entry.slug)));
      metas.forEach((result, index) => {
        if (result.status === "fulfilled") list.append(createContentRow(collection, entries[index], result.value, site));
      });
      if (!list.childElementCount) list.append(createElement("p", "quiet", "还没有内容。"));
    } catch {
      list.append(createElement("p", "quiet", "暂时无法读取这个集合的内容。"));
    }
    block.append(list);
    main.append(block);
  }
}

async function renderCollection(main, site, collection, serial) {
  document.title = `${collection.name || collection.id || "内容集合"} · ${site.title || "个人作品集"}`;
  await ensureRatings(site);
  if (serial !== state.routeSerial) return;
  const header = createElement("header", "collection-header");
  header.append(createElement("h2", "collection-title", collection.name || collection.id || "未命名集合"));
  if (collection.description) header.append(createElement("p", "collection-description", collection.description));
  main.append(header);
  if (collection.status === "planned") {
    main.append(createElement("p", "quiet", "这里还没有内容，之后会放在这里。"));
    return;
  }
  const list = createElement("div", "content-list");
  try {
    const entries = await loadCollectionEntries(collection);
    const metas = await Promise.allSettled(entries.map((entry) => loadMeta(collection.id, entry.slug)));
    metas.forEach((result, index) => {
      if (result.status === "fulfilled") list.append(createContentRow(collection, entries[index], result.value, site));
    });
    if (!list.childElementCount) list.append(createElement("p", "quiet", "还没有内容。"));
  } catch {
    list.append(createElement("p", "quiet", "暂时无法读取这个集合的内容。"));
  }
  main.append(list);
}

function createContentHeader(meta, slug, site, collectionId) {
  const header = createElement("header", "content-header");
  header.append(createElement("h2", "content-title", displayTitle(meta, slug)));
  if (meta?.subtitle) header.append(createElement("p", "content-subtitle", meta.subtitle));
  if (meta?.description) header.append(createElement("p", "content-description", meta.description));
  const metaLine = createElement("div", "content-meta");
  const date = formatDate(meta?.date);
  if (date) metaLine.append(createElement("time", null, date));
  if (Array.isArray(meta?.tags) && meta.tags.length) {
    const tags = meta.tags.filter((tag) => typeof tag === "string" && tag.trim());
    if (tags.length) metaLine.append(createElement("span", null, tags.join("、")));
  }
  if (metaLine.childElementCount) header.append(metaLine);
  const rating = createRatingSummary(site, collectionId, slug, false);
  if (rating) header.append(rating);
  return header;
}

function appendSection(parent, title) {
  const section = createElement("section", "content-section");
  if (title) section.append(createElement("h2", null, title));
  parent.append(section);
  return section;
}

function fileInfo(meta, key) {
  const raw = isRecord(meta?.files?.[key]) ? meta.files[key] : meta?.files?.[key];
  const path = safeContentRelativePath(typeof raw === "string" ? raw : raw?.path);
  if (!path) return null;
  const size = finiteNumber(raw?.size) ?? finiteNumber(meta?.sizes?.[key]);
  return { path, size };
}

function formatFileSize(value) {
  if (value === null || value === undefined || value < 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size >= 10 || unit === 0 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
}

function fileUrl(collectionId, slug, path) {
  return contentPath(collectionId, slug, path);
}

function renderDownloads(section, meta, collectionId, slug, includeUnknown = false) {
  const labels = {
    audio: "MP3 音频",
    score: "PDF 曲谱",
    musicxml: "MusicXML",
    midi: "MIDI",
    mscz: "MuseScore 工程",
    script: "生成脚本"
  };
  const fileKeys = includeUnknown && isRecord(meta?.files) ? Object.keys(meta.files) : [];
  const keys = [...Object.keys(labels), ...fileKeys.filter((key) => !labels[key])];
  const list = createElement("div", "download-list");
  keys.forEach((key) => {
    const info = fileInfo(meta, key);
    if (!info) return;
    const item = createElement("div", "download-item");
    item.append(createAnchor(fileUrl(collectionId, slug, info.path), labels[key] || key));
    if (info.size !== null) item.append(createElement("span", "download-size", formatFileSize(info.size)));
    list.append(item);
  });
  if (list.childElementCount) section.append(list);
}

function renderLicense(section, meta, site) {
  const license = meta?.license || site.defaultLicense || site.license;
  if (!license) return;
  const copy = createElement("p", "license-copy");
  if (license === "CC BY-NC 4.0") {
    copy.append(createAnchor(OFFICIAL_LICENSE_URL, license));
    appendText(copy, "。署名、非商业使用。代码部分为 MIT。");
  } else {
    copy.textContent = `${license}。代码部分为 MIT。`;
  }
  section.append(copy);
}

function renderMusicInfo(section, meta) {
  const entries = [
    ["调性", meta?.key],
    ["速度", meta?.tempo],
    ["小节数", meta?.bars],
    ["乐器", Array.isArray(meta?.instruments) && meta.instruments.length ? meta.instruments.join("、") : null]
  ];
  const dl = createElement("dl", "info-grid");
  entries.forEach(([label, value]) => {
    if (value === undefined || value === null || value === "") return;
    const wrapper = createElement("div");
    wrapper.append(createElement("dt", null, label));
    wrapper.append(createElement("dd", null, typeof value === "number" ? formatInteger(value) : value));
    dl.append(wrapper);
  });
  if (dl.childElementCount) section.append(dl);
}

function renderCredits(section, credits) {
  if (!isRecord(credits)) return;
  const labels = { direction: "方向", generation: "生成与制谱", composer: "作曲", arrangement: "编配" };
  const dl = createElement("dl", "credits");
  Object.keys(labels).forEach((key) => {
    if (credits[key] === undefined || credits[key] === null || credits[key] === "") return;
    dl.append(createElement("dt", null, labels[key]));
    dl.append(createElement("dd", null, credits[key]));
  });
  if (dl.childElementCount) section.append(dl);
}

function tokenValue(value) {
  return finiteNumber(value);
}

function renderTokenTable(section, versions) {
  if (!Array.isArray(versions)) return;
  const validVersions = versions.filter((version) => isRecord(version));
  if (!validVersions.length) return;
  const table = createElement("table", "token-table");
  const caption = createElement("caption");
  caption.textContent = "Token 消耗";
  table.append(caption);
  const head = createElement("thead");
  const headRow = createElement("tr");
  ["版本", "输入", "输出", "总计"].forEach((label) => headRow.append(createElement("th", null, label)));
  head.append(headRow);
  table.append(head);
  const body = createElement("tbody");
  let inputSum = 0;
  let outputSum = 0;
  let totalSum = 0;
  let hasInput = false;
  let hasOutput = false;
  let hasTotal = false;
  validVersions.forEach((version) => {
    const input = tokenValue(version.input);
    const output = tokenValue(version.output);
    const explicitTotal = tokenValue(version.total);
    const total = explicitTotal === null && input !== null && output !== null ? input + output : explicitTotal;
    if (input !== null) { inputSum += input; hasInput = true; }
    if (output !== null) { outputSum += output; hasOutput = true; }
    if (total !== null) { totalSum += total; hasTotal = true; }
    const row = createElement("tr");
    const labelCell = createElement("td");
    appendText(labelCell, version.label || "未命名版本");
    if (version.date) appendText(labelCell, `（${version.date}）`);
    if (version.note) labelCell.append(createElement("span", "token-note", version.note));
    row.append(labelCell, createElement("td", null, formatInteger(input)), createElement("td", null, formatInteger(output)), createElement("td", null, formatInteger(total)));
    body.append(row);
    const barRow = createElement("tr");
    const barCell = createElement("td");
    barCell.colSpan = 4;
    if (input !== null || output !== null) {
      const bar = createElement("div", "token-bar");
      const denominator = Math.max((input || 0) + (output || 0), 1);
      const inputBar = createElement("span", "token-bar-input");
      inputBar.style.width = `${((input || 0) / denominator) * 100}%`;
      const outputBar = createElement("span", "token-bar-output");
      outputBar.style.width = `${((output || 0) / denominator) * 100}%`;
      bar.append(inputBar, outputBar);
      barCell.append(bar);
    }
    barRow.append(barCell);
    body.append(barRow);
  });
  const totalRow = createElement("tr");
  totalRow.append(createElement("th", null, "合计"));
  totalRow.append(createElement("th", null, hasInput ? formatInteger(inputSum) : "—"));
  totalRow.append(createElement("th", null, hasOutput ? formatInteger(outputSum) : "—"));
  totalRow.append(createElement("th", null, hasTotal ? formatInteger(totalSum) : "—"));
  body.append(totalRow);
  table.append(body);
  section.append(table);
}

function renderPromptDetails(section, meta, collectionId, slug) {
  const info = fileInfo(meta, "prompt");
  if (!info) return;
  const details = createElement("details", "prompt-details");
  const summary = createElement("summary", null, "完整提示词");
  details.append(summary);
  let loaded = false;
  details.addEventListener("toggle", async () => {
    if (!details.open || loaded) return;
    loaded = true;
    const pre = createElement("pre", null, "正在加载……");
    details.append(pre);
    try {
      pre.textContent = await fetchText(fileUrl(collectionId, slug, info.path));
    } catch {
      pre.textContent = "提示词暂时无法加载。";
    }
  });
  section.append(details);
}

function renderProcess(section, meta, collectionId, slug) {
  const before = section.childElementCount;
  renderCredits(section, meta?.credits);
  renderTokenTable(section, meta?.versions);
  renderPromptDetails(section, meta, collectionId, slug);
  if (section.childElementCount === before) section.remove();
}

function renderScore(section, meta, collectionId, slug) {
  const score = fileInfo(meta, "score");
  if (!score) return;
  const buttons = createElement("div", "button-row");
  const viewButton = createElement("button", "text-button", "查看曲谱");
  viewButton.type = "button";
  const download = createAnchor(fileUrl(collectionId, slug, score.path), "下载 PDF", "text-button");
  download.setAttribute("download", "");
  buttons.append(viewButton, download);
  section.append(buttons);
  let loaded = false;
  viewButton.addEventListener("click", () => {
    if (loaded) return;
    loaded = true;
    const object = document.createElement("object");
    object.className = "score-frame";
    object.type = "application/pdf";
    object.data = fileUrl(collectionId, slug, score.path);
    const fallback = createElement("p", null, "PDF 无法内嵌显示：");
    fallback.append(createAnchor(fileUrl(collectionId, slug, score.path), "下载 PDF"));
    object.append(fallback);
    object.addEventListener("error", () => {
      object.replaceChildren(fallback);
    });
    section.append(object);
    viewButton.disabled = true;
    viewButton.textContent = "曲谱已展开";
  });
}

function buildTimeline(meta, audio, duration, site) {
  const wrapper = createElement("div", "timeline-wrap");
  const timeline = createElement("div", "timeline");
  timeline.tabIndex = 0;
  timeline.setAttribute("role", "slider");
  timeline.setAttribute("aria-label", "播放进度");
  timeline.setAttribute("aria-valuemin", "0");
  timeline.setAttribute("aria-valuemax", String(duration));
  const svg = createElementNS("svg");
  svg.setAttribute("viewBox", "0 0 1000 78");
  svg.setAttribute("aria-hidden", "true");
  const defs = createElementNS("defs");
  const clip = createElementNS("clipPath");
  const clipId = `timeline-clip-${state.timelineId += 1}`;
  clip.setAttribute("id", clipId);
  const clipRect = createElementNS("rect");
  clipRect.setAttribute("x", "0");
  clipRect.setAttribute("y", "0");
  clipRect.setAttribute("width", "0");
  clipRect.setAttribute("height", "78");
  clip.append(clipRect);
  defs.append(clip);
  svg.append(defs);
  const envelope = Array.isArray(meta?.envelope) && meta.envelope.length ? meta.envelope.map((value) => Math.max(0, Math.min(1, finiteNumber(value) || 0))) : [0.2];
  const sections = normalizedSections(meta, duration);
  applySectionPalette(svg, site, meta);
  const groups = [];
  sections.forEach((section, index) => {
    const group = createElementNS("g");
    group.setAttribute("class", `timeline-segment ${sectionClass(section.color)}`);
    group.style.fill = `var(--section-${sectionKey(section.color)}, var(--section-neutral))`;
    const underlay = createElementNS("path");
    underlay.setAttribute("d", areaPathForTimeline(envelope, section, duration));
    underlay.setAttribute("opacity", "0.28");
    const played = createElementNS("path");
    played.setAttribute("d", areaPathForTimeline(envelope, section, duration));
    played.setAttribute("clip-path", `url(#${clipId})`);
    played.setAttribute("opacity", "1");
    group.append(underlay, played);
    svg.append(group);
    groups.push(group);
  });
  timeline.append(svg);
  const labels = createElement("div", "timeline-labels");
  labels.style.gridTemplateColumns = sections.map((section) => `${Math.max(section.end - section.start, 1)}fr`).join(" ");
  labels.style.setProperty("--section-count", String(sections.length));
  sections.forEach((section) => {
    const button = createElement("button", "section-button", section.name);
    button.type = "button";
    button.addEventListener("click", () => {
      audio.currentTime = Math.max(0, Math.min(duration, section.start));
      update();
    });
    labels.append(button);
  });
  wrapper.append(timeline, labels);
  const current = createElement("p", "current-section");
  current.setAttribute("aria-live", "polite");
  wrapper.append(current);

  function sectionAt(time) {
    return sections.findIndex((section, index) => time >= section.start && (time < section.end || index === sections.length - 1));
  }

  function update() {
    const currentDuration = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : duration;
    const time = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
    const ratio = currentDuration > 0 ? Math.max(0, Math.min(1, time / currentDuration)) : 0;
    clipRect.setAttribute("width", String(ratio * 1000));
    const active = sectionAt(time);
    groups.forEach((group, index) => group.classList.toggle("is-current", index === active && !audio.paused));
    labels.querySelectorAll(".section-button").forEach((button, index) => button.classList.toggle("is-current", index === active));
    timeline.setAttribute("aria-valuemax", String(currentDuration));
    timeline.setAttribute("aria-valuenow", String(Math.round(time * 10) / 10));
    timeline.setAttribute("aria-valuetext", `${formatDuration(time)}，${sections[active]?.name || "全曲"}`);
    current.textContent = `当前：${sections[active]?.name || "全曲"}`;
  }

  function seek(clientX) {
    const rect = timeline.getBoundingClientRect();
    const ratio = rect.width > 0 ? Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)) : 0;
    const currentDuration = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : duration;
    audio.currentTime = ratio * currentDuration;
    update();
  }

  let dragging = false;
  timeline.addEventListener("pointerdown", (event) => {
    dragging = true;
    timeline.setPointerCapture?.(event.pointerId);
    seek(event.clientX);
  });
  timeline.addEventListener("pointermove", (event) => {
    if (dragging) seek(event.clientX);
  });
  timeline.addEventListener("pointerup", () => { dragging = false; });
  timeline.addEventListener("pointercancel", () => { dragging = false; });
  timeline.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      const delta = event.key === "ArrowLeft" ? -5 : 5;
      const currentDuration = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : duration;
      audio.currentTime = Math.max(0, Math.min(currentDuration, (audio.currentTime || 0) + delta));
      update();
    } else if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      if (audio.paused) audio.play().catch(() => {});
      else audio.pause();
    }
  });
  ["timeupdate", "loadedmetadata", "durationchange", "play", "pause", "ended"].forEach((eventName) => audio.addEventListener(eventName, update));
  update();
  return { node: wrapper, update };
}

function areaPathForTimeline(envelope, section, duration) {
  const normalized = { ...section, start: Math.max(0, section.start), end: Math.min(duration, section.end) };
  return areaPath(envelope, normalized, 1000, 78, duration).replaceAll("NaN", "0");
}

function renderPlayer(section, meta, collectionId, slug, site) {
  const audioInfo = fileInfo(meta, "audio");
  if (!audioInfo) return;
  const audio = document.createElement("audio");
  audio.className = "audio-element";
  audio.preload = "metadata";
  audio.src = fileUrl(collectionId, slug, audioInfo.path);
  audio.setAttribute("aria-label", `${displayTitle(meta, slug)} 音频`);
  const controls = createElement("div", "player-controls");
  const playButton = createElement("button", "control-button", "播放");
  playButton.type = "button";
  playButton.setAttribute("aria-label", "播放");
  const duration = Math.max(0, finiteNumber(meta?.duration) || 0);
  const time = createElement("span", "time-display", `0:00 / ${formatDuration(duration) || "0:00"}`);
  playButton.addEventListener("click", () => {
    if (audio.paused) audio.play().catch(() => {});
    else audio.pause();
  });
  const setButtonState = () => {
    playButton.textContent = audio.paused ? "播放" : "暂停";
    playButton.setAttribute("aria-label", audio.paused ? "播放" : "暂停");
  };
  audio.addEventListener("play", setButtonState);
  audio.addEventListener("pause", setButtonState);
  audio.addEventListener("ended", setButtonState);
  audio.addEventListener("timeupdate", () => {
    const total = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : duration;
    time.textContent = `${formatDuration(audio.currentTime) || "0:00"} / ${formatDuration(total) || "0:00"}`;
  });
  controls.append(playButton, time);
  section.append(audio, controls);
  const timeline = buildTimeline(meta, audio, duration || 1, site);
  section.append(timeline.node);
}

function createGiscusSection(site, collectionId, slug, kind) {
  const comments = site.comments;
  const ratings = comments?.ratings;
  const isRating = kind === "rating";
  if (isRating && !isRatingsConfigured(site)) return null;
  if (!isRating && !isCommentsConfigured(site)) return null;
  const section = createElement("section", "content-section");
  section.append(createElement("h2", null, isRating ? "评分" : "评论"));
  const copy = createElement("p", "comments-copy", isRating
    ? "评分使用 GitHub 账号登录。在评论框第一行写 0–5 的整数，例如 4，后面可以写评语。每个账号只计最新一条有效评分。"
    : "评论使用 GitHub 账号登录，内容存放在本仓库的 Discussions。");
  section.append(copy);
  const button = createElement("button", "text-button", isRating ? "我要评分" : "查看评论");
  button.type = "button";
  const host = createElement("div", "giscus-host");
  const status = createElement("p", "giscus-status");
  section.append(button, host, status);
  const config = isRating ? ratings : comments;
  const term = isRating ? `rating/${collectionId}/${slug}` : `${collectionId}/${slug}`;
  button.addEventListener("click", () => loadGiscus({ site, config, button, host, status, term, isRating }));
  return section;
}

function clearGiscusLoads() {
  Array.from(state.giscusLoads).forEach((cleanup) => cleanup());
  state.giscusLoads.clear();
}

function loadGiscus({ site, config, button, host, status, term, isRating }) {
  button.disabled = true;
  button.textContent = "加载中……";
  host.replaceChildren();
  status.textContent = "";
  const script = document.createElement("script");
  script.src = "https://giscus.app/client.js";
  script.async = true;
  script.crossOrigin = "anonymous";
  const values = {
    repo: site.comments.repo,
    repoId: site.comments.repoId,
    category: config.category,
    categoryId: config.categoryId,
    mapping: "specific",
    term,
    strict: "1",
    reactionsEnabled: isRating ? "0" : "1",
    emitMetadata: "0",
    inputPosition: "bottom",
    theme: actualTheme(),
    lang: site.comments.lang || "zh-CN"
  };
  Object.entries(values).forEach(([key, value]) => script.setAttribute(`data-${key.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`, value));
  let finished = false;
  let observer;
  let timer = 0;
  const cleanup = () => {
    observer?.disconnect();
    window.clearTimeout(timer);
    script.remove();
    state.giscusLoads.delete(cleanup);
  };
  const fail = () => {
    if (finished) return;
    finished = true;
    cleanup();
    if (!host.isConnected) return;
    button.disabled = false;
    button.textContent = "重试";
    status.textContent = isRating ? "评分暂时加载失败，可能是网络原因。" : "评论暂时加载失败，可能是网络原因。";
    if (site.comments.discussionsUrl) {
      status.append(document.createTextNode(" "));
      status.append(createAnchor(site.comments.discussionsUrl, "直接到 GitHub Discussions 查看"));
    }
  };
  const success = () => {
    if (finished) return;
    if (!host.isConnected) {
      finished = true;
      cleanup();
      return;
    }
    if (!host.querySelector("iframe.giscus-frame")) return;
    finished = true;
    cleanup();
    button.disabled = true;
    button.textContent = "已加载";
    status.textContent = "";
    syncGiscusTheme();
  };
  observer = new MutationObserver(success);
  observer.observe(host, { childList: true, subtree: true });
  state.giscusLoads.add(cleanup);
  script.addEventListener("error", fail, { once: true });
  host.append(script);
  timer = window.setTimeout(fail, 8000);
  success();
}

function renderRatingAndComments(main, site, collectionId, slug) {
  const ratingSection = createGiscusSection(site, collectionId, slug, "rating");
  if (ratingSection) main.append(ratingSection);
  const commentsSection = createGiscusSection(site, collectionId, slug, "comment");
  if (commentsSection) main.append(commentsSection);
}

async function renderMusicContent(main, site, collection, slug, meta, serial) {
  await ensureRatings(site);
  if (serial !== state.routeSerial) return;
  main.append(createContentHeader(meta, slug, site, collection.id));
  const player = appendSection(main, "试听");
  renderPlayer(player, meta, collection.id, slug, site);
  if (!player.childElementCount) player.remove();
  const info = appendSection(main, "曲目信息");
  renderMusicInfo(info, meta);
  if (!info.childElementCount) info.remove();
  const score = appendSection(main, "曲谱");
  renderScore(score, meta, collection.id, slug);
  if (!score.childElementCount) score.remove();
  const process = appendSection(main, "制作过程");
  renderProcess(process, meta, collection.id, slug);
  const downloads = appendSection(main, "下载");
  renderDownloads(downloads, meta, collection.id, slug);
  if (!downloads.childElementCount) downloads.remove();
  const license = appendSection(main, "协议");
  renderLicense(license, meta, site);
  if (!license.childElementCount) license.remove();
  renderRatingAndComments(main, site, collection.id, slug);
}

function isSafeLink(value) {
  if (typeof value !== "string" || !value.trim()) return false;
  const url = value.trim();
  if (/[\\\u0000-\u001f\u007f]/.test(url) || url.startsWith("//")) return false;
  return /^https?:\/\//i.test(url) || (!/^[a-z][a-z0-9+.-]*:/i.test(url) && !url.startsWith("/"));
}

function isSafeImage(value) {
  if (!isSafeLink(value)) return false;
  return !/^https?:\/\//i.test(value.trim()) && !value.trim().startsWith("//");
}

function normalizeMarkdownPath(value, baseFile = "index.md") {
  if (typeof value !== "string" || !value.trim()) return null;
  const raw = value.trim();
  if (raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\") || /[\u0000-\u001f\u007f]/.test(raw)) return null;
  const baseParts = String(baseFile).split("/");
  baseParts.pop();
  const parts = [...baseParts, ...raw.split("/")];
  const normalized = [];
  for (const part of parts) {
    if (!part || part === ".") continue;
    if (part === "..") {
      if (!normalized.length) return null;
      normalized.pop();
      continue;
    }
    normalized.push(part);
  }
  return normalized.length ? normalized.join("/") : null;
}

function resolveContentReference(collectionId, slug, value, image = false, baseFile = "index.md") {
  if (typeof value !== "string" || !value.trim()) return null;
  const raw = value.trim();
  if (/^https?:\/\//i.test(raw)) return image ? null : raw;
  if (raw.startsWith("#") || raw.startsWith("?")) return image ? null : raw;
  if (raw.startsWith("/") || raw.startsWith("//") || /^[a-z][a-z0-9+.-]*:/i.test(raw)) return null;
  const match = raw.match(/^([^?#]*)([?#].*)?$/);
  const path = normalizeMarkdownPath(match?.[1], baseFile);
  if (!path) return null;
  const resolved = contentPath(collectionId, slug, path);
  return resolved ? `${resolved}${match?.[2] || ""}` : null;
}

function appendInline(parent, source, context = null) {
  let rest = String(source || "");
  const pattern = /(!?)\[([^\]]+)\]\(([^)\s]+)(?:\s+["']([^"']*)["'])?\)|(`+)(.+?)\5|(\*\*|__)(.+?)\7|(\*|_)(.+?)\9/;
  while (rest) {
    const match = pattern.exec(rest);
    if (!match) {
      parent.append(document.createTextNode(rest));
      break;
    }
    if (match.index > 0) parent.append(document.createTextNode(rest.slice(0, match.index)));
    const [full, imageMark, label, target, alt, , codeText, strongMark, strongText, emphasisMark, emphasisText] = match;
    const resolvedTarget = context
      ? resolveContentReference(context.collectionId, context.slug, target, Boolean(imageMark), context.bodyFile)
      : null;
    if (imageMark && resolvedTarget && isSafeImage(target)) {
      const image = document.createElement("img");
      image.src = resolvedTarget;
      image.alt = alt || label;
      parent.append(image);
    } else if (imageMark) {
      parent.append(document.createTextNode(full));
    } else if (codeText !== undefined) {
      parent.append(createElement("code", null, codeText));
    } else if (strongText !== undefined) {
      const strong = createElement("strong");
      appendInline(strong, strongText, context);
      parent.append(strong);
    } else if (emphasisText !== undefined) {
      const emphasis = createElement("em");
      appendInline(emphasis, emphasisText, context);
      parent.append(emphasis);
    } else if ((resolvedTarget || isSafeLink(target)) && !imageMark) {
      const link = createAnchor(resolvedTarget || target, null);
      appendInline(link, label, context);
      parent.append(link);
    } else {
      parent.append(document.createTextNode(full));
    }
    rest = rest.slice(match.index + full.length);
  }
}

function renderMarkdown(container, markdown, context = null) {
  const lines = String(markdown || "").replace(/\r\n?/g, "\n").split("\n");
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) { index += 1; continue; }
    const fence = line.match(/^\s*```(?:[^`]*)$/);
    if (fence) {
      index += 1;
      const code = [];
      while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) { code.push(lines[index]); index += 1; }
      if (index < lines.length) index += 1;
      const pre = createElement("pre");
      pre.append(createElement("code", null, code.join("\n")));
      container.append(pre);
      continue;
    }
    const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*$/);
    if (heading) {
      const h = createElement(`h${heading[1].length}`);
      appendInline(h, heading[2], context);
      container.append(h);
      index += 1;
      continue;
    }
    if (/^\s*>/.test(line)) {
      const quote = createElement("blockquote");
      while (index < lines.length && /^\s*>/.test(lines[index])) {
        const paragraph = createElement("p");
        appendInline(paragraph, lines[index].replace(/^\s*>\s?/, ""), context);
        quote.append(paragraph);
        index += 1;
      }
      container.append(quote);
      continue;
    }
    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.]\s+(.+)$/);
    if (unordered || ordered) {
      const list = createElement(ordered ? "ol" : "ul");
      while (index < lines.length) {
        const itemMatch = lines[index].match(ordered ? /^\s*\d+[.]\s+(.+)$/ : /^\s*[-*+]\s+(.+)$/);
        if (!itemMatch) break;
        const item = createElement("li");
        appendInline(item, itemMatch[1], context);
        list.append(item);
        index += 1;
      }
      container.append(list);
      continue;
    }
    const paragraphLines = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^\s*(#{1,6})\s+/.test(lines[index]) && !/^\s*```/.test(lines[index]) && !/^\s*>/.test(lines[index]) && !/^\s*(?:[-*+]\s+|\d+[.]\s+)/.test(lines[index])) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    const paragraph = createElement("p");
    appendInline(paragraph, paragraphLines.join("\n"), context);
    container.append(paragraph);
  }
}

async function renderArticleContent(main, site, collection, slug, meta, serial) {
  await ensureRatings(site);
  if (serial !== state.routeSerial) return;
  main.append(createContentHeader(meta, slug, site, collection.id));
  const bodySection = appendSection(main, "正文");
  const articleBody = createElement("article", "article-body");
  bodySection.append(articleBody);
  const bodyFile = typeof meta?.body === "string" && meta.body.trim() ? meta.body : "index.md";
  try {
    const markdown = await fetchText(fileUrl(collection.id, slug, bodyFile));
    if (serial === state.routeSerial) {
      renderMarkdown(articleBody, markdown, { collectionId: collection.id, slug, bodyFile });
    }
  } catch {
    articleBody.append(createElement("p", "quiet", "正文暂时无法加载。"));
  }
  const downloads = appendSection(main, "下载");
  renderDownloads(downloads, meta, collection.id, slug, true);
  if (!downloads.childElementCount) downloads.remove();
  const license = appendSection(main, "协议");
  renderLicense(license, meta, site);
  if (!license.childElementCount) license.remove();
  renderRatingAndComments(main, site, collection.id, slug);
}

function renderGenericContent(main, site, collection, slug, meta) {
  main.append(createContentHeader(meta, slug, site, collection.id));
  const downloads = appendSection(main, "下载");
  renderDownloads(downloads, meta, collection.id, slug, true);
  if (!downloads.childElementCount) downloads.remove();
  const license = appendSection(main, "协议");
  renderLicense(license, meta, site);
  if (!license.childElementCount) license.remove();
}

async function renderContent(main, site, collection, slug, serial) {
  try {
    const meta = await loadMeta(collection.id, slug);
    if (serial !== state.routeSerial) return;
    applySectionPalette(main, site, meta);
    state.activeContentNode = main;
    state.activeContentMeta = meta;
    document.title = `${displayTitle(meta, slug)} · ${site.title || "个人作品集"}`;
    if (collection.type === "music") await renderMusicContent(main, site, collection, slug, meta, serial);
    else if (collection.type === "article") await renderArticleContent(main, site, collection, slug, meta, serial);
    else renderGenericContent(main, site, collection, slug, meta);
  } catch {
    if (serial !== state.routeSerial) return;
    document.title = `内容不存在 · ${site.title || "个人作品集"}`;
    renderError(main, "内容不存在", `找不到“${slug}”的内容，或它的 meta.json 无法读取。`);
  }
}

async function renderRoute() {
  clearGiscusLoads();
  const serial = state.routeSerial += 1;
  state.paletteTargets.clear();
  state.activeContentNode = null;
  state.activeContentMeta = null;
  const route = parseRoute();
  document.title = state.site?.title || "ctyx 的曲子";
  let site;
  try {
    state.sitePromise ||= fetchJson("site.json");
    site = await state.sitePromise;
    state.site = site;
    updateSiteMetadata(site);
    applyThemeTokens(site);
  } catch {
    if (serial !== state.routeSerial) return;
    app.replaceChildren();
    const main = createElement("main", "main-content");
    app.append(main);
    renderError(main, "页面无法加载", "站点配置读取失败。请确认使用 python -m http.server 访问，而不是直接双击 HTML 文件。", false);
    return;
  }
  if (serial !== state.routeSerial) return;
  const main = buildShell(site, route);
  if (route.type === "home") {
    await renderHome(main, site, serial);
    return;
  }
  if (route.type === "error") {
    document.title = `地址无效 · ${site.title || "个人作品集"}`;
    renderError(main, "地址无效", route.message);
    return;
  }
  const collection = findCollection(site, route.collectionId);
  if (!collection) {
    document.title = `集合不存在 · ${site.title || "个人作品集"}`;
    renderError(main, "集合不存在", `找不到“${route.collectionId}”这个内容集合。`);
    return;
  }
  if (route.type === "collection") {
    await renderCollection(main, site, collection, serial);
    return;
  }
  await renderContent(main, site, collection, route.slug, serial);
}

state.themeMode = readStoredTheme();
setTheme(state.themeMode);
if (window.matchMedia) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener?.("change", () => {
    if (state.themeMode === "system") {
      applyThemeTokens(state.site);
      refreshPaletteTargets();
      updateThemeButtons();
      syncGiscusTheme();
    }
  });
}
window.addEventListener("hashchange", renderRoute);
renderRoute();
