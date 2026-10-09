#!/usr/bin/env python3
import sys
import os
import time
import json
import uuid
import struct
import socket
import signal
import argparse
import urllib.request
import urllib.parse
import subprocess
from typing import Optional, Dict, Any, Tuple

DEFAULT_CLIENT_ID = "1177081335727267940"
CONFIG_DIR = os.path.expanduser("~/.config/ytm-discord-rpc")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
PID_FILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "ytm-discord-rpc.pid")

DEFAULT_CONFIG = {
    "client_id": DEFAULT_CLIENT_ID,
    "update_interval": 1.5,
    "show_pause_state": True,
    "pause_timeout_seconds": 300,
    "show_listen_button": True,
    "button_label": "Listen on YouTube Music",
    "fallback_icon": "https://music.youtube.com/img/favicon_144.png",
    "play_icon": "https://raw.githubusercontent.com/material-icons/material-icons/master/png/av/play_arrow/baseline_play_arrow_white_48dp.png",
    "pause_icon": "https://raw.githubusercontent.com/material-icons/material-icons/master/png/av/pause/baseline_pause_white_48dp.png",
    "log_level": "INFO"
}


def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                config.update(user_cfg)
        except Exception as e:
            print(f"[WARN] Ошибка загрузки {CONFIG_PATH}: {e}, используются настройки по умолчанию.", file=sys.stderr)
    return config


def log(msg: str, level: str = "INFO"):
    t = time.strftime("%H:%M:%S")
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARN": "\033[93m",
        "ERROR": "\033[91m",
        "RESET": "\033[0m"
    }
    use_color = sys.stdout.isatty()
    prefix = f"{colors[level]}[{level}]{colors['RESET']}" if use_color and level in colors else f"[{level}]"
    print(f"[{t}] {prefix} {msg}", flush=True)


class DiscordIPC:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.sock: Optional[socket.socket] = None
        self.connected = False

    def _find_socket(self) -> Optional[str]:
        uid = os.getuid()
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
        dirs = [
            runtime_dir,
            "/tmp",
            f"/run/user/{uid}",
            f"/run/user/{uid}/app/com.discordapp.Discord",
        ]
        candidates = []
        for d in dirs:
            if os.path.isdir(d):
                for i in range(10):
                    candidates.append(os.path.join(d, f"discord-ipc-{i}"))
                try:
                    for f in os.listdir(d):
                        if "discord-ipc" in f or "vesktop-ipc" in f:
                            candidates.append(os.path.join(d, f))
                except Exception:
                    pass

        for path in dict.fromkeys(candidates):
            if os.path.exists(path):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(1.0)
                    s.connect(path)
                    s.close()
                    return path
                except Exception:
                    continue
        return None

    def connect(self) -> bool:
        if self.connected:
            return True

        sock_path = self._find_socket()
        if not sock_path:
            return False

        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(3.0)
            self.sock.connect(sock_path)

            handshake = {"v": 1, "client_id": self.client_id}
            self._send_packet(0, handshake)
            op, resp = self._recv_packet()

            if resp.get("evt") == "READY":
                self.connected = True
                user = resp.get("data", {}).get("user", {})
                username = user.get("username", "Unknown")
                log(f"Подключено к Discord (пользователь: {username})", "SUCCESS")
                return True
            else:
                self.close()
                return False
        except Exception:
            self.close()
            return False

    def _recv_exact(self, n: int) -> bytes:
        if not self.sock:
            raise ConnectionResetError("Socket not connected")
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionResetError("Соединение разорвано Discord")
            buf.extend(chunk)
        return bytes(buf)

    def _recv_packet(self) -> Tuple[int, dict]:
        header = self._recv_exact(8)
        opcode, length = struct.unpack("<II", header)
        payload_bytes = self._recv_exact(length)
        payload = json.loads(payload_bytes.decode("utf-8"))
        return opcode, payload

    def _send_packet(self, opcode: int, data: dict):
        if not self.sock:
            raise ConnectionResetError("Socket not connected")
        payload = json.dumps(data).encode("utf-8")
        header = struct.pack("<II", opcode, len(payload))
        self.sock.sendall(header + payload)

    def set_activity(self, activity: Optional[dict]) -> bool:
        if not self.connected:
            return False

        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": activity
            },
            "nonce": str(uuid.uuid4())
        }

        try:
            self._send_packet(1, payload)
            self._recv_packet()
            return True
        except Exception as e:
            log(f"Ошибка отправки активности в Discord: {e}", "WARN")
            self.close()
            return False

    def clear_activity(self) -> bool:
        return self.set_activity(None)

    def close(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class CoverArtResolver:
    def __init__(self, fallback_url: str):
        self.fallback_url = fallback_url
        self.cache: Dict[str, Tuple[str, str]] = {}

    def resolve(self, artist: str, title: str) -> Tuple[str, str]:
        key = f"{artist.strip().lower()} - {title.strip().lower()}"
        if key in self.cache:
            return self.cache[key]

        query = f"{artist} {title}".strip()

        try:
            url = f"https://api.deezer.com/search?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=2.5) as r:
                data = json.loads(r.read().decode("utf-8"))
                if data.get("data"):
                    item = data["data"][0]
                    cover = (
                        item.get("album", {}).get("cover_big")
                        or item.get("album", {}).get("cover_medium")
                        or item.get("artist", {}).get("picture_big")
                    )
                    album = item.get("album", {}).get("title", "")
                    if cover:
                        self.cache[key] = (cover, album)
                        return cover, album
        except Exception:
            pass

        try:
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=2.5) as r:
                data = json.loads(r.read().decode("utf-8"))
                if data.get("resultCount", 0) > 0:
                    item = data["results"][0]
                    cover_100 = item.get("artworkUrl100", "")
                    cover = cover_100.replace("100x100bb.jpg", "512x512bb.jpg") if cover_100 else ""
                    album = item.get("collectionName", "")
                    if cover:
                        self.cache[key] = (cover, album)
                        return cover, album
        except Exception:
            pass

        res = (self.fallback_url, "")
        self.cache[key] = res
        return res


