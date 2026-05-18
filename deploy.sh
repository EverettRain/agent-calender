#!/bin/bash
# ============================================================
#  Agent-Calendar VPS 部署引导脚本 (macOS)
#  从本地 server/ 同步代码到 VPS，管理 systemd 服务、数据库备份等
# ============================================================

set -euo pipefail

if [ -n "${ZSH_VERSION:-}" ]; then
    exec /bin/bash "$0" "$@"
fi

if [[ "$(uname)" != "Darwin" ]]; then
    echo "[!] 本脚本设计在 macOS 开发机上运行" >&2
    exit 1
fi

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
DIM='\033[2m'
NC='\033[0m'

write_ok()   { echo -e "  ${GREEN}[√] $1${NC}" >&2; }
write_warn() { echo -e "  ${YELLOW}[!] $1${NC}" >&2; }
write_err()  { echo -e "  ${RED}[!] $1${NC}" >&2; }
write_info() { echo -e "  $1" >&2; }
write_dim()  { echo -e "  ${DIM}$1${NC}" >&2; }
read_choice() {
    echo "" >&2
    echo -ne "  ${WHITE}$1${NC}" >&2
    read -r REPLY
}
confirm() {
    read_choice "$1 [y/N]: "
    [[ "$REPLY" == "y" || "$REPLY" == "Y" ]]
}

# ── 配置 ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/deploy.config.json"
LOCAL_SERVER_DIR="$SCRIPT_DIR/server"
LOCAL_ENV_FILE="$LOCAL_SERVER_DIR/.env"
LOCAL_BACKUP_DIR="$SCRIPT_DIR/backups/db"
LOG_DIR="$SCRIPT_DIR/backups/logs"

if [ ! -f "$CONFIG_FILE" ]; then
    write_err "未找到 deploy.config.json"
    write_info "请先 cp deploy.config.example.json deploy.config.json 并编辑"
    exit 1
fi

get_config() {
    jq -r "$1" "$CONFIG_FILE"
}

REMOTE_HOST=$(get_config '.remoteHost')
REMOTE_BASE=$(get_config '.remoteBase')
SERVICE_NAME=$(get_config '.serviceName')
SERVICE_USER=$(get_config '.serviceUser')
PYTHON_BIN=$(get_config '.pythonBin')
LISTEN_HOST=$(get_config '.listenHost')
LISTEN_PORT=$(get_config '.listenPort')
MAX_DB_BACKUPS=$(get_config '.maxDbBackups')
SUDO_CMD=$(get_config '.sudoCmd')

# Required non-empty fields
for var in REMOTE_HOST REMOTE_BASE SERVICE_NAME SERVICE_USER PYTHON_BIN LISTEN_HOST LISTEN_PORT MAX_DB_BACKUPS; do
    val="${!var}"
    if [ -z "$val" ] || [ "$val" = "null" ]; then
        write_err "deploy.config.json 缺少 $var"
        exit 1
    fi
done

# sudoCmd may be intentionally empty (root SSH user doesn't need sudo)
if [ "$SUDO_CMD" = "null" ]; then
    SUDO_CMD=""
fi

mkdir -p "$LOCAL_BACKUP_DIR" "$LOG_DIR"

log_msg() {
    local ts
    ts=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$ts] $1" >> "$LOG_DIR/deploy.log"
}

# ── 依赖检查 ──
check_deps() {
    for cmd in jq rsync ssh curl; do
        command -v "$cmd" >/dev/null 2>&1 || {
            write_err "未找到 $cmd"
            exit 1
        }
    done
}

# ── SSH 包装 ──
ssh_run() {
    ssh -o ConnectTimeout=10 "$REMOTE_HOST" "$@"
}

ssh_sudo() {
    # 远端以 sudo 执行命令；命令通过 stdin 传，避免引号转义噩梦
    ssh -o ConnectTimeout=10 "$REMOTE_HOST" "$SUDO_CMD bash -s" <<EOF
$*
EOF
}

