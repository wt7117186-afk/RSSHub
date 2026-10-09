#!/usr/bin/env bash
# 一次性：在仓库里建好任务状态标签。在仓库目录里运行：./scripts/初始化.sh
set -euo pipefail

gh label create 待派活     --color FBCA04 --description "老板已下达，等 Muse 补全任务单并派活" --force
gh label create 进行中     --color 1D76DB --description "Codex 正在干活"                     --force
gh label create 待审核     --color 5319E7 --description "PR 已提交，等 Claude 审核"            --force
gh label create 待老板批准 --color 0E8A16 --description "Claude 审核通过，等老板合并"          --force
gh label create 退回       --color D93F0B --description "Claude 审核未通过，需返工"            --force

echo "✔ 标签已建好"
