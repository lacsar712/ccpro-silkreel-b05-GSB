# SilkReel-01 · 江口缫丝坞

缫丝盆环状作业台。登录后看到的是沿汤池围成一圈的盆位，点盆登记汤温并改状态——不是侧栏双列表 CRUD。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Web API | Quart（异步 Flask 族）· Hypercorn |
| 结构 | `repositories.py` 仓储 + `services.py` 门槛，路由不直接拼 SQL |
| 数据 | SQLAlchemy 2 async · asyncpg · PostgreSQL 15 |
| 前端 | Preact 10 · Vite |
| 部署 | Docker Compose |

## 路径与端口

- 前端：http://localhost:4760
- API：http://localhost:8760
- PostgreSQL：localhost:6160

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 缫丝工 |

## 业务规则

- 盆状态不可标成「已缫完」，除非该盆**最近一条**汤温记录落在 **38～42℃**。
- 同一盆两次汤温登记须隔满**最小间隔分钟**（管理员在「汤温间隔」专页设定，至少 5 分钟）；间隔未满再登会被中文拒绝且不入库。改盆态不看间隔。规则在 `backend/app/services.py`。

顶栏可切换「环盆作业台」与「汤温间隔」专页；缫丝工打开专页只能看间隔数字，仅管理员可调整。

## 快速启动

```bash
cd SilkReel/SilkReel-01
docker compose up --build
```