ssh_check() {
    write_info "检查 SSH 连接 ${REMOTE_HOST} ..."
    if ! ssh_run "echo ok" >/dev/null 2>&1; then
        write_err "SSH 连接失败"
        write_info "请先在 ~/.ssh/config 配好或测试 \`ssh ${REMOTE_HOST}\`"
        return 1
    fi
    write_ok "SSH 连接正常"
}

# ── 远端环境探测 ──
detect_remote_python() {
    local v
    v=$(ssh_run "command -v ${PYTHON_BIN} && ${PYTHON_BIN} --version" 2>/dev/null || true)
    if [ -z "$v" ]; then
        write_err "远端找不到 ${PYTHON_BIN}"
        write_info "请先在 VPS 安装 Python 3.11-3.13，例如："
        write_dim "  Debian/Ubuntu: sudo apt install python3 python3-venv python3-dev"
        write_dim "  RHEL/CentOS:   sudo dnf install python3 python3-pip"
        return 1
    fi
    write_ok "远端 Python: $(echo "$v" | tr '\n' ' ')"
}

# ── 同步代码 ──
rsync_code() {
    write_info "同步 server/ → ${REMOTE_HOST}:${REMOTE_BASE} ..."
    log_msg "rsync_code start"
    rsync -az --delete \
        --exclude '.venv/' \
        --exclude '__pycache__/' \
        --exclude '.pytest_cache/' \
        --exclude '.ruff_cache/' \
        --exclude '.mypy_cache/' \
        --exclude '*.egg-info/' \
        --exclude 'data/' \
        --exclude 'logs/' \
        --exclude '.env' \
        --exclude '.env.*' \
        -e ssh \
        "${LOCAL_SERVER_DIR}/" \
        "${REMOTE_HOST}:${REMOTE_BASE}/app_src/"

    # 把代码所有权交给 SERVICE_USER
    ssh_sudo "chown -R ${SERVICE_USER}:${SERVICE_USER} ${REMOTE_BASE}/app_src"
    ensure_data_symlinks
    log_msg "rsync_code done"
    write_ok "代码同步完成"
}

# 让 app_src/ 内的相对路径（./data, ./logs）解析到 REMOTE_BASE/{data,logs}
# 这样 .env 里 DATABASE_URL=sqlite+aiosqlite:///./data/data.db 在
# alembic（CWD=app_src）与 systemd uvicorn（WorkingDirectory=app_src）下都能用
ensure_data_symlinks() {
    ssh_sudo "
        ln -sfn ${REMOTE_BASE}/data ${REMOTE_BASE}/app_src/data
        ln -sfn ${REMOTE_BASE}/logs ${REMOTE_BASE}/app_src/logs
        chown -h ${SERVICE_USER}:${SERVICE_USER} ${REMOTE_BASE}/app_src/data ${REMOTE_BASE}/app_src/logs
    "
}

