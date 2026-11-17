# 山岚 · 内容订阅行为分群

将会员阅读档案转为可解释的行为群组，再制定带冻结成员清单的站内触达方案。

## 真实业务场景

模拟客户山岚内容社有会员运营组4人、编辑6人，试点240位订阅会员。原流程是运营人员导出 `山岚_会员周阅读_20261109.xlsx`，按阅读次数手工分组，再把名单和选题建议发给编辑。三个痛点是篇数与比例量纲混用、分群名单随工作簿修订漂移、内容建议无法追溯到当时的行为画像；手填档案还会被跨设备重叠阅读虚增活跃度。本项目用带编号的阅读事件在站内聚合出周口径，替代手工分组与名单归档，下游由编辑和运营负责人审阅内容主题、渠道假设及频次。

业务模块：阅读事件（接收/撤销/周汇总发布）、阅读档案（录入/完整字段修订）、特征选择（2–3维、k=2–6）、分群图谱（标准化散点、轮廓系数、原始单位画像、群成员）、触达方案（冻结名单、站内起草、负责人签核与导出）。核心实体为ReadEvent、WeeklySummary、Reader、Segment、Outreach；另有用户与审计记录。不连接真实会员系统或外发服务。

|角色|权限和页面|典型动作|
|---|---|---|
|admin|全部页面、审计和独占签核|核对内容主题和频次后签核|
|analyst|档案读写、分群任务、起草与导出|选择行为维度，形成群组内容草案|
|viewer|业务只读与导出，后端拒绝写操作|核对画像和冻结成员|

## 一天的工作剧本

1. 08:50 viewer查看SL-001至SL-240的周阅读篇数、完读率、夜读占比。
2. 09:00 analyst核对输入来自同一完整自然周，修订说明保留在note。
3. 09:05 接收事件 `EVT-…`（会员、文章、起止时间、完读比例），跨设备重叠时段在汇总里只计一次；异常事件登记撤销与依据。
4. 09:10 新增 `SL-241`，周阅读15篇、完读率0.8、夜读占比0.2。
5. 09:20 计算待计算汇总，核对时段合并与撤销依据后发布，档案差异列回到一致。
6. 09:30 在特征选择创建“11月会员阅读分群”，勾选全部3个维度、k=3。
7. 09:40 worker执行标准化KMeans，点击刷新查看轮廓系数和原始单位画像。
8. 09:50 点击群组切换成员表，核对人数与阅读习惯，不把群号当作价值排名。
9. 10:00 起草“低频读者轻阅读试点”，绑定成功版本和群1，说明每周一次短篇精选。
10. 10:10 admin签核，10:20 viewer下载 `reader-outreach-<id>.json`，获得固定成员清单。

## 事件与汇总口径

事件携带唯一编号、会员编号、文章编号、起止时间（ISO 8601，无时区按北京时间）和完读比例0–1。同编号重试返回原记录不重复计入，同编号不同内容返回409；撤销按编号登记依据，撤销先到则原事件后到或重试都保持已撤销不复活，重复撤销保留首个依据。接收与撤销按事件编号加咨询锁串行化。

自然周为北京时间周一00:00（含）至下周一00:00（不含），跨周事件按周界裁剪到各周。周阅读篇数按文章去重；完读率为各文章最高完读比例的均值；夜读占比为22:00–06:00时段并集 ÷ 全部时段并集，跨设备重叠只计一次；全部时段并集为零时长时夜读占比留空，无文章时完读率留空。

汇总生命周期为待计算→已计算→已发布：事件或撤销触及的（会员,自然周）自动回到待计算；计算记录当时的档案版本作为发布基线；发布把口径值写回档案并递增版本号，重复发布幂等。人工修订档案需携带最新版本号，版本不符返回409；人工修订后已计算/已发布的汇总回到待计算，发布基线不符也返回409——两条路径都不静默覆盖。分群快照只取档案表，待计算/已计算的汇总不参与分群，即分群取数只见完整版本。已完成分群版本与触达名单保留，不回溯修改。

## 计算口径和失败态

分群输入为会员唯一编号和最近完整自然周的3个聚合指标：周阅读篇数0–1000、完读率0–1、夜读占比0–1。指标可由阅读事件汇总发布回填（口径见上节），也可手工录入；夜读口径22:00–06:00。选择2–3个不同特征，k限定2–6。

Python先用StandardScaler的总体均值和总体标准差生成z=(x−mean)/std，再运行KMeans欧氏距离，`n_init=20, random_state=3107, algorithm=lloyd`。所有会员共同用于无监督聚类，不宣称预测评估。轮廓系数s=(b−a)/max(a,b)，a为同群平均距离，b为最近其他群平均距离，范围−1至1；较高表示当前标准化空间中分离更清晰，不表示业务价值。

