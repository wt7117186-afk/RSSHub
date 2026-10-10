#!/usr/bin/env bash
# 打印公司看板：每个状态下有哪些任务，以及所有未合并的 PR。
set -euo pipefail

for label in 待派活 进行中 退回 待审核 待老板批准; do
  echo "== $label =="
  gh issue list --state open --label "$label" --json number,title \
    -q '.[] | "  #\(.number) \(.title)"'
done

echo "== 未合并的 PR =="
gh pr list --state open --json number,title,headRefName \
  -q '.[] | "  #\(.number) \(.title)  [\(.headRefName)]"'