# ── 远端初始化（首装专用） ──
op_setup() {
    ssh_check || return 1
    detect_remote_python || return 1

    if [ ! -f "$LOCAL_ENV_FILE" ]; then
        write_err "本地未找到 ${LOCAL_ENV_FILE}"
        write_info "请先 cp server/.env.example server/.env 并填入 API_TOKEN / DEEPSEEK_API_KEY"
        return 1
    fi

    write_warn "首次部署：将在 VPS 上创建用户、装依赖、写 systemd 单元，并启动服务"
    confirm "确认对 ${REMOTE_HOST} 执行首装吗" || return 0

    log_msg "setup start host=${REMOTE_HOST}"

    write_info "[1/8] 创建系统用户 ${SERVICE_USER}（如已存在则跳过）..."
    ssh_sudo "id ${SERVICE_USER} >/dev/null 2>&1 || useradd -r -m -d /home/${SERVICE_USER} -s /bin/bash ${SERVICE_USER}"
    write_ok "用户就绪"

    write_info "[2/8] 创建目录 ${REMOTE_BASE} ..."
    ssh_sudo "mkdir -p ${REMOTE_BASE} ${REMOTE_BASE}/data ${REMOTE_BASE}/logs && chown -R ${SERVICE_USER}:${SERVICE_USER} ${REMOTE_BASE}"
    write_ok "目录就绪"

    write_info "[3/8] 推送代码..."
    rsync_code

    write_info "[4/8] 推送 .env ..."
    rsync -az -e ssh "$LOCAL_ENV_FILE" "${REMOTE_HOST}:/tmp/agent-calendar.env"
    ssh_sudo "install -m 600 -o ${SERVICE_USER} -g ${SERVICE_USER} /tmp/agent-calendar.env ${REMOTE_BASE}/.env && rm -f /tmp/agent-calendar.env"
    write_ok ".env 已部署（权限 600）"

    write_info "[5/8] 创建 venv 并安装依赖..."
    ssh_sudo "sudo -u ${SERVICE_USER} bash -lc 'cd ${REMOTE_BASE} && ${PYTHON_BIN} -m venv .venv && .venv/bin/pip install --upgrade pip --quiet && .venv/bin/pip install -e ./app_src --quiet'"
    write_ok "venv + 依赖安装完成"

    write_info "[6/8] 运行 Alembic 迁移..."
    ssh_sudo "sudo -u ${SERVICE_USER} bash -lc 'cd ${REMOTE_BASE}/app_src && ../.venv/bin/alembic upgrade head'"
    write_ok "数据库初始化完成"

    write_info "[7/8] 安装 systemd 单元..."
    install_systemd_unit
    write_ok "systemd 单元已安装"

    write_info "[8/8] 启动服务..."
    ssh_sudo "systemctl daemon-reload && systemctl enable --now ${SERVICE_NAME}"
    sleep 2
    if check_healthz; then
        write_ok "服务已启动并通过 /healthz 检测"
    else
        write_err "服务起来了但 /healthz 没响应，请用 logs 查看"
    fi

    log_msg "setup done"
}

install_systemd_unit() {
    local unit_path="/etc/systemd/system/${SERVICE_NAME}.service"
    # 用 heredoc 在远端直接写文件，避免本地拼接转义
    ssh_sudo "cat > ${unit_path} <<'UNIT'
[Unit]
Description=Agent-Calendar Backend
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${REMOTE_BASE}/app_src
EnvironmentFile=${REMOTE_BASE}/.env
ExecStart=${REMOTE_BASE}/.venv/bin/uvicorn app.main:app \\
          --host ${LISTEN_HOST} --port ${LISTEN_PORT} \\
          --workers 1 --limit-concurrency 5 --backlog 10
Restart=on-failure
RestartSec=5

# 资源硬限（见项目 CLAUDE.md 的资源约束章节）
MemoryMax=320M
MemoryHigh=280M

# 沙箱
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=${REMOTE_BASE}
ProtectHome=true

[Install]
WantedBy=multi-user.target
UNIT
chmod 644 ${unit_path}"
}

# ── 增量部署（routine update） ──
op_deploy() {
    ssh_check || return 1
    log_msg "deploy start"

    rsync_code

    # 检测 pyproject 是否变化，决定是否要 reinstall deps
    local local_hash
    local_hash=$(shasum -a 256 "${LOCAL_SERVER_DIR}/pyproject.toml" | awk '{print $1}')
    local remote_hash
    remote_hash=$(ssh_run "test -f ${REMOTE_BASE}/.pyproject.hash && cat ${REMOTE_BASE}/.pyproject.hash || echo none")

    if [ "$local_hash" != "$remote_hash" ]; then
        write_info "检测到 pyproject.toml 变化，重装依赖..."
        ssh_sudo "sudo -u ${SERVICE_USER} bash -lc 'cd ${REMOTE_BASE} && .venv/bin/pip install -e ./app_src --quiet'"
        ssh_sudo "echo ${local_hash} > ${REMOTE_BASE}/.pyproject.hash && chown ${SERVICE_USER}:${SERVICE_USER} ${REMOTE_BASE}/.pyproject.hash"
        write_ok "依赖更新完成"
    else
        write_dim "pyproject.toml 无变化，跳过依赖安装"
    fi

    write_info "运行 Alembic 迁移（幂等）..."
    ssh_sudo "sudo -u ${SERVICE_USER} bash -lc 'cd ${REMOTE_BASE}/app_src && ../.venv/bin/alembic upgrade head'"

    write_info "重启服务..."
    ssh_sudo "systemctl restart ${SERVICE_NAME}"
    sleep 2

    if check_healthz; then
        write_ok "部署完成并通过 /healthz"
    else
        write_err "服务重启了但 /healthz 没响应，请 logs 排查"
    fi
    log_msg "deploy done"
}

