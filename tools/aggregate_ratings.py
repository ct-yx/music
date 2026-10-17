#!/usr/bin/env python3
"""Aggregate valid first-line ratings from a GitHub Discussions category."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GRAPHQL_URL = "https://api.github.com/graphql"
TERM_PATTERN = re.compile(r"^rating/([^/]+)/([^/]+)$")
SCORE_PATTERN = re.compile(r"^(?:评分\s*[:：]\s*)?([0-5])\s*(?:/\s*5|分)?\s*$")
DISCUSSIONS_QUERY = """
query($owner: String!, $name: String!, $categoryId: ID!, $after: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: 100, after: $after, categoryId: $categoryId) {
      nodes { id title }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""
COMMENTS_QUERY = """
query($discussionId: ID!, $after: String) {
  node(id: $discussionId) {
    ... on Discussion {
      comments(first: 100, after: $after) {
        nodes { body updatedAt author { login } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


class AggregationError(Exception):
    pass


def parse_repo(value: object) -> tuple[str, str]:
    if not isinstance(value, str):
        raise AggregationError("site.json 的 comments.repo 必须填写 owner/repository")
    match = re.fullmatch(r"(?:https://github\.com/)?([^/]+)/([^/]+?)(?:\.git)?/?", value.strip())
    if not match or not all(match.groups()):
        raise AggregationError("site.json 的 comments.repo 必须填写 owner/repository")
    return match.group(1), match.group(2)


def graphql(query: str, variables: dict[str, object], token: str) -> dict[str, object]:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ctyx-ratings-aggregator",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AggregationError(f"GitHub GraphQL 请求失败：{error}") from error
    if not isinstance(payload, dict) or payload.get("errors"):
        raise AggregationError(f"GitHub GraphQL 返回错误：{payload.get('errors') if isinstance(payload, dict) else '无效响应'}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise AggregationError("GitHub GraphQL 响应缺少 data")
    return data


def discussion_pages(owner: str, repo: str, category_id: str, token: str) -> list[dict[str, object]]:
    discussions: list[dict[str, object]] = []
    after = None
    while True:
        data = graphql(DISCUSSIONS_QUERY, {"owner": owner, "name": repo, "categoryId": category_id, "after": after}, token)
        repository = data.get("repository")
        connection = repository.get("discussions") if isinstance(repository, dict) else None
        if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
            raise AggregationError("无法读取评分分类的讨论列表")
        discussions.extend(node for node in connection["nodes"] if isinstance(node, dict))
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict) or not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            raise AggregationError("讨论分页缺少 endCursor")
    return discussions


def comment_pages(discussion_id: str, token: str) -> list[dict[str, object]]:
    comments: list[dict[str, object]] = []
    after = None
    while True:
        data = graphql(COMMENTS_QUERY, {"discussionId": discussion_id, "after": after}, token)
        node = data.get("node")
        connection = node.get("comments") if isinstance(node, dict) else None
        if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
            raise AggregationError(f"无法读取讨论 {discussion_id} 的一级评论")
        comments.extend(comment for comment in connection["nodes"] if isinstance(comment, dict))
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict) or not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            raise AggregationError("评论分页缺少 endCursor")
    return comments


def fixture_discussions(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AggregationError(f"无法读取 fixture：{error}") from error
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("discussions"), list):
        return [item for item in payload["discussions"] if isinstance(item, dict)]
    raise AggregationError("fixture 格式应为讨论数组或 {\"discussions\": [...]} ")


def fixture_comments(discussion: dict[str, object]) -> list[dict[str, object]]:
    comments = discussion.get("comments", [])
    if isinstance(comments, dict):
        comments = comments.get("nodes", [])
    return [item for item in comments if isinstance(item, dict)] if isinstance(comments, list) else []


def parse_score(body: object) -> int | None:
    if not isinstance(body, str):
        return None
    first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
    match = SCORE_PATTERN.fullmatch(first_line)
    return int(match.group(1)) if match else None


def parse_updated_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def collect_votes(
    discussions: list[dict[str, object]],
    comments_for: object,
    excluded_authors: set[str],
    owner: str,
) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, tuple[datetime, int]]] = {}
    for discussion in discussions:
        title = discussion.get("title")
        match = TERM_PATTERN.fullmatch(title) if isinstance(title, str) else None
        if not match:
            continue
        key = f"{match.group(1)}/{match.group(2)}"
        comments = comments_for(discussion)
        for comment in comments:
            author = comment.get("author")
            login = author.get("login") if isinstance(author, dict) else None
            if not isinstance(login, str) or not login.strip():
                continue
            login = login.strip()
            if login.casefold() == owner.casefold() or login.casefold() in excluded_authors:
                continue
            score = parse_score(comment.get("body"))
            updated = parse_updated_at(comment.get("updatedAt"))
            if score is None or updated is None:
                continue
            item_votes = latest.setdefault(key, {})
            current = item_votes.get(login.casefold())
            if current is None or updated > current[0]:
                item_votes[login.casefold()] = (updated, score)
    result: dict[str, dict[str, object]] = {}
    for key, votes in latest.items():
        scores = [updated_score for _, updated_score in votes.values()]
        if not scores:
            continue
        distribution = [0] * 6
        for score in scores:
            distribution[score] += 1
        result[key] = {
            "count": len(scores),
            "average": round(sum(scores) / len(scores) + 1e-12, 2),
            "distribution": distribution,
        }
    return result


def load_site(path: Path) -> dict[str, object]:
    try:
        site = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AggregationError(f"无法读取 site.json：{error}") from error
    if not isinstance(site, dict):
        raise AggregationError("site.json 顶层必须是对象")
    comments = site.get("comments")
    ratings = comments.get("ratings") if isinstance(comments, dict) else None
    if not isinstance(ratings, dict):
        raise AggregationError("site.json 缺少 comments.ratings")
    return {"site": site, "comments": comments, "ratings": ratings}


def build_output(site_path: Path, fixture: Path | None, token: str | None) -> dict[str, object]:
    configuration = load_site(site_path)
    site = configuration["site"]
    comments = configuration["comments"]
    ratings = configuration["ratings"]
    owner, repo = parse_repo(comments.get("repo"))
    category_id = ratings.get("categoryId")
    if not isinstance(category_id, str) or not category_id.strip():
        raise AggregationError("site.json 的 comments.ratings.categoryId 不能为空")
    excluded = ratings.get("excludeAuthors", [])
    if not isinstance(excluded, list) or any(not isinstance(name, str) for name in excluded):
        raise AggregationError("comments.ratings.excludeAuthors 必须是字符串数组")
    excluded_authors = {name.casefold() for name in excluded}
    if fixture:
        discussions = fixture_discussions(fixture)
        comments_for = fixture_comments
    else:
        if not token:
            raise AggregationError("请通过 GITHUB_TOKEN 环境变量提供 GitHub token")
        discussions = discussion_pages(owner, repo, category_id.strip(), token)
        comment_cache: dict[str, list[dict[str, object]]] = {}

        def comments_for(discussion: dict[str, object]) -> list[dict[str, object]]:
            discussion_id = discussion.get("id")
            if not isinstance(discussion_id, str) or not discussion_id:
                raise AggregationError("讨论缺少 GraphQL id")
            if discussion_id not in comment_cache:
                comment_cache[discussion_id] = comment_pages(discussion_id, token)
            return comment_cache[discussion_id]

    items = collect_votes(discussions, comments_for, excluded_authors, owner)
    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "items": items,
    }


def write_atomically(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_existing(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="从 GitHub Discussions 汇总评分")
    parser.add_argument("--site", type=Path, default=Path("site.json"), help="站点配置路径")
    parser.add_argument("--fixture", type=Path, help="从本地 fixture JSON 读取讨论，跳过 GitHub API")
    parser.add_argument("--output", type=Path, default=Path("data/ratings.json"), help="输出 JSON 路径")
    args = parser.parse_args()
    try:
        output = build_output(args.site, args.fixture, os.environ.get("GITHUB_TOKEN"))
        existing = read_existing(args.output)
        if isinstance(existing, dict) and existing.get("items") == output.get("items"):
            previous_time = existing.get("updatedAt")
            if isinstance(previous_time, str) and previous_time:
                output["updatedAt"] = previous_time
        if existing == output:
            print(f"评分没有变化，保留 {args.output}")
            return 0
        write_atomically(args.output, output)
    except (AggregationError, OSError) as error:
        print(f"评分汇总失败：{error}", file=sys.stderr)
        return 1
    print(f"已更新 {args.output}（{len(output['items'])} 条内容评分）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
