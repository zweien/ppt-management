Status: done

# 02 — 单管理员认证(登录/改密/登出)

## Parent

阶段一 MVP(`.scratch/phase-1-foundation/`)。

## What to build

一条完整的认证 vertical slice,端到端穿过 schema / API / UI / test:单管理员账号能登录、修改密码、登出,受保护的 API 与页面要求登录态。

这是后续所有需要鉴权的 slice(上传、文件管理等)的前置。

约束(遵守 PRD §3.1、§18.1):

- **单管理员**:DB 中 `users` 表第一版仅一条管理员记录。但表结构保留 `owner_id`/`created_by`/`updated_by` 等字段,为后续多人模式预留(见 CONTEXT.md「单管理员」)。
- **密码哈希**:用 Argon2id 或 bcrypt,**不存明文**。
- **会话**:用基于 Redis 的 session 或 JWT(具体由实现选,MVP 内不必引入完整 OAuth)。
- **首个管理员**:首次启动时通过环境变量(或一次性 bootstrap 命令)创建初始管理员账号与默认密码,不依赖手动 SQL。

API 形状参考 PRD §14.1:`POST /auth/login`、`POST /auth/logout`、`PUT /auth/password`。

## Acceptance criteria

- [ ] `users` 表建立,密码字段存 Argon2id/bcrypt 哈希,无明文
- [ ] 首次启动可通过配置创建初始管理员账号(非手动插 SQL)
- [ ] 登录、登出、修改密码三个 API 端点可用
- [ ] 受保护 API 与页面在未登录时拒绝访问(401 / 重定向登录)
- [ ] 前端有登录页,登录后进入主界面,登出后回到登录页
- [ ] Alembic 迁移可重放(干净 DB 上 `alembic upgrade head` 建出表)

## Blocked by

- 01 — 项目脚手架:全栈可从零启动(需要 DB、Redis、FastAPI、前端骨架就绪)