def sanitize_text(text: Optional[str], fallback: str = "Unknown") -> str:
    if not text or not text.strip():
        return fallback
    clean = text.strip()
    if len(clean) < 2:
        clean = clean + " "
    if len(clean) > 128:
        clean = clean[:125] + "..."
    return clean


class MediaMonitor:
    @staticmethod
    def find_player() -> Optional[str]:
        try:
            out = subprocess.check_output(["playerctl", "-l"], stderr=subprocess.DEVNULL).decode("utf-8")
        except Exception:
            return None

        players = [p.strip() for p in out.splitlines() if p.strip().startswith("chromium")]
        if not players:
            return None

        for p in players:
            if "instance" in p:
                pid = p.split("instance")[-1]
                try:
                    with open(f"/proc/{pid}/cmdline", "rb") as f:
                        cmdline = f.read().decode("utf-8", errors="ignore")
                        if "cinhimbnkkaeohfgghhklpknlkffjgod" in cmdline or "music.youtube.com" in cmdline:
                            return p
                except Exception:
                    pass

        try:
            hypr_out = subprocess.check_output(["hyprctl", "clients", "-j"], stderr=subprocess.DEVNULL).decode("utf-8")
            clients = json.loads(hypr_out)
            for c in clients:
                t = (c.get("title", "") + " " + c.get("initialTitle", "")).lower()
                if "youtube music" in t:
                    pid = str(c.get("pid"))
                    target = f"chromium.instance{pid}"
                    if target in players:
                        return target
        except Exception:
            pass

        for p in players:
            try:
                st = subprocess.check_output(["playerctl", "-p", p, "status"], stderr=subprocess.DEVNULL).decode("utf-8").strip()
                if st == "Playing":
                    return p
            except Exception:
                pass

        return players[0]

    @staticmethod
    def get_metadata(player: str) -> Optional[dict]:
        try:
            fmt = "{{status}}\t{{title}}\t{{artist}}\t{{album}}\t{{mpris:length}}\t{{position}}\t{{mpris:artUrl}}"
            cmd = ["playerctl", "-p", player, "metadata", "--format", fmt]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()
            if not out:
                return None

            parts = out.split("\t")
            status = parts[0] if len(parts) > 0 else ""
            title = parts[1] if len(parts) > 1 else ""
            artist = parts[2] if len(parts) > 2 else ""
            album = parts[3] if len(parts) > 3 else ""
            raw_len = parts[4] if len(parts) > 4 else "0"
            raw_pos = parts[5] if len(parts) > 5 else "0"
            art_url = parts[6] if len(parts) > 6 else ""

            length_sec = int(raw_len) // 1_000_000 if raw_len.isdigit() else 0

            pos_sec = 0
            if raw_pos:
                try:
                    pos_sec = int(float(raw_pos)) // 1_000_000
                except ValueError:
                    pos_sec = 0

            return {
                "player": player,
                "status": status,
                "title": title,
                "artist": artist,
                "album": album,
                "length": length_sec,
                "position": pos_sec,
                "art_url": art_url
            }
        except Exception:
            return None


