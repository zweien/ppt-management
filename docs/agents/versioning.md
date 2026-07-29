# Versioning: SemVer + 单一真相源

本项目遵循 [SemVer](https://semver.org/lang/zh-CN/)。版本号决定什么变更是破坏性的、什么只是新增功能。

## 单一真相源

**`backend/app/__init__.py` 的 `__version__` 是版本号的唯一权威。**

传播链路（无需手动同步的部分）：

- `backend/app/core/config.py` → `from app import __version__`，`APP_VERSION = __version__`
- `backend/app/main.py` → `FastAPI(version=settings.APP_VERSION)`（Swagger / OpenAPI info）
- `GET /` 根路由 → `{"version": settings.APP_VERSION, ...}`
- 前端 `lib/version.ts` → `fetchVersion()` 从 `GET /` 拉取，缓存到 localStorage（1h TTL）
- 前端 `AppShell` 侧边栏底部显示版本号，「更新日志」页显示当前版本

**需要手动同步的**（npm 元数据，非真相源）：

- `frontend/package.json` 的 `version` 字段 —— 发版时一并更新，保持一致即可

## 版本号规则（SemVer）

格式 `MAJOR.MINOR.PATCH`：

| 升哪一位 | 触发条件 | 示例 |
|---------|---------|------|
| **MAJOR** | 不兼容的 API / 数据库 / 行为变更 | 改返回字段结构、删接口、破坏性 DB 迁移 |
| **MINOR** | 向后兼容的新功能 | 新接口、新页面、新功能模块 |
| **PATCH** | 向后兼容的修复 | bug 修复、UI 调整、文档、性能优化 |

预发布 / 内测期（当前 `0.x.x`）：MINOR 也可能包含较大变更，MAJOR 留到 `1.0.0` 正式发布。

## 发版流程

每次发版按以下步骤（顺序重要）：

1. **改版本号**：编辑 `backend/app/__init__.py` 的 `__version__`
2. **同步 npm 元数据**：编辑 `frontend/package.json` 的 `version`（保持一致）
3. **更新 CHANGELOG**：
   - 在 `CHANGELOG.md` 把顶部 `## [Unreleased]` 改为 `## [x.y.z] - YYYY-MM-DD`
   - 在其上方新增空的 `## [Unreleased]`
   - 同步 `frontend/src/lib/version.ts` 的 `CHANGELOG` 数组（在 Unreleased 后插入新版本对象）
4. **提交**：`git commit -m "chore(release): vx.y.z"`
5. **打 tag**（可选）：`git tag vx.y.z && git push --tags`

## CHANGELOG 规范

[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格。分类用 emoji 前缀：

| Emoji | 分类 | 用途 |
|-------|------|------|
| 🎉 | 里程碑 | 重大版本节点（阶段交付） |
| ✨ | 新功能 | feat: |
| 🐛 | 修复 | fix: |
| 📚 | 文档 | docs: |
| ♻️ | 重构 | refactor: |
| ⚡ | 性能 | perf: |

每条变更对应一个或一组 commit，重要的条目可引用 commit short hash，如 ``(`a311931`)``。

## Commit 规范

延续 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat:` 新功能（触发 MINOR）
- `fix:` 修复（触发 PATCH）
- `docs:` 文档（通常 PATCH）
- `chore:` 杂务 / 构建 / 发版
- `refactor:` / `perf:` / `test:` / `style:` 同标准
- 可带 scope：`fix(render):`、`feat(ui):`

发版提交统一用 `chore(release): vx.y.z`。