中心用scaler.inverse_transform还原为原始单位；画像另统计群内三个原始维度的均值（即使某维未选入聚类也展示其描述均值）。群号按逆变换中心排序，仅保证同一输入和seed可复核，不跨版本等价。散点图展示前两个所选标准化维度，聚类仍用所有选择维度，二维重叠不代表同群。

样本数≤k、所选常量列、唯一特征点少于k、实际群数不足、缺失/非有限值均明确失败；不静默补值、降k或删除样本。输入验证422，重复会员编号409，队列故障503。任务失败保存failed和错误原因，修订后新建版本。创建时冻结输入，worker保存成员、中心、画像、轮廓系数、scaler参数、seed和checksum。触达草案保存版本成员副本，不随后续档案修改漂移。分群只描述行为相似性，不判断会员价值或因果关系。

## 快速启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
docker compose exec -T backend python -m pytest tests -q   # 事件/汇总/并发与分群回归
```

前端 [localhost:18206](http://localhost:18206)，后端 [localhost:19206/docs](http://localhost:19206/docs)，PostgreSQL映射17706。演示账号 `admin@demo.local`、`analyst@demo.local`、`viewer@demo.local`，密码均 `Demo123!`。seed=3107，240会员；另含2026-11-09自然周的演示事件（跨设备重叠、跨周、两条撤销），计算后留在已计算待发布。自然键只插入缺失账号、档案、事件与撤销，重复执行不覆盖人工修改。`SEED_DEMO=true`时启动自动执行一次，失败记录日志但不阻塞服务。

五服务frontend/backend/worker/db/redis均有健康检查。backend等待数据库/Redis，worker还等待backend，frontend等待backend。worker真实消费Redis任务，心跳 `/tmp/heartbeat`；单worker启动恢复queued/running。数据库、Redis和产物用命名卷，产物位于共享 `/artifacts`。Nginx将 `/api/`转发到后端根路由。显式子网10.253.107.0/24规避当前机器默认地址池耗尽，可通过NETWORK_SUBNET调整。结束用 `docker compose down -v --remove-orphans` 清理本项目数据。

## 技术、目录与本地开发

|层|实现|
|---|---|
|前端|原生HTML/CSS/ES modules，Nginx1.27|
|后端|Python3.11、FastAPI、SQLAlchemy、PyJWT|
|计算|scikit-learn1.6、NumPy2.2、SciPy1.14|
|数据与队列|PostgreSQL16、Redis7|

`frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}` 分离网络、状态、契约、共用表格/字段/状态标签、表单工具、页面和枚举。`backend/src/{routes,controllers,services,models,schemas,middlewares,utils,constants,config}` 分离HTTP、查询、算法、持久化、校验、鉴权和配置；`services/aggregation.py`为纯函数的周聚合（时区、裁剪、并集、夜读窗口），`services/events.py`为事件幂等接收、撤销墓碑与汇总生命周期。RequestId与SecurityHeaders为两个中间件，全局错误可恢复，业务写入有审计。ORM建初表，migrations/001_initial.sql与002_reading_events.sql保留实际DDL，readers新增列由后端启动时幂等ALTER补齐（仅PostgreSQL），没有在线版本迁移执行器。

本地开发先启动db/redis，在backend安装requirements，设置DATABASE_URL/REDIS_URL/JWT_SECRET后运行 `uvicorn src.main:app --reload`。前端静态文件通过Nginx同源代理，也可配置本地开发代理。环境变量见.env.example：COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、DB_PASSWORD、JWT_SECRET、SEED_DEMO、NETWORK_SUBNET。部署时替换演示凭据与密钥。

共享枚举ROLES、STATES、FEATURES、OUTREACH_STATES、EVENT_STATES、SUMMARY_STATES、SOURCES在后端src/constants/enums.py和前端src/constants/enums.js；字段约束在schemas/business.py，持久化列在models/entities.py。前端共用table/fields/status，表单hooks和HTML转义utils至少两个工具。

## 范围与证据

逐条表单/API录入及完整字段修订，无CSV/Excel导入、删除、分页、在线新会员预测或自动跨版本群组对齐。触达仅站内方案与签核，不发送邮件或消息。单worker；不宣称多worker exactly-once或大规模性能；事件接收与撤销按事件编号加锁串行化，试点规模下汇总计算为同步请求。Google Fonts需联网，离线使用serif/sans-serif回退。验证位于 `backend/tests/`：`test_aggregation.py`（纯标准库，覆盖跨周裁剪、嵌套重叠并集、夜读并集、零时长留空）可用 `python -m unittest tests.test_aggregation` 直接运行；`test_api.py`（TestClient+SQLite，覆盖乱序撤销不复活、重试幂等、发布与人工修订并发409、已完成分群回归）用 `docker compose exec -T backend python -m pytest tests -q` 运行。已知差异与截图位于源码外 `../../test-artifacts/gb-3107/`。许可证MIT，见LICENSE。
