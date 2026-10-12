"""A fast, safe, and responsive desktop-control engine for Windows."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import urllib.parse
import webbrowser
import winreg
from difflib import get_close_matches
from typing import Callable, Optional
import time

import pyautogui

from .brain import Decision
from .config import Settings

SAFE_KEYS = {
    "enter", "esc", "tab", "space", "backspace", "delete", "home", "end",
    "up", "down", "left", "right", "pageup", "pagedown",
    "volumeup", "volumedown", "volumemute", "playpause", "nexttrack", "prevtrack",
}

SAFE_HOTKEYS = {
    ("ctrl", "c"), ("ctrl", "v"), ("ctrl", "a"), ("ctrl", "z"),
    ("alt", "tab"), ("win", "d"), ("ctrl", "w"), ("ctrl", "t"),
}

COMMON_APP_COMMANDS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "settings": ["cmd.exe", "/c", "start", "", "ms-settings:"],
    "task manager": ["taskmgr.exe"],
    "taskmgr": ["taskmgr.exe"],
    "paint": ["mspaint.exe"],
    "mspaint": ["mspaint.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "terminal": ["wt.exe"],
    "windows terminal": ["wt.exe"],
    "camera": ["cmd.exe", "/c", "start", "", "microsoft.windows.camera:"],
    "control panel": ["control.exe"],
    "chrome": ["cmd.exe", "/c", "start", "", "chrome"],
    "google chrome": ["cmd.exe", "/c", "start", "", "chrome"],
    "browser": ["cmd.exe", "/c", "start", "", "https://www.google.com"],
    "web browser": ["cmd.exe", "/c", "start", "", "https://www.google.com"],
    "edge": ["cmd.exe", "/c", "start", "", "msedge"],
    "microsoft edge": ["cmd.exe", "/c", "start", "", "msedge"],
    "brave": ["cmd.exe", "/c", "start", "", "brave"],
    "firefox": ["cmd.exe", "/c", "start", "", "firefox"],
    "spotify": ["cmd.exe", "/c", "start", "", "spotify:"],
    "discord": ["cmd.exe", "/c", "start", "", "discord:"],
    "steam": ["cmd.exe", "/c", "start", "", "steam:"],
    "whatsapp": ["explorer.exe", r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"],
    "vscode": ["code"],
    "vs code": ["code"],
    "visual studio code": ["code"],
    "code": ["code"],
    "word": ["winword.exe"],
    "excel": ["excel.exe"],
    "powerpoint": ["powerpnt.exe"],
}


class ActionEngine:
    """Execute validated UI and desktop control actions with high responsiveness."""

    def __init__(self, settings: Settings, confirm: Callable[[Decision], bool] | None = None) -> None:
        self.settings = settings
        self.log = logging.getLogger(self.__class__.__name__)
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = settings.pyautogui_pause_seconds
        self.confirm = confirm or self._confirm_in_terminal

        # Fast local shortcuts and start app cache
        self._shortcut_apps: dict[str, str] = {}
        self._registry_apps: dict[str, str] = {}
        self._start_apps: list[dict[str, str]] = []
        self._load_app_indexes()

    def _load_app_indexes(self) -> None:
        """Scan Start Menu folders and Registry App Paths in milliseconds."""
        try:
            menu_folders = [
                os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
                os.path.expandvars(r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs"),
            ]
            for folder in menu_folders:
                if not os.path.exists(folder):
                    continue
                for root, _, files in os.walk(folder):
                    for file in files:
                        if file.lower().endswith((".lnk", ".url")):
                            name = file[:-4].lower().strip()
                            self._shortcut_apps[name] = os.path.join(root, file)
        except Exception as exc:
            self.log.debug("Error scanning Start Menu shortcuts: %s", exc)

        try:
            for root_key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(root_key, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths") as key:
                        num_subkeys = winreg.QueryInfoKey(key)[0]
                        for i in range(num_subkeys):
                            subkey_name = winreg.EnumKey(key, i)
                            app_name = subkey_name.lower().replace(".exe", "").strip()
                            try:
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    path = winreg.QueryValue(subkey, "")
                                    if path:
                                        self._registry_apps[app_name] = path
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception as exc:
            self.log.debug("Error scanning Registry App Paths: %s", exc)

        # Background cache for UWP / StartApps catalog
        threading.Thread(target=self._load_uwp_start_apps, daemon=True).start()

    def _load_uwp_start_apps(self) -> None:
        """Cache Get-StartApps in background without blocking assistant startup."""
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            data = json.loads(proc.stdout or "[]")
            if isinstance(data, dict):
                data = [data]
            self._start_apps = [item for item in data if isinstance(item, dict) and item.get("Name") and item.get("AppID")]
        except Exception as exc:
            self.log.debug("Could not cache UWP StartApps: %s", exc)

    @staticmethod
    def _confirm_in_terminal(decision: Decision) -> bool:
        answer = input(f"Allow desktop action {decision.action!r}? [y/N]: ").strip().lower()
        return answer in {"y", "yes"}

    def execute(self, decision: Decision) -> bool:
        if decision.action == "none":
            return True
        if self.settings.action_mode == "disabled":
            self.log.info("Action mode disabled; skipped %s", decision.action)
            return False
        if self.settings.action_mode == "confirm" and not self.confirm(decision):
            self.log.info("User declined %s", decision.action)
            return False
        try:
            self._execute_validated(decision)
            return True
        except pyautogui.FailSafeException:
            self.log.warning("PyAutoGUI fail-safe triggered. Move mouse away from screen corner.")
            return False
        except Exception as exc:
            self.log.exception("Desktop action '%s' failed: %s", decision.action, exc)
            return False

    def _coordinates(self, decision: Decision) -> tuple[int, int]:
        assert decision.x is not None and decision.y is not None
        width, height = pyautogui.size()
        if not (0 <= decision.x < width and 0 <= decision.y < height):
            raise ValueError(f"Coordinates ({decision.x}, {decision.y}) outside {width}x{height} screen")
        return decision.x, decision.y

    def _execute_validated(self, decision: Decision) -> None:
        act = decision.action
        if act == "move":
            pyautogui.moveTo(*self._coordinates(decision), duration=0.25)
        elif act == "click":
            pyautogui.click(*self._coordinates(decision), clicks=max(1, min(decision.clicks, 2)))
        elif act == "double_click":
            pyautogui.doubleClick(*self._coordinates(decision), interval=0.15)
        elif act == "type":
            text_to_type = (decision.text or "")[:5_000]
            try:
                import pyperclip
                pyperclip.copy(text_to_type)
                time.sleep(0.05)
                pyautogui.hotkey("ctrl", "v")
            except Exception:
                pyautogui.write(text_to_type, interval=0.01)
        elif act == "press":
            key = (decision.key or "").lower()
            if key not in SAFE_KEYS:
                raise ValueError(f"Rejected unsafe key: {key}")
            pyautogui.press(key)
        elif act == "hotkey":
            keys = tuple(k.lower() for k in decision.keys)
            if keys not in SAFE_HOTKEYS:
                raise ValueError(f"Rejected unsafe hotkey: {keys}")
            pyautogui.hotkey(*keys)
        elif act == "scroll":
            pyautogui.scroll(max(-20, min(decision.scrolls, 20)))
        elif act in {"open_app", "open_named_app"}:
            self._open_any_app(decision.app or "")
        elif act == "open_url":
            self._open_url(decision.text or "", in_chrome=False)
        elif act == "open_url_in_chrome":
            self._open_url(decision.text or "", in_chrome=True)
        elif act == "play_youtube":
            self._play_youtube(decision.text or "", in_chrome=False)
        elif act == "play_youtube_in_chrome":
            self._play_youtube(decision.text or "", in_chrome=True)
        elif act == "volume_up":
            for _ in range(3):
                pyautogui.press("volumeup")
        elif act == "volume_down":
            for _ in range(3):
                pyautogui.press("volumedown")
        elif act == "mute":
            pyautogui.press("volumemute")
        elif act == "media_play_pause":
            pyautogui.press("playpause")
        elif act == "media_next":
            pyautogui.press("nexttrack")
        elif act == "media_prev":
            pyautogui.press("prevtrack")
        elif act == "college_wifi_login":
            self._college_wifi_login()
        elif act == "open_whatsapp":
            self._open_whatsapp_with_password()
        elif act == "search_web":
            query = urllib.parse.quote_plus(decision.text or "")
            self._open_url(f"https://www.google.com/search?q={query}", in_chrome=False)
        else:
            raise ValueError(f"Unhandled action {act}")

    def _college_wifi_login(self) -> None:
        """Automate login to RIT Roorkee campus captive portal."""
        portal_url = os.getenv("COLLEGE_WIFI_PORTAL", "https://192.168.10.1:8090/httpclient.html")
        username = os.getenv("COLLEGE_WIFI_USERNAME", "26010106335")
        password = os.getenv("COLLEGE_WIFI_PASSWORD", "Ayush@2008")

        try:
            import ssl
            import urllib.parse
            import urllib.request
            api_url = "https://192.168.10.1:8090/login.xml"
            post_data = urllib.parse.urlencode({
                "mode": "191",
                "username": username,
                "password": password,
                "a": str(int(time.time() * 1000)),
                "producttype": "0",
            }).encode("utf-8")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                api_url,
                data=post_data,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=4) as resp:
                result = resp.read().decode("utf-8", errors="ignore")
                if "status" in result.lower() or "success" in result.lower() or "live" in result.lower():
                    self.log.info("WiFi portal login succeeded via direct HTTP POST")
                    return
        except Exception as exc:
            self.log.debug("Direct HTTP portal login skipped: %s", exc)

        self.log.info("Opening college WiFi portal in Chrome: %s", portal_url)
        self._open_url(portal_url, in_chrome=True)

        def _fill_creds():
            time.sleep(2.5)
            try:
                pyautogui.write(username, interval=0.03)
                pyautogui.press("tab")
                time.sleep(0.2)
                pyautogui.write(password, interval=0.03)
                pyautogui.press("enter")
            except Exception as e:
                self.log.debug("Auto-fill WiFi portal error: %s", e)

        threading.Thread(target=_fill_creds, daemon=True).start()

    def _open_whatsapp_with_password(self) -> None:
        """Open WhatsApp Desktop and automatically enter the passcode."""
        password = os.getenv("WHATSAPP_PASSWORD", "Arpit@3007")
        self.log.info("Launching WhatsApp Desktop...")

        launched = False
        try:
            subprocess.Popen(["explorer.exe", r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"], shell=False)
            launched = True
        except Exception as exc:
            self.log.debug("WhatsApp UWP launch failed: %s", exc)

        if not launched:
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "", "whatsapp:"], shell=False)
            except Exception as exc:
                self.log.warning("WhatsApp URI launch failed: %s", exc)
                self._open_any_app("whatsapp")

        def _fill_pass():
            time.sleep(2.5)
            try:
                focus_script = "$wshell = New-Object -ComObject WScript.Shell; $wshell.AppActivate('WhatsApp')"
                subprocess.run(["powershell.exe", "-NoProfile", "-Command", focus_script], capture_output=True, timeout=5)
                time.sleep(0.5)

                import pyperclip
                pyperclip.copy(password)
                time.sleep(0.1)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.2)
                pyautogui.press("enter")
                self.log.info("WhatsApp password auto-typed successfully")
            except Exception as e:
                self.log.warning("WhatsApp auto-password error: %s", e)
                try:
                    pyautogui.write(password, interval=0.02)
                    pyautogui.press("enter")
                except Exception:
                    pass

        threading.Thread(target=_fill_pass, daemon=True).start()

    def _open_url(self, url: str, in_chrome: bool = False) -> None:
        """Open web URL in browser."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        if in_chrome:
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "", "chrome", url], shell=False)
                return
            except Exception:
                pass
        webbrowser.open_new_tab(url)

    def _play_youtube(self, query: str, in_chrome: bool = False) -> None:
        """Find video on YouTube and play it with autoplay, falling back to search page."""
        query = query.strip()
        if not query:
            self._open_url("https://www.youtube.com", in_chrome=in_chrome)
            return

        video_id: Optional[str] = None
        try:
            from yt_dlp import YoutubeDL
            options = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True,
                "socket_timeout": 2,
            }
            with YoutubeDL(options) as client:
                result = client.extract_info(f"ytsearch1:{query}", download=False)
            entries = result.get("entries") or []
            first = next((e for e in entries if e and e.get("id")), None)
            if first:
                video_id = first["id"]
        except Exception as exc:
            self.log.debug("yt-dlp quick resolution skipped: %s", exc)

        if video_id:
            url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
        else:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.youtube.com/results?search_query={encoded}"

        self._open_url(url, in_chrome=in_chrome)

    def _open_any_app(self, requested_name: str) -> None:
        """Universal launcher: known commands, Start Menu, Registry, or UWP app."""
        target = requested_name.strip().casefold()
        if not target:
            raise ValueError("Application name was empty")

        # 1. Check known aliases
        if target in COMMON_APP_COMMANDS:
            cmd = COMMON_APP_COMMANDS[target]
            # If wt is not installed, fallback to powershell
            if cmd == ["wt.exe"] and not shutil.which("wt.exe"):
                cmd = ["powershell.exe"]
            self.log.info("Launching builtin app command: %s", cmd)
            subprocess.Popen(cmd, shell=False)
            return

        # 2. Check Start Menu shortcuts (.lnk / .url)
        if target in self._shortcut_apps:
            path = self._shortcut_apps[target]
            self.log.info("Launching shortcut: %s", path)
            os.startfile(path)
            return

        for name, path in self._shortcut_apps.items():
            if target in name or name in target:
                self.log.info("Launching matched shortcut (%s): %s", name, path)
                os.startfile(path)
                return

        # 3. Check Registry App Paths
        if target in self._registry_apps:
            path = self._registry_apps[target]
            self.log.info("Launching registry app path: %s", path)
            subprocess.Popen([path], shell=False)
            return

        for name, path in self._registry_apps.items():
            if target in name or name in target:
                self.log.info("Launching matched registry app (%s): %s", name, path)
                subprocess.Popen([path], shell=False)
                return

        # 4. Check UWP / StartApps catalog
        for app in self._start_apps:
            app_name = app.get("Name", "").casefold()
            if target == app_name or target in app_name or app_name in target:
                app_id = app.get("AppID")
                if app_id:
                    self.log.info("Launching UWP app: %s", app.get("Name"))
                    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"], shell=False)
                    return

        # 5. Fuzzy match against all available shortcuts
        candidates = list(self._shortcut_apps.keys()) + list(self._registry_apps.keys())
        matches = get_close_matches(target, candidates, n=1, cutoff=0.55)
        if matches:
            best = matches[0]
            if best in self._shortcut_apps:
                self.log.info("Fuzzy launched shortcut (%s): %s", best, self._shortcut_apps[best])
                os.startfile(self._shortcut_apps[best])
                return
            if best in self._registry_apps:
                self.log.info("Fuzzy launched registry app (%s): %s", best, self._registry_apps[best])
                subprocess.Popen([self._registry_apps[best]], shell=False)
                return

        # 6. Fallback to Windows cmd /c start "" <target>
        self.log.info("Attempting generic Windows start command for: %s", target)
        subprocess.Popen(["cmd.exe", "/c", "start", "", target], shell=False)