def run_rpc_daemon(config: dict):
    ipc = DiscordIPC(config["client_id"])
    art_resolver = CoverArtResolver(config["fallback_icon"])
    monitor = MediaMonitor()

    running = True

    def sig_handler(signum, frame):
        nonlocal running
        log("Завершение работы (получен сигнал остановки)...", "INFO")
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

    log(f"Запущен демон YouTube Music Discord RPC (PID: {os.getpid()})", "SUCCESS")

    last_track_key = None
    last_status = None
    last_update_time = 0
    pause_start_time = None
    was_active = False

    try:
        while running:
            if not ipc.connected:
                if not ipc.connect():
                    time.sleep(3.0)
                    continue

            player = monitor.find_player()
            meta = monitor.get_metadata(player) if player else None

            now = time.time()

            if not meta or not meta["title"] or meta["status"] in ("Stopped", ""):
                if was_active:
                    ipc.clear_activity()
                    was_active = False
                    last_track_key = None
                    last_status = None
                    log("Музыка остановлена. Активность Discord очищена.", "INFO")
                time.sleep(config["update_interval"])
                continue

            status = meta["status"]
            title = meta["title"]
            artist = meta["artist"] or "YouTube Music"
            track_key = f"{artist} - {title}"

            if status == "Paused":
                if pause_start_time is None:
                    pause_start_time = now

                if not config["show_pause_state"] or (now - pause_start_time > config["pause_timeout_seconds"]):
                    if was_active:
                        ipc.clear_activity()
                        was_active = False
                        log("На паузе дольше лимита. Активность Discord очищена.", "INFO")
                    time.sleep(config["update_interval"])
                    continue
            else:
                pause_start_time = None

            status_changed = status != last_status
            track_changed = track_key != last_track_key
            throttled_refresh = (now - last_update_time) > 15.0

            if track_changed or status_changed or throttled_refresh:
                cover_url, resolved_album = art_resolver.resolve(artist, title)
                display_album = meta["album"] or resolved_album or "YouTube Music"

                activity: Dict[str, Any] = {
                    "type": 2,
                    "details": sanitize_text(title),
                    "state": sanitize_text(artist),
                    "assets": {
                        "large_image": cover_url,
                        "large_text": sanitize_text(display_album),
                    }
                }

                if status == "Playing":
                    activity["assets"]["small_image"] = config["play_icon"]
                    activity["assets"]["small_text"] = "Воспроизведение"

                    if meta["length"] > 0:
                        start_ts = int(now - meta["position"])
                        end_ts = int(start_ts + meta["length"])
                        activity["timestamps"] = {
                            "start": start_ts,
                            "end": end_ts
                        }
                    else:
                        activity["timestamps"] = {
                            "start": int(now - meta["position"])
                        }
                else:
                    activity["assets"]["small_image"] = config["pause_icon"]
                    activity["assets"]["small_text"] = "На паузе"

                if config["show_listen_button"]:
                    query = urllib.parse.quote_plus(f"{artist} - {title}")
                    listen_url = f"https://music.youtube.com/search?q={query}"
                    activity["buttons"] = [
                        {
                            "label": config["button_label"],
                            "url": listen_url
                        }
                    ]

                success = ipc.set_activity(activity)
                if success:
                    was_active = True
                    last_track_key = track_key
                    last_status = status
                    last_update_time = now
                    st_str = "▶ Играет" if status == "Playing" else "⏸ Пауза"
                    log(f"{st_str}: {artist} — {title}", "INFO")

            time.sleep(config["update_interval"])

    finally:
        log("Очистка активности Discord перед выходом...", "INFO")
        try:
            ipc.clear_activity()
            ipc.close()
        except Exception:
            pass

        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass


