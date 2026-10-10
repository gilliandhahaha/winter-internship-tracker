#!/usr/bin/env python3
"""Weekly, API-key-based recruitment lead discovery; no access-controlled scraping.

This script collects search-result leads, NOT verified, open job positions.
Set SERPER_API_KEY only as an environment secret (GitHub Actions secret).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data" / "jobs.json"
REPORT = ROOT / "site" / "reports" / "latest.md"
TZ = ZoneInfo("Asia/Shanghai")
NOW = datetime.now(TZ)
TODAY = NOW.date().isoformat()

CITIES = ("天津", "北京")
ROLE_TERMS = {
    "供应链管理/分析": ("供应链", "供应链分析", "supply chain", "s&op", "供应链运营"),
    "物流规划/运营": ("物流", "物流规划", "物流运营", "配送", "logistics"),
    "采购/供应商管理": ("采购", "供应商", "sourcing", "procurement", "供应商管理"),
    "需求计划/生产计划": ("需求计划", "生产计划", "物料计划", "计划实习", "demand planning", "production planning", "物控", "pmc"),
}
SEARCH_KEYWORDS = {
    "供应链管理/分析": "供应链管理 供应链分析",
    "物流规划/运营": "物流规划 物流运营",
    "采购/供应商管理": "采购 供应商管理",
    "需求计划/生产计划": "需求计划 生产计划",
}
BLOCKED_HOSTS = ("zhihu.com", "bilibili.com", "xiaohongshu.com", "weibo.com", "douyin.com", "toutiao.com", "tieba.baidu.com", "baike.baidu.com", "wikipedia.org")
SOURCES = {
    "zhipin.com": "BOSS直聘",
    "shixiseng.com": "实习僧",
    "ncss.cn": "国家大学生就业服务平台",
    "yingjiesheng.com": "应届生求职网",
    "nowcoder.com": "牛客",
    "liepin.com": "猎聘",
    "51job.com": "前程无忧",
    "zhaopin.com": "智联招聘",
    "campus.51job.com": "校园招聘平台",
}
INTERNSHIP_WORDS = ("实习", "intern", "internship", "寒假实习")
NOISE_WORDS = ("培训班", "面试题", "面试经验", "笔试题", "求职攻略", "简历模板", "工资待遇", "薪酬查询", "话题讨论", "实习报告")


def load_data():
    try:
        obj = json.loads(DATA.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def save_data(obj):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    temp = DATA.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(DATA)


def canonical_url(url):
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    if parts.hostname.lower() in ("google.com", "www.google.com", "bing.com", "www.bing.com"):
        return None
    clean_query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    clean_query = [(k, v) for k, v in clean_query if not (k.startswith("utm_") or k in ("from", "spm", "track", "source"))]
    path = parts.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urllib.parse.urlencode(clean_query), ""))


def classify_link(url):
    """Conservative URL-based hint, NOT an HTTP/page-content verification.

    detail: URL follows a known single-position pattern.
    entry:  URL looks like a result list, keyword search or generic career entry.
    unknown: cannot decide without opening the page.
    """
    if not url:
        return "unknown"
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    path = urllib.parse.unquote(parts.path).lower().rstrip("/") or "/"
    query = {k.lower(): v for k, v in urllib.parse.parse_qs(parts.query).items()}
    detail_keys = ("jobid", "job_id", "jobidlist", "jobno", "positionid", "position_id", "postingid", "recruitid", "jobcode", "jk")
    if any(k in query and any(value.strip() for value in query[k]) for k in detail_keys):
        return "detail"

    # Known platform-specific single-posting URLs. These patterns can change.
    if re.search(r"/job_detail/[^/]+", path):
        return "detail"  # BOSS 直聘等
    if (host == "shixiseng.com" or host.endswith(".shixiseng.com")) and re.search(r"/intern/[^/]+", path):
        return "detail"
    if re.search(r"/positions?/[\w-]{5,}/detail(?:$|/)", path):
        return "detail"
    if re.search(r"/(?:jobdetails?|jobs?/detail|positions?/detail|position_detail|vacanc(?:y|ies)/detail)/[^/]+", path):
        return "detail"
    if re.search(r"/(?:job|jobs|position|positions|posting|postings|vacancy|vacancies)/[\w-]{5,}(?:\.s?html)?$", path):
        return "detail"
    if (host.endswith(".lever.co") or host.endswith(".smartrecruiters.com")) and len([p for p in path.split('/') if p]) >= 2 and not any(x in path for x in ('/search','/all-jobs')):
        return "detail"
    if re.search(r"/(?:viewjob|jobdetail|job-details)(?:$|/)", path) and (any(k in query for k in ('id','jobid','jk','job_id')) or len(path.split('/')) > 2):
        return "detail"
    if host.endswith(".51job.com") and re.search(r"/\d{6,}\.html$", path):
        return "detail"

    # Search/list pages are never single postings, even when their search
    # snippet mentions a specific role and city.
    search_params = ("q", "query", "keyword", "keywords", "search", "searchkey", "searchtext", "wd", "kw")
    if any(k in query for k in search_params):
        return "entry"
    if re.search(r"/(?:search|jobs?-search|search-jobs|jobsearch|joblist|job-list|zhaopin|sou|list|positions-list|job-recommend)(?:/|$|\.)", path):
        return "entry"
    if path in ("/", "/jobs", "/job", "/intern", "/positions", "/position", "/careers", "/career", "/recruit", "/recruitment", "/campus"):
        return "entry"
    if path.endswith(("/jobs", "/positions", "/careers", "/recruitment", "/search")):
        return "entry"
    return "unknown"


def host_name(url):
    return urllib.parse.urlsplit(url).hostname or ""


def source_type(host):
    for domain, label in SOURCES.items():
        if host == domain or host.endswith("." + domain):
            return "招聘平台", label
    if any(x in host for x in ("jobs.", "careers.", "career.", "campus.", "join.", "recruit.")):
        return "企业招聘网站", host
    return "其他来源/待确认", host


def short_text(txt, limit=400):
    txt = re.sub(r"\s+", " ", str(txt or "")).strip()
    return txt[:limit]


def title_company(raw):
    # Search titles frequently include 'job | company' but exact company names
    # cannot be inferred with confidence. Display the raw title rather than fabricate.
    return short_text(raw, 130), "企业待确认"


def role_tag(text):
    text = text.lower()
    scores = {name: sum(1 for term in keys if term in text) for name, keys in ROLE_TERMS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "其他相关岗位"


def city_tag(text, search_city):
    # City is extracted from result text where possible; a city in the search query
    # alone is not evidence that the position is located there.
    cities = [c for c in CITIES if c in text]
    if len(cities) == 1:
        return cities[0]
    return "地点待确认"


def graduation_tag(text):
    if re.search(r"2028\s*(?:届|年毕业)", text):
        return "提及2028届（待原文核实）"
    if re.search(r"202[0-7]\s*(?:届|年毕业)", text):
        return "提及其他毕业届别（请仔细核对）"
    return "未明确（待核实）"


def candidate_from_result(item, query_city):
    title = short_text(item.get("title", ""), 150)
    snippet = short_text(item.get("snippet", ""), 460)
    combined = title + " " + snippet
    low = combined.lower()
    if not title or any(w in low for w in NOISE_WORDS):
        return None
    if not any(term in low for terms in ROLE_TERMS.values() for term in terms):
        return None
    if not any(w in low for w in INTERNSHIP_WORDS):
        return None
    url = canonical_url(item.get("link", ""))
    if not url:
        return None
    host = host_name(url)
    if any(host == blocked or host.endswith("." + blocked) for blocked in BLOCKED_HOSTS):
        return None
    channel, source = source_type(host)
    formatted_title, company = title_company(title)
    link_type = classify_link(url)
    rec = {
        "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
        "title": formatted_title,
        "company": company,
        "city": city_tag(combined, query_city),
        "search_city": query_city,
        "category": role_tag(combined),
        "industry": "待确认",
        "url": url,
        "link_type": link_type,
        "source": source,
        "channel": channel,
        "snippet": snippet,
        "first_seen": TODAY,
        "last_seen": TODAY,
        "deadline": None,
        "published_at": None,
        "graduation_requirement": graduation_tag(combined),
        "work_days": "摘要提及每周5天（待核验）" if re.search(r"(?:每周|一周|每星期)\s*5\s*天|5\s*天[/／]周|每周五天", combined) else "待确认",
        "duration": "待确认",
        "availability": "待核验",
        "verification": ("URL疑似指向单个岗位；未核实正文和招聘状态" if link_type == "detail" else "招聘搜索/列表入口，不是单个岗位详情" if link_type == "entry" else "链接类型待确认，请打开核对"),
        "search_date_text": short_text(item.get("date", ""), 40),
    }
    return rec


def search(q, key):
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps({"q": q, "gl": "cn", "hl": "zh-cn", "num": 10}).encode("utf-8"),
        headers={"X-API-KEY": key, "Content-Type": "application/json", "User-Agent": "InternshipTracker/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=28) as res:
        return json.loads(res.read().decode("utf-8")).get("organic", [])


def build_queries():
    result = []
    for city in CITIES:
        for role in SEARCH_KEYWORDS.values():
            result.append((city, f"{city} {role} 实习生 招聘 职位详情"))
        # Restrict some searches to known direct-job URL patterns. Search
        # engine indexing and platform login rules can still yield zero results.
        result.append((city, f"{city} 供应链 采购 实习 site:zhipin.com/job_detail/"))
        result.append((city, f"{city} 物流 生产计划 实习 site:shixiseng.com/intern/"))
        result.append((city, f"{city} 2027 寒假实习 2028届 供应链 物流 采购 招聘"))
    return result


def build_report(data, old_ids):
    jobs = data.get("jobs", [])
    newly = [j for j in jobs if j.get("id") not in old_ids and j.get("last_seen") == TODAY]
    fresh = [j for j in jobs if j.get("last_seen") == TODAY]
    likely_detail = [j for j in newly if j.get("link_type") == "detail"]
    other = [j for j in newly if j.get("link_type") != "detail"]
    lines = [
        "# 寒假实习招聘线索 · 每周周报", "",
        f"- 检索日期：{NOW.strftime('%Y-%m-%d %H:%M')}（北京时间）",
        "- 定向城市：天津优先、北京可接受",
        "- 目标：2026年12月争取面试，2027年寒假实习约3个月，每周5天；2028年6月毕业",
        f"- 本次成功查询：{data.get('search_queries', 0)} 条",
        f"- 本次检索发现线索：{len(fresh)} 条；其中URL疑似岗位详情：{sum(j.get('link_type') == 'detail' for j in fresh)} 条",
        f"- 新发现的疑似岗位详情：{len(likely_detail)} 条",
        f"- 新发现的招聘入口及待确认链接：{len(other)} 条", "",
        "> 重要：岗位详情仅基于网址结构推测，**未访问原始页面逐条核实**；不能保证链接有效、岗位真实在招、条件符合或可投递。", "",
    ]
    for header, records in (("## 新增：疑似单个岗位详情页", likely_detail), ("## 新增：招聘入口与链接待确认", other)):
        lines.extend((header, ""))
        if not records:
            lines.append("本次暂无。\n")
        for i, j in enumerate(records, 1):
            lines.extend((
                f"### {i}. {j.get('title', '未命名线索').replace('#','')}",
                f"- 链接分类：{j.get('link_type', 'unknown')}（仅基于网址规则）",
                f"- 城市判断：{j.get('city', '待确认')}（搜索城市：{j.get('search_city', '待确认')}）",
                f"- 职能类别：{j.get('category', '待确认')}",
                f"- 来源：{j.get('source', '待确认')}；在招状态：待核验",
                f"- 原始网址：{j.get('url', '')}",
                f"- 搜索摘要：{j.get('snippet') or '暂无'}", "",
            ))
    lines.extend(("## 使用提醒", "", "- 岗位优先打开详情链接，但仍需确认是否有效及是否要求登录。", "- 其他招聘入口没有被伪装成岗位详情，可以在网站中切换查看。", "- 收藏和投递进度只存在当前浏览器，建议定期导出。", ""))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def run():
    data = load_data()
    data.setdefault("jobs", [])
    key = os.getenv("SERPER_API_KEY", "").strip()
    if not key:
        print("SERPER_API_KEY is missing; keeping existing dataset unchanged.")
        return 0
    seen = {j["id"]: j for j in data["jobs"] if j.get("id")}
    old_ids = set(seen)
    queries = build_queries()
    done = 0
    failures = 0
    count_result = 0
    for city, query in queries:
        try:
            results = search(query, key)
            done += 1
            count_result += len(results)
            for item in results:
                candidate = candidate_from_result(item, city)
                if not candidate:
                    continue
                jid = candidate["id"]
                if jid in seen:
                    candidate["first_seen"] = seen[jid].get("first_seen", TODAY)
                seen[jid] = candidate
            time.sleep(0.25)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as e:
            failures += 1
            print(f"Search failed ({city}): {type(e).__name__} {e}", file=sys.stderr)
    if done == 0:
        print("All searches failed; previous data preserved, job update skipped.", file=sys.stderr)
        return 1
    # Upgrade existing V1.1 records as well as newly discovered records.
    for j in seen.values():
        j["link_type"] = classify_link(j.get("url", ""))
        if j.get("company") == "招聘页面待确认":
            j["company"] = "企业待确认"
        if j["link_type"] == "entry":
            j["verification"] = "招聘搜索/列表入口，不代表某个具体岗位"
        elif j["link_type"] == "unknown":
            j["verification"] = "无法根据URL判断是否为岗位详情，需人工核对"
        else:
            j["verification"] = "URL疑似岗位详情；招聘状态及岗位要求尚未核实"

    # Previous leads are retained for history and clearly marked as not re-found.
    for j in seen.values():
        if j.get("last_seen") != TODAY:
            try:
                days = (NOW.date() - datetime.strptime(j["last_seen"], "%Y-%m-%d").date()).days
            except (KeyError, ValueError):
                days = 99
            j["availability"] = "历史线索" if days >= 28 else "本次未检索到"
            j["verification"] = "未能从近期搜索确认招聘状态，请点击原始链接核实"
    order = {"天津": 0, "北京": 1, "地点待确认": 2}
    jobs = sorted(seen.values(), key=lambda j: (j.get("last_seen", ""), -order.get(j["city"], 9), j["title"]), reverse=True)[:600]
    # Sort newest first and Tianjin first among same-date results.
    jobs.sort(key=lambda j: (-int(j.get("last_seen", TODAY).replace("-", "")), order.get(j.get("city"), 9), j.get("title", "")))
    output = {
        "schema_version": 2,
        "last_updated": NOW.isoformat(timespec="seconds"),
        "last_run": NOW.isoformat(timespec="seconds"),
        "collection_status": "partial_success" if failures else "success",
        "collection_note": f"搜索返回{count_result}条结果；成功查询{done}/{len(queries)}。已按网址区分疑似详情和招聘入口，但未经正文核验。",
        "search_queries": done,
        "jobs": jobs,
    }
    save_data(output)
    build_report(output, old_ids)
    print(f"Saved {len(jobs)} leads ({sum(j.get('link_type') == 'detail' for j in jobs)} probable detail links; {len(jobs)-len(old_ids)} new), successful searches {done}/{len(queries)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