# ── 健康检查 ──
check_healthz() {
    ssh_run "curl -fsS -o /dev/null -w '%{http_code}' http://${LISTEN_HOST}:${LISTEN_PORT}/healthz" 2>/dev/null \
        | grep -q '^200$'
}

# ── 状态 ──
op_status() {
    ssh_check || return 1
    echo ""
    write_info "── systemd 状态 ──"
    ssh_sudo "systemctl status ${SERVICE_NAME} --no-pager --lines=0" 2>&1 | sed 's/^/    /' >&2 || true

    echo ""
    write_info "── 内存占用 ──"
    ssh_run "systemctl show ${SERVICE_NAME} --property=MemoryCurrent,MemoryMax,MemoryHigh,MainPID,ActiveState" 2>&1 \
        | sed 's/^/    /' >&2 || true

    echo ""
    write_info "── /healthz ──"
    if check_healthz; then
        write_ok "通过"
    else
        write_err "失败"
    fi

    echo ""
    write_info "── 最近 10 条日志 ──"
    ssh_sudo "journalctl -u ${SERVICE_NAME} -n 10 --no-pager" 2>&1 | sed 's/^/    /' >&2 || true
}

# ── 日志跟随 ──
op_logs() {
    ssh_check || return 1
    write_info "Ctrl+C 退出"
    ssh -t "$REMOTE_HOST" "$SUDO_CMD journalctl -u ${SERVICE_NAME} -f --no-pager" || true
}

# ── 服务控制 ──
op_restart() {
    ssh_check || return 1
    ssh_sudo "systemctl restart ${SERVICE_NAME}"
    sleep 2
    if check_healthz; then write_ok "重启完成 + /healthz 通过"; else write_err "/healthz 失败"; fi
    log_msg "restart"
}

op_start() {
    ssh_check || return 1
    ssh_sudo "systemctl start ${SERVICE_NAME}"
    write_ok "已启动"
    log_msg "start"
}

op_stop() {
    ssh_check || return 1
    confirm "确认停止 ${SERVICE_NAME}" || return 0
    ssh_sudo "systemctl stop ${SERVICE_NAME}"
    write_ok "已停止"
    log_msg "stop"
}