def stop_daemon():
    if not os.path.exists(PID_FILE):
        log("Файл PID не найден. Демон, вероятно, не запущен.", "WARN")
        return

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        log(f"Отправлен сигнал остановки процессу {pid}.", "SUCCESS")
    except ProcessLookupError:
        log("Процесс не найден. Удаляю устаревший PID файл.", "WARN")
        os.remove(PID_FILE)
    except Exception as e:
        log(f"Ошибка при остановке: {e}", "ERROR")


def check_status():
    if not os.path.exists(PID_FILE):
        log("Демон не запущен (PID файл отсутствует).", "INFO")
        return

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        log(f"Демон активен и работает (PID: {pid}).", "SUCCESS")
    except ProcessLookupError:
        log("PID файл существует, но процесс не найден (зависший PID).", "WARN")
    except Exception as e:
        log(f"Статус неизвестен: {e}", "WARN")


def test_system():
    config = load_config()
    log("=== ТЕСТИРОВАНИЕ СИСТЕМЫ YTM RPC ===", "INFO")

    log("1. Проверка playerctl и плеера Chromium...", "INFO")
    player = MediaMonitor.find_player()
    if player:
        log(f"✓ Найден активный плеер: {player}", "SUCCESS")
        meta = MediaMonitor.get_metadata(player)
        if meta:
            log(f"  Статус: {meta['status']}", "INFO")
            log(f"  Название: {meta['title']}", "INFO")
            log(f"  Исполнитель: {meta['artist']}", "INFO")
            log(f"  Альбом: {meta['album'] or '(не указан)'}", "INFO")
            log(f"  Длительность: {meta['length']} сек", "INFO")
            log(f"  Позиция: {meta['position']} сек", "INFO")
        else:
            log("⚠ Метаданные плеера пусты.", "WARN")
    else:
        log("✗ Активный плеер Chromium / YouTube Music не найден.", "WARN")

    log("2. Поиск сокета Discord IPC...", "INFO")
    ipc = DiscordIPC(config["client_id"])
    sock_path = ipc._find_socket()
    if sock_path:
        log(f"✓ Сокет найден: {sock_path}", "SUCCESS")
        if ipc.connect():
            log("✓ Успешное рукопожатие с Discord RPC!", "SUCCESS")
            ipc.clear_activity()
            ipc.close()
        else:
            log("✗ Не удалось установить связь с Discord.", "ERROR")
    else:
        log("✗ Сокет Discord не найден. Убедитесь, что Discord запущен.", "ERROR")

    log("3. Тест поиска обложки трека...", "INFO")
    art_resolver = CoverArtResolver(config["fallback_icon"])
    test_artist = meta["artist"] if meta and meta["artist"] else "Queen"
    test_title = meta["title"] if meta and meta["title"] else "Bohemian Rhapsody"
    cover, alb = art_resolver.resolve(test_artist, test_title)
    log(f"✓ Обложка для '{test_artist} — {test_title}':", "SUCCESS")
    log(f"  URL: {cover}", "INFO")
    if alb:
        log(f"  Альбом: {alb}", "INFO")

    log("=== ТЕСТ ЗАВЕРШЕН ===", "INFO")


def main():
    parser = argparse.ArgumentParser(description="YouTube Music Discord Rich Presence Daemon for Linux Chromium")
    parser.add_argument("--daemon", "-d", action="store_true", help="Запустить в фоновом режиме (daemon)")
    parser.add_argument("--stop", "-k", action="store_true", help="Остановить фоновый демон")
    parser.add_argument("--status", "-s", action="store_true", help="Проверить статус демона")
    parser.add_argument("--test", "-t", action="store_true", help="Протестировать плеер, сокет Discord и поиск обложек")

    args = parser.parse_args()

    if args.stop:
        stop_daemon()
        return

    if args.status:
        check_status()
        return

    if args.test:
        test_system()
        return

    config = load_config()

    if args.daemon:
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)

        sys.stdout.flush()
        sys.stderr.flush()
        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())

        log_file_path = os.path.expanduser("~/.cache/ytm-discord-rpc.log")
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        log_f = open(log_file_path, "a", buffering=1, encoding="utf-8")
        os.dup2(log_f.fileno(), sys.stdout.fileno())
        os.dup2(log_f.fileno(), sys.stderr.fileno())

        run_rpc_daemon(config)
    else:
        run_rpc_daemon(config)


if __name__ == "__main__":
    main()
