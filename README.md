# travel-guide · 旅游攻略 Skill

把“想去”变成同行者能执行的计划：知道从哪里出发、下一步去哪、哪些事先预约、何时必须返程，以及计划变化时先删什么。默认在明确要求完整攻略时，交付可分享的**单文件 HTML**。

> A reusable Agent Skill that turns scattered travel requests into an executable itinerary — with verified facts, real maps and licensed photos — and delivers a single-file, phone-and-desktop-friendly HTML guide.

## 输出契约

| 等级 | 适用 | 交付内容 |
| --- | --- | --- |
| `quick` | 简单推荐、单段路线或单个事实 | 通常直接在对话中回答，不启动完整流程 |
| `standard` | 可执行行程 | 路线、时间线、关键地点、必要地图、来源、预算与替代方案 |
| `rich` | 给同行者分享的详细图文 | 在 standard 之上逐点补足现场观察、抵达参照、停留 / 离开条件、停车或换乘、拍照位置，以及每个核心地点至少一张主题核实、许可清楚的真实实景图 |

完整度按**核心地点覆盖率**判断，不按总字数判断。“随便逛”表示节奏宽松，“半日 / 一日”表示时间边界，都不改变用户已明确指定的 `rich` 成品。

## 六阶段流程

| 阶段 | 做什么 | 过门条件 |
| --- | --- | --- |
| 1 出行条件 | 建立本次 brief 与输出契约 | 已确认与待确认分开，输出契约写明 |
| 2 可行性 | 先定骨架再填景点 | 无时段冲突、无折返、不靠跳过饭赶车 |
| 3 资料核验 | 给会影响决定的事实找证据 | 关键操作事实可回溯，未核实项降级 |
| 4 可执行攻略 | 写清下一步，不只写景点名 | 读者能按顺序出行，易混项已区分 |
| 5 HTML | 把内容变成现场工具 | 离线可读，路线不变量与覆盖率达契约 |
| 6 验收交付 | 内容复核 + 浏览器验收 | 静态、内容、浏览器分别验证过 |

## 核心规则

- **状态统一**：事实记为 `verified` / `estimated` / `unknown` / `login_required`，记录查阅时间与停止原因。
- **有界核实**：换一次查询表达、来源类别与访问通道后仍不确定就停下，不用低质量页面“冲淡”未知。登录墙不等于“未搜索”。
- **不伪装动态状态**：日期未定时，不写死车次、余票、预约空位或临时营业。
- **地图真实**：中国内地未指定平台时，按 高德网页版 → 百度 → 腾讯 → OpenStreetMap + OSRM 依次降级，保留署名，不混用坐标系，不绕验证码。
- **照片可追溯**：`rich` 的每个核心地点需原文件页、作者、许可与 `subject_verified`；地图、菜单截图和通用城市天际线不算实景覆盖。找不到合法照片时保留地点并显示缺口，不用 AI 图顶替。
- **更新防缩水**：更新旧攻略前先做 section inventory，除用户要求外不得无声减少内容。
- **只做攻略**：不代办订票、预约、付款、获取隐私或公开发布。

## 安装

把仓库克隆到你的技能目录：

```bash
git clone https://github.com/huangguozhao/travel-guide.git ~/.codex/skills/travel-guide
```

也可以只复制单侧（Windows PowerShell）：

```powershell
git clone https://github.com/huangguozhao/travel-guide.git "$env:USERPROFILE\.codex\skills\travel-guide"
```

若使用 DSH，会话工作区技能目录为 `<项目>\.dsh\skills\<name>\`，克隆进去即可被识别。

## 使用

```
使用 $travel-guide，做一份杭州出发的苏州两日游攻略，最后交付 HTML。
```

条件给得越具体，越少来回确认：

```
使用 $travel-guide。
我们两个人，周六从杭州东站出发，当天返回，
想看园林和老街，步行别超过 12 公里，预算每人 500 元。
需要预约、交通、真实地图、餐食，
最后做成手机和电脑都能看的 HTML。
```

## 目录结构

```
travel-guide/
├─ SKILL.md                        # 主流程：输出契约、六阶段、完成标准
├─ references/
│  ├─ evidence-and-maps.md         # 事实台账、有界核实、地图降级、实景覆盖
│  ├─ html-delivery.md             # 页面模块、单文件离线、交互条件、验收顺序
│  ├─ trip-data-and-quality.md     # trip-data.json 契约、路线不变量、门禁
│  └─ regression-cases.md          # A–F 六道回归题与评分维度
├─ scripts/
│  ├─ html_bundle.py               # pack：内嵌图片；audit：静态结构检查
│  ├─ validate_trip_data.py        # 数据契约 + HTML 渲染覆盖率
│  ├─ test_html_bundle.py
│  └─ test_validate_trip_data.py
├─ agents/openai.yaml              # 界面元数据（显示名、简介、默认提示词）
├─ LICENSE
└─ README.md
```

## 脚本

只依赖 Python 3 标准库，无网络请求，无第三方包。`standard` / `rich` 以工作目录中的 `trip-data.json` 为唯一可编辑真源。

```bash
# 1. 只验数据：地点、路段、路线、时间线、媒体、来源与替代方案
python scripts/validate_trip_data.py work/trip-data.json

# 2. 打包：把 {{asset:assets/map.png}} 换成 data URI
python scripts/html_bundle.py pack work/source.html --out outputs/攻略.html

# 3. 带 --html 复验：核心地点与受控媒体是否真的渲染出来
python scripts/validate_trip_data.py work/trip-data.json \
  --html outputs/攻略.html --report work/content-qa.json

# 4. 静态审计：重复 ID、断裂页内链接、外部渲染资源、损坏图片
python scripts/html_bundle.py audit outputs/攻略.html --report work/html-qa.json
```

约束与边界：

- `pack` 只接受资产根目录内的 PNG / JPEG / GIF / WebP，签名必须与扩展名一致，禁止跨目录与绝对路径；不发起网络请求。
- 发现已存在的输出时**不覆盖**，确认要更新本次文件才加 `--overwrite`；`--asset-root` 可改资产根目录。
- `validate_trip_data.py` 用 `data-stop-id` 与 `data-media-id` 核对页面是否真的渲染了每个核心地点与受控媒体。
- 静态检查**不证明**资料真实、许可有效、JS 正确或浏览器布局通过；浏览器验收仍需执行。

## 测试

```bash
cd scripts && python -m unittest discover -s . -p "test_*.py"
```

13 条测试覆盖资产内嵌与越权读取、图片签名校验、重复 ID、断裂页内链接、损坏图片、Rich 实景门禁、路段连续性与 HTML 覆盖率。`references/regression-cases.md` 另提供 6 道端到端回归题，用于 Skill 大改后的独立前向测试。

## 许可

[MIT](LICENSE)
