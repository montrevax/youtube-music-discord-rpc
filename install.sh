#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
CONFIG_DIR="$HOME/.config/ytm-discord-rpc"

echo "=== Установка YouTube Music Discord RPC ==="

mkdir -p "$BIN_DIR" "$SYSTEMD_DIR" "$CONFIG_DIR"

chmod +x "$SCRIPT_DIR/ytm_rpc.py"
ln -sf "$SCRIPT_DIR/ytm_rpc.py" "$BIN_DIR/ytm-discord-rpc"
echo "✓ Симлинк создан: $BIN_DIR/ytm-discord-rpc"

if [ ! -f "$CONFIG_DIR/config.json" ]; then
    cp "$SCRIPT_DIR/config.json" "$CONFIG_DIR/config.json"
    echo "✓ Создан файл конфигурации: $CONFIG_DIR/config.json"
else
    echo "✓ Файл конфигурации уже существует ($CONFIG_DIR/config.json)"
fi

cp "$SCRIPT_DIR/ytm-discord-rpc.service" "$SYSTEMD_DIR/ytm-discord-rpc.service"
systemctl --user daemon-reload
echo "✓ Служба systemd скопирована в $SYSTEMD_DIR"

systemctl --user enable --now ytm-discord-rpc.service
echo "✓ Служба активирована и запущена!"

echo ""
echo "Статус службы:"
systemctl --user status ytm-discord-rpc.service --no-pager
echo ""
echo "=== Установка завершена успешно! ==="
echo "Команды для управления:"
echo "  systemctl --user status ytm-discord-rpc"
echo "  systemctl --user restart ytm-discord-rpc"
echo "  systemctl --user stop ytm-discord-rpc"
echo "  journalctl --user -u ytm-discord-rpc -f"
echo "  ytm-discord-rpc --test"
