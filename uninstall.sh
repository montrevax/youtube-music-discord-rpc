#!/usr/bin/env bash
set -e

BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
CONFIG_DIR="$HOME/.config/ytm-discord-rpc"

echo "=== Удаление YouTube Music Discord RPC ==="

if systemctl --user is-active --quiet ytm-discord-rpc.service 2>/dev/null; then
    systemctl --user stop ytm-discord-rpc.service
    echo "✓ Служба остановлена"
fi

if systemctl --user is-enabled --quiet ytm-discord-rpc.service 2>/dev/null; then
    systemctl --user disable ytm-discord-rpc.service
    echo "✓ Автозапуск службы отключен"
fi

rm -f "$SYSTEMD_DIR/ytm-discord-rpc.service"
systemctl --user daemon-reload
echo "✓ Файл службы удален"

rm -f "$BIN_DIR/ytm-discord-rpc"
echo "✓ Симлинк удален: $BIN_DIR/ytm-discord-rpc"

read -p "Удалить конфигурацию и кэш ($CONFIG_DIR)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    rm -f "$HOME/.cache/ytm-discord-rpc.log"
    echo "✓ Конфигурация и кэш удалены"
fi

echo "=== Удаление завершено! ==="