# ── DB 备份 ──
op_backup_db() {
    ssh_check || return 1
    local ts dst
    ts=$(date +"%Y%m%d_%H%M%S")
    dst="${LOCAL_BACKUP_DIR}/data_${ts}.db"

    write_info "从 VPS 拉取数据库..."
    log_msg "backup_db start"
    # SQLite hot backup（避免读到正在写入的事务中间态）
    ssh_sudo "sudo -u ${SERVICE_USER} ${REMOTE_BASE}/.venv/bin/python -c \"
import sqlite3
src = sqlite3.connect('${REMOTE_BASE}/data/data.db')
dst = sqlite3.connect('/tmp/data_backup.db')
src.backup(dst); dst.close(); src.close()
\""
    rsync -az -e ssh "${REMOTE_HOST}:/tmp/data_backup.db" "$dst"
    ssh_run "rm -f /tmp/data_backup.db"

    write_ok "已备份到 ${dst}"

    # 轮转：保留最新 N 份
    local backups=()
    while IFS= read -r f; do
        [ -n "$f" ] && backups+=("$f")
    done < <(find "$LOCAL_BACKUP_DIR" -maxdepth 1 -type f -name 'data_*.db' | sort -r)

    if [ ${#backups[@]} -gt "$MAX_DB_BACKUPS" ]; then
        local old=("${backups[@]:$MAX_DB_BACKUPS}")
        for f in "${old[@]}"; do
            rm -f "$f"
            write_dim "删除旧备份: $(basename "$f")"
        done
    fi
    log_msg "backup_db done file=${dst}"
}

# ── DB 恢复 ──
op_restore_db() {
    ssh_check || return 1
    local backups=()
    while IFS= read -r f; do
        [ -n "$f" ] && backups+=("$f")
    done < <(find "$LOCAL_BACKUP_DIR" -maxdepth 1 -type f -name 'data_*.db' | sort -r)

    if [ ${#backups[@]} -eq 0 ]; then
        write_err "没有可用备份"
        return 1
    fi

    write_info "可用备份："
    for i in "${!backups[@]}"; do
        write_info "  $((i+1)). $(basename "${backups[$i]}")"
    done
    read_choice "选择恢复哪个 [1-${#backups[@]}] (0 取消): "
    local idx=$((REPLY - 1))
    if [ "$idx" -lt 0 ] || [ "$idx" -ge ${#backups[@]} ]; then
        write_dim "取消"
        return 0
    fi
    local src="${backups[$idx]}"

    write_warn "将覆盖远端 ${REMOTE_BASE}/data/data.db"
    confirm "确认恢复 $(basename "$src")" || return 0

    log_msg "restore_db start src=${src}"
    write_info "停服..."
    ssh_sudo "systemctl stop ${SERVICE_NAME}"

    rsync -az -e ssh "$src" "${REMOTE_HOST}:/tmp/restore.db"
    ssh_sudo "install -m 600 -o ${SERVICE_USER} -g ${SERVICE_USER} /tmp/restore.db ${REMOTE_BASE}/data/data.db && rm -f /tmp/restore.db"

    write_info "启服..."
    ssh_sudo "systemctl start ${SERVICE_NAME}"
    sleep 2
    if check_healthz; then write_ok "恢复完成 + /healthz 通过"; else write_err "/healthz 失败"; fi
    log_msg "restore_db done"
}

# ── 推送 .env（更新配置） ──
op_push_env() {
    ssh_check || return 1
    if [ ! -f "$LOCAL_ENV_FILE" ]; then
        write_err "本地 ${LOCAL_ENV_FILE} 不存在"
        return 1
    fi
    write_warn "将用本地 server/.env 覆盖远端 ${REMOTE_BASE}/.env"
    confirm "确认覆盖远端 .env" || return 0

    rsync -az -e ssh "$LOCAL_ENV_FILE" "${REMOTE_HOST}:/tmp/agent-calendar.env"
    ssh_sudo "install -m 600 -o ${SERVICE_USER} -g ${SERVICE_USER} /tmp/agent-calendar.env ${REMOTE_BASE}/.env && rm -f /tmp/agent-calendar.env"
    write_ok ".env 已更新"
    if confirm "立即重启服务以加载新配置"; then
        op_restart
    fi
    log_msg "push_env done"
}

# ── SSH ──
op_ssh() {
    write_info "进入 VPS shell（exit 退出）"
    ssh -t "$REMOTE_HOST" || true
}

# ── 卸载（危险） ──
op_uninstall() {
    ssh_check || return 1
    write_err "[!] 该操作会：停止并禁用服务、删除 ${REMOTE_BASE} 整个目录、删除 systemd 单元"
    write_err "[!] 数据库不会保留，请先手动 backup-db"
    confirm "我已理解风险，确认卸载" || return 0
    confirm "再次确认（不可恢复）" || return 0

    log_msg "uninstall start"
    ssh_sudo "systemctl disable --now ${SERVICE_NAME} 2>/dev/null || true"
    ssh_sudo "rm -f /etc/systemd/system/${SERVICE_NAME}.service && systemctl daemon-reload"
    ssh_sudo "rm -rf ${REMOTE_BASE}"
    write_ok "已卸载"
    log_msg "uninstall done"
}

# ── 菜单 ──
show_menu() {
    check_deps

    while true; do
        clear
        echo ""
        echo -e "  ${CYAN}╔════════════════════════════════════════════╗${NC}"
        echo -e "  ${CYAN}║   Agent-Calendar VPS 部署引导 (macOS)      ║${NC}"
        echo -e "  ${CYAN}╚════════════════════════════════════════════╝${NC}"
        echo ""
        write_info "远端:       ${REMOTE_HOST}"
        write_info "安装目录:   ${REMOTE_BASE}"
        write_info "服务名:     ${SERVICE_NAME}"
        write_info "监听:       ${LISTEN_HOST}:${LISTEN_PORT}"
        echo ""
        echo -e "    ${CYAN}1.${NC} 首次部署 (setup)               ${DIM}— 用户/目录/venv/迁移/systemd 一条龙${NC}"
        echo -e "    ${CYAN}2.${NC} 增量部署 (deploy)              ${DIM}— rsync 代码 + 必要时重装依赖 + 迁移 + 重启${NC}"
        echo -e "    ${CYAN}3.${NC} 查看状态 (status)              ${DIM}— systemd + 内存 + /healthz + 最近日志${NC}"
        echo -e "    ${CYAN}4.${NC} 跟随日志 (logs -f)"
        echo -e "    ${CYAN}5.${NC} 重启 (restart)"
        echo -e "    ${CYAN}6.${NC} 启动 (start)"
        echo -e "    ${CYAN}7.${NC} 停止 (stop)"
        echo -e "    ${CYAN}8.${NC} 备份数据库 (backup-db)         ${DIM}— SQLite hot backup → 本地 backups/db/${NC}"
        echo -e "    ${CYAN}9.${NC} 恢复数据库 (restore-db)"
        echo -e "   ${CYAN}10.${NC} 推送 .env (push-env)           ${DIM}— 用本地 server/.env 覆盖远端${NC}"
        echo -e "   ${CYAN}11.${NC} SSH 进入 VPS"
        echo -e "    ${RED}99.${NC} 卸载 (uninstall)               ${DIM}— 危险，会删除整个安装${NC}"
        echo -e "    ${DIM}0. 退出${NC}"

        read_choice "请选择: "
        case "$REPLY" in
             1) op_setup;       read -r -p "  按回车继续..." ;;
             2) op_deploy;      read -r -p "  按回车继续..." ;;
             3) op_status;      read -r -p "  按回车继续..." ;;
             4) op_logs;        read -r -p "  按回车继续..." ;;
             5) op_restart;     read -r -p "  按回车继续..." ;;
             6) op_start;       read -r -p "  按回车继续..." ;;
             7) op_stop;        read -r -p "  按回车继续..." ;;
             8) op_backup_db;   read -r -p "  按回车继续..." ;;
             9) op_restore_db;  read -r -p "  按回车继续..." ;;
            10) op_push_env;    read -r -p "  按回车继续..." ;;
            11) op_ssh;         read -r -p "  按回车继续..." ;;
            99) op_uninstall;   read -r -p "  按回车继续..." ;;
             0) exit 0 ;;
        esac
    done
}

# ── 非交互命令（CI/脚本调用）──
# 用法：./deploy.sh <cmd>
if [ $# -gt 0 ]; then
    check_deps
    case "$1" in
        setup)       op_setup ;;
        deploy)      op_deploy ;;
        status)      op_status ;;
        logs)        op_logs ;;
        restart)     op_restart ;;
        start)       op_start ;;
        stop)        op_stop ;;
        backup-db)   op_backup_db ;;
        restore-db)  op_restore_db ;;
        push-env)    op_push_env ;;
        ssh)         op_ssh ;;
        uninstall)   op_uninstall ;;
        *)
            write_err "未知命令: $1"
            write_info "用法: $0 [setup|deploy|status|logs|restart|start|stop|backup-db|restore-db|push-env|ssh|uninstall]"
            write_info "不带参数则进入交互菜单"
            exit 1
            ;;
    esac
else
    show_menu
fi
