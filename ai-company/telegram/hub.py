#!/usr/bin/env python3
"""公司 Telegram 工作群中枢。

Telegram 规定机器人之间互相看不到对方的消息，所以群里的三个机器人
（Muse / Codex / Claude）统一由这个中枢收发：
  - 用 Muse 机器人接收群里所有消息（需关闭它的隐私模式）
  - 消息里 @codex / @claude 时，在本机调用对应的 AI，用它自己的机器人把回复发回群里
  - AI 的回复里再 @ 别人，中枢继续转达，实现 AI 之间互相派活
  - @muse 的消息由 Muse 自己用“等 / 看”命令读取，用“说”命令回复

用法（在仓库根目录运行）：
  python3 telegram/hub.py ids           配置前：查看群 ID 和你的用户 ID
  python3 telegram/hub.py run           启动中枢（常驻运行）
  python3 telegram/hub.py 看            Muse 用：看上次之后的新消息
  python3 telegram/hub.py 等 [秒]       Muse 用：等到有人 @Muse 再返回（默认 600 秒）
  python3 telegram/hub.py 说 <文本>     Muse 用：以 Muse 身份在群里发言（不带文本则读标准输入）
  python3 telegram/hub.py 历史 [条数]   看最近的群聊记录（默认 30 条）
"""

import json
import os
import queue
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = HERE / 'data'
LOG = DATA / 'log.jsonl'
OUTBOX = DATA / 'outbox'
CURSOR = DATA / 'muse_cursor'
OFFSET = DATA / 'offset'
USERNAMES = DATA / 'usernames.json'
WORKSPACE = REPO / '群聊工作区'

API = os.environ.get('TG_API_BASE', 'https://api.telegram.org')
AGENTS = ('muse', 'codex', 'claude')
NAMES = {'boss': '老板', 'muse': 'Muse', 'codex': 'Codex', 'claude': 'Claude'}
HISTORY = 30

INTRO = {
    'codex': '你是公司的工程师 Codex，负责写代码、做网站、写脚本、处理数据。',
    'claude': '你是公司的监事兼顾问 Claude，负责审核大家的产出、核对汇报是否属实、给老板明确的建议。你只查看文件，不修改文件。',
}

GROUP_RULES = """# 群聊规则
- 你在公司的 Telegram 工作群里。成员：老板（人类）、Muse（总经理）、Codex（工程师）、Claude（监事 / 顾问）。
- 你的回复会原样发到群里：用中文，直接说结论和结果，不要客套。
- 需要别人接手时，在回复里写 @muse、@codex 或 @claude，并说清楚要对方做什么。不需要对方做事就不要 @。
- 一条消息只会叫到一个人：开头连着的几个 @ 都会被叫到；开头没有 @ 时，只叫第一个被 @ 的人。
- 群聊里做出来的文件放在仓库的“群聊工作区/”目录。正式任务走 GitHub Issue 流程（见 AGENTS.md）。"""

CLAUDE_TOOLS = ','.join([
    'Read', 'Grep', 'Glob',
    'Bash(git log:*)', 'Bash(git diff:*)', 'Bash(git status:*)', 'Bash(git show:*)',
    'Bash(gh issue view:*)', 'Bash(gh issue list:*)',
    'Bash(gh pr view:*)', 'Bash(gh pr diff:*)', 'Bash(gh pr list:*)',
])

_log_lock = threading.Lock()


# ---------- 配置 ----------

def load_config():
    cfg = {}
    env_file = HERE / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                cfg[key.strip()] = value.strip()
    for key in list(cfg) + ['MUSE_BOT_TOKEN', 'CODEX_BOT_TOKEN', 'CLAUDE_BOT_TOKEN',
                            'GROUP_CHAT_ID', 'BOSS_USER_ID', 'MAX_HOPS', 'CODEX_ARGS']:
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    return cfg


def require(cfg, *keys):
    missing = [k for k in keys if not cfg.get(k)]
    if missing:
        sys.exit(f'telegram/.env 缺少：{", ".join(missing)}（参考 telegram/.env.example）')


# ---------- Telegram ----------

