# AI 公司总部

## 组织架构

```
                  老板（你）
         定目标 · 拍板 · 合并 PR = 最终批准
           │                       │
  Muse：总经理                 Claude：监事 / 顾问
  接目标 · 拆任务 · 派活 · 汇报   审核交付 · 直接向老板报告
           │                       ▲
  Codex：工程师                    │
  按任务单干活 ─────── 提交 PR ─────┘
```

| 角色 | 谁 | 在 Slack 里怎么叫它 | 岗位说明 |
|---|---|---|---|
| 老板 | 你 | — | — |
| 总经理 | Muse | 通过 Muse 的 Slack 连接器读写群消息 | [roles/muse-总经理.md](roles/muse-总经理.md) |
| 工程师 | Codex | `@Codex`（或你的 dot） | [roles/codex-工程师.md](roles/codex-工程师.md) |
| 监事 / 顾问 | Claude | `@Claude` | [roles/claude-监事.md](roles/claude-监事.md) |

## 工作群 = Slack 的 `#公司群` 频道

- **一个任务 = 一个话题串（thread）。** 话题串第一条是任务单，之后所有沟通都回复在这个话题串里。
  Codex 和 Claude 被 @ 时会读取整个话题串，所以前面的人说过什么它们都知道。
- 日常闲聊、临时问题直接发在频道里。
- 代码和文件放在这个 GitHub 仓库：Codex 和 Claude 在云端干活时都会读取这里的 `AGENTS.md`。

## 一个任务怎么走

1. **老板**在 `#公司群` 发一句话目标，@Muse 或直接告诉 Muse。
2. **Muse** 开一个话题串，写任务单（目标、交付物、验收标准、不做什么、截止时间），然后在话题串里 `@Codex` 派活。
3. **Codex** 干完活，在 GitHub 开 PR，把 PR 链接回复到话题串。
4. **Muse** 在话题串里 `@Claude`，请它按任务单审核这个 PR。
   （仓库装了 Claude 自动审核后，PR 一开 Claude 就会在 GitHub 上自动审一次。）
5. **Claude** 回复 `通过` 或 `退回 + 具体问题`。退回 → Muse 再 `@Codex` 返工。
6. **Muse** @老板 汇报；**老板**合并 PR，任务完成。

## 目录

```
开张清单.md          从零搭起来的步骤
AGENTS.md            公司手册（Codex、Claude、Muse 开工前读）
CLAUDE.md            Claude 的入口
roles/               三个岗位说明
.github/             PR 模板、Claude 自动审核
reports/             日报模板
决策日志.md           老板拍板的事
备用方案.md           不用 Slack 时的做法（Muse 云电脑脚本、Telegram 群）
```
