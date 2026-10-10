# OfferFlow：2027年寒假实习线索管理网站

这是一个**可部署的网页项目**，面向天津、北京的物流工程/供应链管理相关实习岗位。

- 城市：**天津优先，北京可接受**。
- 方向：供应链管理/分析、物流规划/运营、采购/供应商管理、需求计划/生产计划。
- 行业：不限。
- 背景：硕士研究生，**2028年6月毕业**；技能包括 Excel、Python、SQL、Maple、MATLAB、Photoshop 基础。
- 时间：目标**2026年12月面试**，**2027年寒假实习约3个月、**每周最多可到岗5天****；普通日常实习也收录，前提是时间和资格相符（网站提供人工核查清单）。
- 来源：企业官网、校园招聘、实习僧、BOSS直聘、国家大学生就业服务平台等公开搜索结果。

## 项目完成了什么？

| 能力 | 当前状态 |
|---|---|
| 可打开的响应式网页 | ✅ 已实现 |
| 天津/北京、四类岗位筛选及搜索 | ✅ 已实现 |
| 收藏、投递进度（待投递/已投递/笔试/面试/已结束） | ✅ 已实现（仅当前浏览器） |
| 手动保存岗位链接 | ✅ 已实现（仅当前浏览器） |
| 导出 CSV / Markdown | ✅ 已实现 |
| 每周搜索线索、去重、保留首次发现日期 | ✅ 后端代码已实现，**需自行配置 API 密钥并云端部署** |
| 每周自动生成最新 Markdown 周报 | ✅ 后端代码已实现，**需自行配置密钥并执行** |
| 电脑关机后继续运行 | ✅ 部署 GitHub Actions 后运行于云端，不依赖本机 |
| 逐条验证仍在招聘、毕业届别、可入职时长 | ⚠️ **尚未实现，需人工点击来源核实** |
| 跨设备同步收藏与申请记录 | ❌ 需要后续账户系统/数据库 |
| 自动搜集全部招聘网站的完整职位 | ❌ 不保证；不绕过登录、验证码与反爬机制 |
| 邮件/微信主动推送 | ❌ 当前为网站查看 + Markdown 周报，不自动发消息 |

## 先试用：不部署也能看页面

直接打开 `site/index.html` 即可预览页面。因为本地 `file://` 环境通常不能读取 JSON 数据，界面会启用明确标注的**虚构演示岗位**。页面可以试用搜索、城市筛选、收藏、投递管理和导出。

如需模拟真实部署的数据加载，请在项目根目录执行：

```bash
python -m http.server 8000 --directory site
```

然后在浏览器中打开 `http://localhost:8000/`。

注意：此时 `site/data/jobs.json` 为空，并不包含真实招聘。

## 让它每周日自动更新（GitHub Pages + GitHub Actions）

以下仅需初次配置，之后云端定时执行；**不需要你的电脑保持开机**。

### 1. 创建代码仓库

**详细的零基础点击步骤**请查看同一压缩包根目录下的 `零基础部署指南.md`。

1. 登录 [GitHub](https://github.com/)，创建一个新仓库，例如 `winter-internship-tracker`，建议先建立**公开仓库**以使用 GitHub Pages。不要放个人简历、手机号或其他私人资料，因为公开仓库和公开网页均可能被任何人查看。
2. 把此项目**整个文件夹内部的所有文件**上传到仓库根目录，包含隐藏的 `.github/workflows/weekly.yml`。默认主分支应为 `main`；否则要修改工作流中的分支名称。

### 2. 配置搜索接口（必要）

1. 在 [Serper](https://serper.dev/) 创建自己的搜索 API Key。该接口负责向公开网页发起搜索，不是向招聘平台非法爬取用户数据。
2. GitHub 仓库进入 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`。
3. 名字填写 **`SERPER_API_KEY`**，值填写你自己的 API Key。**切勿把密钥写入网页 JavaScript、JSON、代码或聊天记录，也不要提交到 GitHub。**
4. API 使用可能存在次数/费用限制；在服务商控制台了解当前计费规则。默认每周执行约 **10 次搜索请求**。

> 重要：**没有配置 API Key 时，定时工作流可以运行，但不会获取新的真实岗位。** 这不是无密钥的全自动搜索网站。

### 3. 开启 GitHub Pages

进入仓库 `Settings` → `Pages` → `Build and deployment`，把 `Source` 设为 **GitHub Actions**。

进入 `Actions` → `每周招聘更新并发布网站` → `Run workflow`，手动执行一次，确认采集与发布成功后，进入 `Settings` → `Pages` 查看网站地址。通常形式为：

`https://<GitHub用户名>.github.io/<仓库名>/`

### 4. 后续自动更新机制

- 默认每周日**北京时间10:27**，GitHub Actions 执行 `scripts/update_jobs.py`。
- 搜索天津、北京 × 四类方向（包括普通日常实习）+ 寒假实习补充查询，共**10条查询**。
- 通过 `https://google.serper.dev/search` 收集公开**搜索线索**（标题、摘要、来源链接）；筛选相关关键词、去重，保留首次发现时间。
- 生成 `site/data/jobs.json` 和 `site/reports/latest.md`，并发布 GitHub Pages。
- GitHub Actions 的定时执行可能延迟或偶尔不执行；公开仓库长期无活动时，GitHub 可能停用定时工作流（详见 GitHub 官方文档）。因此应不定期查看 Actions 运行记录和页面最后更新时间。

## 数据可靠性与限制

搜索 API **不能**替代招聘官方网站的岗位状态核验。本项目会把所有新收集结果标为“待核验”而不是“招聘中”。职位在天津/北京的判断仅来自标题或摘要；如果搜索结果没有清楚写地点，会标记“地点待确认”。毕业届别、实习时长、每周到岗天数及截止日期在未确认时一律标记“待确认”，不做虚构补齐。

- 不采用绕过 BOSS直聘、实习僧登录或验证码的技术。
- 平台搜索结果可能会有广告、过期职位、资讯文章或异地岗位；投递前必须到原页面核验。
- 数据在 GitHub Pages **公开可访问**，请勿录入私密求职信息。
- 收藏和进度保存在**当前浏览器的 localStorage**，不会因为云端更新而丢失（清除浏览器数据会丢失），也不会跨设备同步。
- 手动添加信息同样仅存储本地；可定期导出 CSV 和 Markdown 备份。
- 搜索 API 出错且全部查询失败时脚本会保留上次的数据并退出失败，而不会生成虚假的“更新成功”。

## 技术结构

```text
site/
  index.html            网页界面（HTML/CSS/JS）
  data/jobs.json        最新搜索线索数据（初始为空）
  reports/latest.md     最新Markdown周报
scripts/update_jobs.py  每周搜索、筛选去重、生成周报
.github/workflows/weekly.yml  GitHub Actions 定时采集及 Pages 发布
```

后续如需跨设备同步、自动邮件提醒、对接真实企业职位 API，需要增加账户、后端数据库或通知服务。

## 参考技术文档

- GitHub 定时事件：https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Pages 配置：https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- Serper 搜索接口：https://serper.dev/