def tg(token, method, **params):
    req = urllib.request.Request(
        f'{API}/bot{token}/{method}',
        data=json.dumps(params).encode(),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            res = json.load(resp)
    except urllib.error.HTTPError as e:
        res = json.load(e)
    if not res.get('ok'):
        raise RuntimeError(f'Telegram {method} 失败：{res.get("description", res)}')
    return res['result']


# ---------- 群聊记录 ----------

def append_log(who, text, hops=0, tg_id=None):
    rec = {'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'who': who, 'text': text, 'hops': hops, 'tg_id': tg_id}
    with _log_lock, LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec


def read_log():
    if not LOG.exists():
        return []
    return [json.loads(line) for line in LOG.read_text(encoding='utf-8').splitlines() if line.strip()]


def fmt(rec, limit=2000):
    text = rec['text'] if len(rec['text']) <= limit else rec['text'][:limit] + '…（后略）'
    return f'[{rec["ts"]}] {NAMES.get(rec["who"], rec["who"])}：{text}'


def mentioned(text, usernames):
    found = []
    for agent in AGENTS:
        patterns = [rf'@{agent}\b']
        if usernames.get(agent):
            patterns.append('@' + re.escape(usernames[agent]) + r'\b')
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            found.append(agent)
    return found


def mention_spans(text, usernames):
    spans = []
    for agent in AGENTS:
        patterns = [rf'@{agent}\b']
        if usernames.get(agent):
            patterns.append('@' + re.escape(usernames[agent]) + r'\b')
        for p in patterns:
            spans += [(m.start(), m.end(), agent) for m in re.finditer(p, text, re.IGNORECASE)]
    return sorted(spans)


def called(text, usernames):
    """这条消息叫谁接手：开头连着的 @ 都叫；开头没有 @ 时，只叫第一个被 @ 的人。"""
    spans = mention_spans(text, usernames)
    lead, pos = [], 0
    for start, end, agent in spans:
        if text[pos:start].strip(' ,，、\n') != '':
            break
        lead.append(agent)
        pos = end
    chosen = lead or [spans[0][2] for _ in spans[:1]]
    return list(dict.fromkeys(chosen))


def load_usernames():
    return json.loads(USERNAMES.read_text(encoding='utf-8')) if USERNAMES.exists() else {}


# ---------- 调用 AI ----------

def build_prompt(agent, rec):
    history = '\n'.join(fmt(r) for r in read_log()[-HISTORY:])
    return f"""{INTRO[agent]}

{GROUP_RULES}

# 最近的群聊记录
{history}

# 现在轮到你
请回复{NAMES.get(rec['who'], rec['who'])}的这条消息：
{rec['text']}
"""


def run_codex(prompt, extra_args):
    WORKSPACE.mkdir(exist_ok=True)
    fd, out_file = tempfile.mkstemp(suffix='.txt')
    os.close(fd)
    try:
        proc = subprocess.run(
            ['codex', 'exec', '-C', str(WORKSPACE), '-s', 'workspace-write', '-o', out_file, *extra_args, '-'],
            input=prompt, text=True, capture_output=True, timeout=3600,
        )
        reply = Path(out_file).read_text(encoding='utf-8').strip()
    finally:
        os.unlink(out_file)
    return reply or (proc.stderr or proc.stdout).strip()[-3000:] or f'（Codex 没有输出，退出码 {proc.returncode}）'


def run_claude(prompt):
    proc = subprocess.run(
        ['claude', '-p', '--output-format', 'text', '--allowedTools', CLAUDE_TOOLS],
        input=prompt, text=True, capture_output=True, cwd=REPO, timeout=1800,
    )
    return proc.stdout.strip() or proc.stderr.strip()[-3000:] or f'（Claude 没有输出，退出码 {proc.returncode}）'


# ---------- 中枢 ----------

class Hub:
    def __init__(self, cfg):
        self.tokens = {a: cfg[f'{a.upper()}_BOT_TOKEN'] for a in AGENTS}
        self.chat = int(cfg['GROUP_CHAT_ID'])
        self.boss = int(cfg['BOSS_USER_ID'])
        self.max_hops = int(cfg.get('MAX_HOPS') or 6)
        self.codex_args = shlex.split(cfg.get('CODEX_ARGS', ''))
        self.usernames = {a: tg(self.tokens[a], 'getMe')['username'] for a in AGENTS}
        USERNAMES.write_text(json.dumps(self.usernames, ensure_ascii=False), encoding='utf-8')
        self.queues = {a: queue.Queue() for a in ('codex', 'claude')}
        for agent, q in self.queues.items():
            threading.Thread(target=self.worker, args=(agent, q), daemon=True).start()

    def send(self, agent, text, reply_to=None):
        first_id = None
        for i, chunk in enumerate([text[j:j + 4000] for j in range(0, len(text), 4000)] or ['（空）']):
            params = {'chat_id': self.chat, 'text': chunk}
            if reply_to and i == 0:
                params['reply_parameters'] = {'message_id': reply_to, 'allow_sending_without_reply': True}
            msg = tg(self.tokens[agent], 'sendMessage', **params)
            first_id = first_id or msg['message_id']
        return first_id

    def route(self, rec):
        if rec['who'] != 'boss' and rec['who'] not in AGENTS:
            return
        targets = [a for a in called(rec['text'], self.usernames) if a != rec['who'] and a != 'muse']
        if not targets:
            return
        if rec['hops'] >= self.max_hops:
            self.send('muse', f'【系统】AI 之间已经连续接力 {rec["hops"]} 轮，先暂停，等老板指示。')
            return
        for agent in targets:
            self.queues[agent].put(rec)

    def worker(self, agent, q):
        while True:
            rec = q.get()
            try:
                tg(self.tokens[agent], 'sendChatAction', chat_id=self.chat, action='typing')
                prompt = build_prompt(agent, rec)
                reply = run_codex(prompt, self.codex_args) if agent == 'codex' else run_claude(prompt)
            except Exception as e:  # 出错也要在群里说一声
                reply = f'【出错】{e}'
            try:
                tg_id = self.send(agent, reply, reply_to=rec.get('tg_id'))
                self.route(append_log(agent, reply, rec['hops'] + 1, tg_id))
            except Exception as e:
                print(f'[{agent}] 发送失败：{e}', file=sys.stderr)

    def flush_outbox(self):
        for f in sorted(OUTBOX.glob('*.json')):
            text = json.loads(f.read_text(encoding='utf-8'))['text']
            tg_id = self.send('muse', text)
            f.unlink()
            self.route(append_log('muse', text, 0, tg_id))

    def run(self):
        print(f'中枢已启动：群 {self.chat}，机器人 {self.usernames}', flush=True)
        offset = int(OFFSET.read_text()) if OFFSET.exists() else None
        while True:
            try:
                self.flush_outbox()
                updates = tg(self.tokens['muse'], 'getUpdates', offset=offset, timeout=5, allowed_updates=['message'])
            except Exception as e:
                print(f'轮询出错：{e}', file=sys.stderr, flush=True)
                time.sleep(5)
                continue
            for u in updates:
                offset = u['update_id'] + 1
                OFFSET.write_text(str(offset))
                m = u.get('message') or {}
                sender = m.get('from') or {}
                if m.get('chat', {}).get('id') != self.chat or 'text' not in m or sender.get('is_bot'):
                    continue
                who = 'boss' if sender.get('id') == self.boss else sender.get('first_name', '成员')
                self.route(append_log(who, m['text'], 0, m['message_id']))


# ---------- 命令 ----------

def cmd_ids(cfg):
    require(cfg, 'MUSE_BOT_TOKEN')
    updates = tg(cfg['MUSE_BOT_TOKEN'], 'getUpdates', timeout=0)
    if not updates:
        print('还没收到消息：先把 Muse 机器人拉进群，在群里随便发一句话，再运行这个命令。')
    for u in updates:
        m = u.get('message') or {}
        chat, sender = m.get('chat', {}), m.get('from', {})
        print(f'群「{chat.get("title", "私聊")}」 GROUP_CHAT_ID={chat.get("id")}    '
              f'发言人「{sender.get("first_name")}」 BOSS_USER_ID={sender.get("id")}')


def cmd_look():
    log = read_log()
    start = int(CURSOR.read_text()) if CURSOR.exists() else 0
    usernames = load_usernames()
    new = log[start:]
    for rec in new:
        star = '★ ' if rec['who'] != 'muse' and 'muse' in mentioned(rec['text'], usernames) else '  '
        print(star + fmt(rec, limit=100000))
    if not new:
        print('（没有新消息）')
    CURSOR.write_text(str(len(log)))


def cmd_wait(seconds):
    usernames = load_usernames()
    start = int(CURSOR.read_text()) if CURSOR.exists() else 0
    deadline = time.time() + seconds
    while time.time() < deadline:
        if any(r['who'] != 'muse' and 'muse' in mentioned(r['text'], usernames) for r in read_log()[start:]):
            break
        time.sleep(3)
    cmd_look()


def cmd_say(text):
    text = text.strip()
    if not text:
        sys.exit('没有要发的内容')
    tmp = OUTBOX / f'{time.time_ns()}.tmp'
    tmp.write_text(json.dumps({'text': text}, ensure_ascii=False), encoding='utf-8')
    tmp.replace(tmp.with_suffix('.json'))
    print('已交给中枢发送')


def cmd_history(n):
    for rec in read_log()[-n:]:
        print(fmt(rec, limit=100000))


def main():
    DATA.mkdir(exist_ok=True)
    OUTBOX.mkdir(exist_ok=True)
    args = sys.argv[1:]
    cmd = args[0] if args else ''
    if cmd == 'ids':
        cmd_ids(load_config())
    elif cmd == 'run':
        cfg = load_config()
        require(cfg, 'MUSE_BOT_TOKEN', 'CODEX_BOT_TOKEN', 'CLAUDE_BOT_TOKEN', 'GROUP_CHAT_ID', 'BOSS_USER_ID')
        Hub(cfg).run()
    elif cmd == '看':
        cmd_look()
    elif cmd == '等':
        cmd_wait(int(args[1]) if len(args) > 1 else 600)
    elif cmd == '说':
        cmd_say(' '.join(args[1:]) if len(args) > 1 else sys.stdin.read())
    elif cmd == '历史':
        cmd_history(int(args[1]) if len(args) > 1 else HISTORY)
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
