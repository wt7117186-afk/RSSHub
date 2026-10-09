# AI 公司总部

这个仓库就是公司的办公室：任务、交付物、汇报和群聊记录都在这里。

## 组织架构

```
                  老板（你）
       定目标 · 拍板 · 合并 PR = 最终批准
           │                       │
  Muse：总经理                 Claude：监事 / 顾问
  接目标 · 拆任务 · 派活 · 汇报   审核交付 · 核对汇报 · 直接向老板报告
           │                       ▲
  Codex：工程师                    │
  在 Muse 云电脑里干活 ──── 提交 PR ┘
```

| 角色 | 谁 | 岗位说明 |
|---|---|---|
| 老板 | 你 | 发目标、合并 PR、关闭任务 |
| 总经理 | Muse | [roles/muse-总经理.md](roles/muse-总经理.md) |
| 工程师 | Codex | [roles/codex-工程师.md](roles/codex-工程师.md) |
| 监事 / 顾问 | Claude | [roles/claude-监事.md](roles/claude-监事.md) |

## 工作群

### Telegram 群：日常沟通、随手派活

- 群里有你和三个机器人：Muse、Codex、Claude。
- `@codex 做个……` → Codex 干活，结果发回群里；`@claude 帮我看看……` → Claude 回答；`@muse ……` → Muse 处理。
- AI 之间也会互相 @ 接力（例如 Codex 做完 @claude 检查），最多连续 6 轮，之后等你发话。
- 一条消息叫谁：开头连着的几个 @ 都会被叫到；开头没有 @ 时，只叫第一个被 @ 的人。
- 背后是 Muse 云电脑上的中枢程序 `telegram/hub.py`，配置见 [开张清单.md](开张清单.md) 第 6 步。

### GitHub Issues：正式任务的记录

- **一个任务 = 一个 Issue。** 所有人在 Issue 下面留言，这就是这个任务的档案。
- 每条留言开头写角色名：`【老板】` `【Muse】` `【Codex】` `【Claude】`。
- 状态用标签表示：`待派活` → `进行中` → `待审核` → `待老板批准` → 关闭。

## 一个任务怎么走

1. **老板**开 Issue，用“任务单”模板，写一句话目标就行。
2. **Muse** 把任务单补全（交付物、验收标准、截止时间），打上 `进行中`，派给 Codex：
   `./scripts/派活.sh <Issue编号>`
3. **Codex** 在 `task/<Issue编号>` 分支干活，提交 PR，PR 描述里写 `Closes #<Issue编号>`。
4. **Muse** 在 Issue 里汇报进度，把标签改成 `待审核`。
5. **Claude** 按验收标准审 PR，结论写在 PR 里：`通过` 或 `退回 + 具体问题`。
   - 退回 → 回到第 3 步，Muse 重新派给 Codex。
   - 通过 → 标签改成 `待老板批准`。
6. **老板**合并 PR，任务自动关闭。

## 目录

```
AGENTS.md            公司手册（Codex 和 Muse 每次开工先读）
CLAUDE.md            Claude 的入口（引用公司手册 + 监事职责）
roles/               三个岗位说明（贴给对应的 AI）
scripts/初始化.sh     一次性：建标签
scripts/派活.sh       Muse 用来派活给 Codex
scripts/群聊.sh       Muse 在 Telegram 群里看消息、发言
telegram/hub.py      Telegram 工作群中枢（在 Muse 云电脑上常驻运行）
reports/             日报 / 周报
决策日志.md           老板拍板的事
.github/             任务单模板、PR 模板、Claude 自动审核
```

## 开张步骤

见 [开张清单.md](开张清单.md)。
