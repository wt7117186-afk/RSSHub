#!/usr/bin/env bash
# 总经理（Muse）用这个脚本把一个 Issue 派给工程师（Codex）。
#
# 用法：./scripts/派活.sh <Issue编号> [传给 codex exec 的额外参数...]
#   例：任务需要联网装依赖时
#   ./scripts/派活.sh 12 -c sandbox_workspace_write.network_access=true
#
# 脚本会：
#   1. 拉最新代码，切到分支 task/<编号>（返工时沿用已有分支）
#   2. 把岗位说明 + 任务单 + 已有留言（含 Claude 的退回意见）交给 Codex
#   3. Codex 改完文件后，提交、推送、开 PR（或更新已有 PR）
#   4. 在 Issue 里留言汇报，标签改成“待审核”
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "用法：$0 <Issue编号> [codex exec 额外参数...]" >&2
  exit 1
fi

N="$1"
shift

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

mkdir -p logs
TS="$(date +%Y%m%d-%H%M%S)"
LOG="logs/task-$N-$TS.log"
PR_BODY="logs/pr-$N.md"
BRANCH="task/$N"

TITLE="$(gh issue view "$N" --json title -q .title)"
gh issue edit "$N" --remove-label 待派活,退回 --add-label 进行中 >/dev/null || true
ISSUE_TEXT="$(gh issue view "$N" --comments)"

# 切分支：远端已有 task/<编号> 就是返工，沿用；否则从最新 main 新建
git fetch origin
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  git checkout -B "$BRANCH" "origin/$BRANCH"
  PR_TEXT="$(gh pr view "$BRANCH" --comments 2>/dev/null || true)"
else
  git checkout -B "$BRANCH" origin/main
  PR_TEXT=""
fi
rm -f "$PR_BODY"

PROMPT="$(cat roles/codex-工程师.md)

---

# 本次任务：Issue #$N

$ISSUE_TEXT
"

if [ -n "$PR_TEXT" ]; then
  PROMPT="$PROMPT

---

# 这是返工。已有 PR 和审核意见如下，逐条处理：

$PR_TEXT
"
fi

PROMPT="$PROMPT

---

# 本次执行说明

- 你现在在分支 $BRANCH 上。提交、推送、开 PR 由派活脚本完成，你只需要改文件。
- 干完后把 PR 说明写进 $PR_BODY（第一行 \`Closes #$N\`）。
"

echo "▶ 派活给 Codex：#$N $TITLE（日志：$LOG）"
printf '%s' "$PROMPT" | codex exec -C "$ROOT" -s workspace-write "$@" - 2>&1 | tee "$LOG"

# Codex 没有产出改动
if [ -z "$(git status --porcelain)" ]; then
  gh issue comment "$N" --body "【Muse】Codex 本次没有产出任何改动，日志在云电脑的 \`$LOG\`，我来补充说明后重新派活。"
  echo "✖ Codex 没有改动任何文件" >&2
  exit 1
fi

[ -f "$PR_BODY" ] || printf 'Closes #%s\n\n（Codex 没有写 PR 说明，请 Muse 补充）\n' "$N" > "$PR_BODY"

git add -A
git commit -q -m "[#$N] $TITLE"
git push -q -u origin "$BRANCH"

if gh pr view "$BRANCH" >/dev/null 2>&1; then
  gh pr comment "$BRANCH" --body-file <(printf '【Codex】已按意见修改并推送。\n\n'; cat "$PR_BODY")
  PR_URL="$(gh pr view "$BRANCH" --json url -q .url)"
else
  PR_URL="$(gh pr create --base main --head "$BRANCH" --title "[#$N] $TITLE" --body-file "$PR_BODY")"
fi

gh issue edit "$N" --remove-label 进行中 --add-label 待审核 >/dev/null || true
gh issue comment "$N" --body "【Codex】已提交：$PR_URL
Claude 会自动审核这个 PR。"

echo "✔ 完成：$PR_URL"
