# 行程数据契约与内容门禁

只在 `standard`、`rich` HTML 或更新已有攻略时读取。目标不是把所有旅行都变成数据库，而是用一份小型真源阻止正文、地图、图片和来源互相漂移。

## 工作文件

在任务工作目录保存 `trip-data.json`；它不进入最终输出目录。HTML 可以由它生成，也可以人工编写后逐项对照，但路线顺序、媒体与来源只在这里编辑一次。

结构片段（为了突出字段关系，省略了被引用的 `museum`、`map-main` 和其他来源条目，不能直接作为验证样例运行）：

```json
{
  "schema_version": 1,
  "meta": {
    "title": "示例一日游",
    "detail": "rich",
    "audience": "两位同行朋友",
    "as_of": "2026-10-05",
    "required_sections": ["prepare", "timeline", "maps", "food", "fallbacks", "sources"]
  },
  "stops": [
    {
      "id": "old-town",
      "order": 1,
      "name": "老街",
      "role": "core",
      "summary": "现场会看到什么",
      "why_go": "为什么值得停",
      "arrival": "在哪停车或从哪里进入",
      "duration_min": 50,
      "leave_when": "何时离开",
      "map_ref": "map-main",
      "source_ids": ["src-tourism"],
      "media_ids": ["photo-old-town"]
    }
  ],
  "legs": [
    {
      "id": "leg-a-b",
      "from": "old-town",
      "to": "museum",
      "mode": "walk",
      "duration_min": 15,
      "status": "estimated",
      "source_ids": ["src-map"],
      "map_media_id": "map-main"
    }
  ],
  "routes": [
    {
      "id": "main",
      "label": "主路线",
      "primary": true,
      "stop_ids": ["old-town", "museum"],
      "leg_ids": ["leg-a-b"]
    }
  ],
  "timeline": [
    {"id": "t1", "label": "抵达老街", "stop_id": "old-town"}
  ],
  "media": [
    {
      "id": "photo-old-town",
      "type": "photo",
      "subject_stop_id": "old-town",
      "subject_verified": true,
      "source_url": "https://example.org/file-page",
      "source_platform": "公开图片页面",
      "author": "页面显示的作者（若有）",
      "usage": "裁切并压缩",
      "local_path": "assets/old-town.jpg",
      "caption": "老街实景"
    },
    {
      "id": "map-old-town-museum",
      "type": "map",
      "subject_stop_ids": ["old-town", "museum"],
      "source_url": "https://example.org/route",
      "local_path": "assets/route.jpg",
      "caption": "老街至博物馆路线"
    }
  ],
  "sources": [
    {
      "id": "src-tourism",
      "title": "官方旅游页面",
      "url": "https://example.org/place",
      "accessed_on": "2026-10-05",
      "status": "verified"
    }
  ],
  "fallbacks": [
    {
      "trigger": "下雨",
      "action": "删除露天段，保留室内馆",
      "remove_stop_ids": [],
      "preserve": "返程时间"
    }
  ]
}
```

单一地点的照片和局部图用 `subject_stop_id`；跨多个地点的总览或路线图用 `subject_stop_ids`。二者只能出现一个。真实照片必须绑定一个明确地点，不能用多地点数组模糊主题核实。

实际文件可以增加 `facts`、`food`、`facilities`、`budget`、`links`、`notes` 等字段；验证器忽略未知字段。不要复制同一事实到多个字段后分别维护。

## 路线不变量

1. `routes[].stop_ids` 是正文和地图编号的顺序。
2. 每两个连续地点恰有一个对应 `leg`；`leg_ids` 的数量必须比 `stop_ids` 少一，并按相同顺序连接。
3. 每个 `leg` 标明模式、时间、证据状态与来源；距离可选，但写了就必须是非负数。
4. `timeline` 至少覆盖每个核心地点一次。可选 / 备选地点不强塞进主路线。
5. 地图、照片和来源通过 ID 关联；不把坐标复制到另一个坐标系后直接使用。

## 核心地点门禁

`standard` 与 `rich` 的核心地点必须有 `summary / why_go / arrival / duration_min / leave_when / map_ref / source_ids`。HTML 中必须出现对应 `data-stop-id`。

`rich` 还要求每个核心地点至少一个 `type: photo`、`subject_verified: true` 的媒体；媒体必须有原页面、图注和本地资产或稳定 URL。平台、作者、拍摄时间、修改说明和许可字段有则记录，但缺失不阻止覆盖通过。HTML 中必须出现相应 `data-media-id`。地图、插画和通用氛围照不计入实景覆盖。

图片许可不明不是缺口，也不应触发“暂无可用授权实景图”。只有在公开来源中找不到能确认是该地点的真实照片时，才在页面显示图片缺口和建议搜索入口；默认不把地点错误的图片、通用氛围照或生成图算作合格实景媒体。

## 更新防缩水

更新已有攻略前，在工作笔记写 section inventory：章节 ID / 标题、核心地点 ID、媒体 ID、交互、用户填写字段、已核实事实。更新后比较数量和身份；只有用户明确删除或新事实证明失效的内容才能减少，并记录原因。

## 验证顺序

```text
python <skill-dir>/scripts/validate_trip_data.py trip-data.json
python <skill-dir>/scripts/html_bundle.py pack source.html --out final.html
python <skill-dir>/scripts/validate_trip_data.py trip-data.json --html final.html --report content-qa.json
python <skill-dir>/scripts/html_bundle.py audit final.html --report html-qa.json
```

验证器证明字段、引用和覆盖关系，不证明事实真实、照片地点判断正确、路线安全或浏览器布局正确。浏览器验收仍必须执行。

