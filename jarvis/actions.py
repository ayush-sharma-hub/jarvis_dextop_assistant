"""Safe Windows desktop-control engine; imports safely on Linux CI."""
from __future__ import annotations
import ctypes
import json
import logging
import os
import platform
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from difflib import get_close_matches
from typing import Callable, Optional

try:
    import pyautogui
except Exception:  # Linux test collection only; pyautogui can fail without DISPLAY.
    class _NoPyAutoGUI:
        class FailSafeException(Exception): pass
        def __getattr__(self, name: str): raise RuntimeError("pyautogui is required on Windows")
    pyautogui = _NoPyAutoGUI()  # type: ignore[assignment]

from .brain import ALLOWED_ACTIONS, Decision
from .config import Settings

SAFE_KEYS = {"enter", "esc", "tab", "space", "backspace", "delete", "home", "end", "up", "down", "left", "right", "pageup", "pagedown", "volumeup", "volumedown", "volumemute", "playpause", "nexttrack", "prevtrack"}
SAFE_HOTKEYS = {("ctrl", "c"), ("ctrl", "v"), ("ctrl", "a"), ("ctrl", "z"), ("alt", "tab"), ("win", "d"), ("ctrl", "w"), ("ctrl", "t")}
COMMON_APP_COMMANDS = {
    "notepad":["notepad.exe"], "calculator":["calc.exe"], "calc":["calc.exe"], "explorer":["explorer.exe"], "file explorer":["explorer.exe"], "settings":["explorer.exe","ms-settings:"], "task manager":["taskmgr.exe"], "taskmgr":["taskmgr.exe"], "paint":["mspaint.exe"], "mspaint":["mspaint.exe"], "cmd":["cmd.exe"], "command prompt":["cmd.exe"], "powershell":["powershell.exe"], "terminal":["wt.exe"], "windows terminal":["wt.exe"], "camera":["explorer.exe","microsoft.windows.camera:"], "control panel":["control.exe"], "chrome":["chrome.exe"], "google chrome":["chrome.exe"], "browser":["msedge.exe"], "web browser":["msedge.exe"], "edge":["msedge.exe"], "microsoft edge":["msedge.exe"], "brave":["brave.exe"], "firefox":["firefox.exe"], "spotify":["explorer.exe","spotify:"], "discord":["explorer.exe","discord:"], "steam":["explorer.exe","steam:"], "whatsapp":["explorer.exe",r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"], "vscode":["code"], "vs code":["code"], "visual studio code":["code"], "code":["code"], "word":["winword.exe"], "excel":["excel.exe"], "powerpoint":["powerpnt.exe"]}

class ActionEngine:
    def __init__(self, settings: Settings, confirm: Callable[[Decision], bool] | None = None) -> None:
        self.settings, self.log = settings, logging.getLogger(self.__class__.__name__)
        pyautogui.FAILSAFE, pyautogui.PAUSE = True, settings.pyautogui_pause_seconds
        self.confirm = confirm or self._confirm_in_terminal
        self._shortcut_apps: dict[str,str] = {}; self._registry_apps: dict[str,str] = {}; self._start_apps: list[dict[str,str]] = []
        self._load_app_indexes()

    def _load_app_indexes(self) -> None:
        try:
            for folder in (os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"), os.path.expandvars(r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs")):
                if os.path.exists(folder):
                    for root, _, files in os.walk(folder):
                        for file in files:
                            if file.lower().endswith((".lnk", ".url")): self._shortcut_apps[file[:-4].lower().strip()] = os.path.join(root,file)
        except Exception as exc: self.log.debug("Start Menu indexing failed: %s", exc)
        if platform.system() != "Windows": return
        try:
            import winreg
            for root_key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(root_key,r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths") as key:
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            subname=winreg.EnumKey(key,i); name=subname.lower().replace(".exe","").strip()
                            try:
                                with winreg.OpenKey(key,subname) as subkey:
                                    path=winreg.QueryValue(subkey,"")
                                    if path: self._registry_apps[name]=path
                            except Exception as exc: self.log.debug("Registry App Path %s failed: %s",name,exc)
                except Exception as exc: self.log.debug("Registry App Paths scan failed: %s",exc)
        except Exception as exc: self.log.debug("Registry indexing failed: %s",exc)
        threading.Thread(target=self._load_uwp_start_apps,daemon=True).start()

    def _load_uwp_start_apps(self) -> None:
        try:
            proc=subprocess.run(["powershell.exe","-NoProfile","-Command","Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"],capture_output=True,text=True,timeout=15)
            data=json.loads(proc.stdout or "[]"); data=[data] if isinstance(data,dict) else data
            self._start_apps=[v for v in data if isinstance(v,dict) and v.get("Name") and v.get("AppID")]
        except Exception as exc: self.log.debug("UWP index failed: %s",exc)

    @staticmethod
    def _confirm_in_terminal(d: Decision) -> bool: return input(f"Allow desktop action {d.action!r}? [y/N]: ").strip().lower() in {"y","yes"}

    def _validate_before_confirmation(self,d: Decision) -> None:
        if d.action not in ALLOWED_ACTIONS: raise ValueError(f"Unhandled action {d.action}")
        if d.action == "press" and (d.key or "").lower() not in SAFE_KEYS: raise ValueError(f"Rejected unsafe key: {d.key or ''}")
        if d.action == "hotkey" and tuple(k.lower() for k in d.keys) not in SAFE_HOTKEYS: raise ValueError(f"Rejected unsafe hotkey: {d.keys}")
        if d.action in {"move","click","double_click"} and (d.x is None or d.y is None): raise ValueError("Coordinates are required")
        if d.action in {"open_url","open_url_in_chrome"}: self._validated_http_url(d.text or "")

    def execute(self,d: Decision) -> bool:
        if d.action == "none": return True
        if self.settings.action_mode == "disabled": self.log.info("Action mode disabled; skipped %s",d.action); return False
        try:
            self._validate_before_confirmation(d)
            if self.settings.action_mode == "confirm" and not self.confirm(d): self.log.info("User declined %s",d.action); return False
            self._execute_validated(d); return True
        except pyautogui.FailSafeException: self.log.warning("PyAutoGUI fail-safe triggered"); return False
        except Exception as exc: self.log.exception("Desktop action '%s' failed: %s",d.action,exc); return False

    def _coordinates(self,d: Decision) -> tuple[int,int]:
        if d.x is None or d.y is None: raise ValueError("Coordinates are required")
        width,height=pyautogui.size()
        if not (0 <= d.x < width and 0 <= d.y < height): raise ValueError(f"Coordinates ({d.x}, {d.y}) outside {width}x{height} screen")
        return d.x,d.y

    def _execute_validated(self,d: Decision) -> None:
        a=d.action
        if a=="move": pyautogui.moveTo(*self._coordinates(d),duration=.25)
        elif a=="click": pyautogui.click(*self._coordinates(d),clicks=max(1,min(d.clicks,2)))
        elif a=="double_click": pyautogui.doubleClick(*self._coordinates(d),interval=.15)
        elif a=="type": self._type_with_restored_clipboard((d.text or "")[:5000])
        elif a=="press": pyautogui.press((d.key or "").lower())
        elif a=="hotkey": pyautogui.hotkey(*(k.lower() for k in d.keys))
        elif a=="scroll": pyautogui.scroll(max(-20,min(d.scrolls,20)))
        elif a in {"open_app","open_named_app"}: self._open_any_app(d.app or "")
        elif a in {"open_url","open_url_in_chrome"}: self._open_url(d.text or "",a.endswith("in_chrome"))
        elif a in {"play_youtube","play_youtube_in_chrome"}: self._play_youtube((d.text or "")[:200],a.endswith("in_chrome"))
        elif a=="search_web": self._open_url("https://www.google.com/search?q="+urllib.parse.quote_plus((d.text or "")[:200]))
        elif a=="volume_up": [pyautogui.press("volumeup") for _ in range(3)]
        elif a=="volume_down": [pyautogui.press("volumedown") for _ in range(3)]
        elif a=="mute": pyautogui.press("volumemute")
        elif a=="media_play_pause": pyautogui.press("playpause")
        elif a=="media_next": pyautogui.press("nexttrack")
        elif a=="media_prev": pyautogui.press("prevtrack")
        elif a=="college_wifi_login": self._college_wifi_login()
        elif a=="open_whatsapp": self._open_whatsapp_with_password()
        elif a=="remember_fact": self.log.info("remember_fact is handled by the conversation layer")

    def _type_with_restored_clipboard(self,text: str) -> None:
        try: import pyperclip
        except ImportError: self.log.debug("pyperclip unavailable; typing directly"); pyautogui.write(text,interval=.01); return
        try: old=pyperclip.paste()
        except Exception as exc: self.log.warning("Could not read clipboard; typing directly: %s",exc); pyautogui.write(text,interval=.01); return
        try: pyperclip.copy(text); time.sleep(.05); pyautogui.hotkey("ctrl","v")
        except Exception as exc: self.log.warning("Clipboard paste failed; typing directly: %s",exc); pyautogui.write(text,interval=.01)
        finally:
            try: pyperclip.copy(old)
            except Exception as exc: self.log.warning("Could not restore clipboard: %s",exc)

    def _secret(self,name: str) -> str | None:
        value=os.getenv(name)
        if not value: self.log.error("Required credential %s is missing; refusing feature",name); return None
        return value

    def _foreground_window_title(self) -> str | None:
        if platform.system() != "Windows": return None
        try:
            hwnd=ctypes.windll.user32.GetForegroundWindow(); length=ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if not hwnd or length <= 0: return None
            buf=ctypes.create_unicode_buffer(length+1); ctypes.windll.user32.GetWindowTextW(hwnd,buf,length+1); return buf.value or None
        except Exception as exc: self.log.debug("Could not read foreground title: %s",exc); return None

    def _foreground_matches(self,expected: tuple[str,...]) -> bool:
        title=self._foreground_window_title()
        if not title or not any(v.casefold() in title.casefold() for v in expected): self.log.warning("Credential entry aborted: expected %s foreground", "/".join(expected)); return False
        return True

    def _college_wifi_login(self) -> None:
        username,password=self._secret("COLLEGE_WIFI_USERNAME"),self._secret("COLLEGE_WIFI_PASSWORD")
        if not username or not password: return
        portal=os.getenv("COLLEGE_WIFI_PORTAL","https://192.168.10.1:8090/httpclient.html")
        try:
            import ssl
            import urllib.request
            context=ssl.create_default_context()
            if os.getenv("COLLEGE_WIFI_INSECURE_TLS") == "1": self.log.warning("COLLEGE_WIFI_INSECURE_TLS=1 disables TLS certificate verification"); context.check_hostname=False; context.verify_mode=ssl.CERT_NONE
            data=urllib.parse.urlencode({"mode":"191","username":username,"password":password,"a":str(int(time.time()*1000)),"producttype":"0"}).encode()
            req=urllib.request.Request("https://192.168.10.1:8090/login.xml",data=data,headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req,context=context,timeout=4) as r:
                if any(x in r.read().decode("utf-8",errors="ignore").lower() for x in ("status","success","live")): self.log.info("WiFi portal login succeeded"); return
        except Exception as exc: self.log.debug("Direct WiFi portal login skipped: %s",exc)
        self._open_url(portal,True)
        def fill() -> None:
            time.sleep(2.5)
            if not self._foreground_matches(("Chrome","Edge","Firefox","Brave")): return
            try:
                pyautogui.write(username,interval=.03); pyautogui.press("tab")
                if not self._foreground_matches(("Chrome","Edge","Firefox","Brave")): return
                pyautogui.write(password,interval=.03); pyautogui.press("enter")
            except Exception as exc: self.log.debug("WiFi portal autofill failed: %s",exc)
        threading.Thread(target=fill,daemon=True).start()

    def _open_whatsapp_with_password(self) -> None:
        password=self._secret("WHATSAPP_PASSWORD")
        if not password: return
        try: subprocess.Popen(COMMON_APP_COMMANDS["whatsapp"],shell=False)
        except Exception as exc: self.log.warning("WhatsApp launch failed: %s",exc); return
        def fill() -> None:
            time.sleep(2.5)
            if not self._foreground_matches(("WhatsApp",)): return
            try:
                import pyperclip; pyperclip.copy(password); pyautogui.hotkey("ctrl","v")
            except Exception as exc:
                self.log.warning("WhatsApp password clipboard entry failed: %s",exc)
                if not self._foreground_matches(("WhatsApp",)): return
                try: pyautogui.write(password,interval=.02)
                except Exception as write_exc: self.log.warning("WhatsApp password entry failed: %s",write_exc); return
            if self._foreground_matches(("WhatsApp",)): pyautogui.press("enter")
        threading.Thread(target=fill,daemon=True).start()

    @staticmethod
    def _validated_http_url(url: str) -> str:
        p=urllib.parse.urlparse(url)
        if p.scheme not in {"http","https"} or not p.netloc: raise ValueError("Only absolute http and https URLs are allowed")
        return url
    def _open_url(self,url: str,in_chrome: bool=False) -> None:
        url=self._validated_http_url(url)
        if in_chrome:
            try: subprocess.Popen(["chrome.exe",url],shell=False); return
            except Exception as exc: self.log.debug("Chrome launch failed; using default browser: %s",exc)
        webbrowser.open_new_tab(url)
    def _play_youtube(self,query: str,in_chrome: bool=False) -> None:
        query=query.strip()[:200]
        if not query: self._open_url("https://www.youtube.com",in_chrome); return
        video_id: Optional[str]=None
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({"quiet":True,"no_warnings":True,"skip_download":True,"extract_flat":True,"socket_timeout":2}) as client: result=client.extract_info(f"ytsearch1:{query}",download=False)
            first=next((v for v in (result.get("entries") or []) if v and v.get("id")),None); video_id=first["id"] if first else None
        except Exception as exc: self.log.debug("yt-dlp resolution skipped: %s",exc)
        self._open_url(f"https://www.youtube.com/watch?v={video_id}&autoplay=1" if video_id else "https://www.youtube.com/results?search_query="+urllib.parse.quote_plus(query),in_chrome)
    def _open_any_app(self,requested_name: str) -> None:
        target=requested_name.strip().casefold()
        if not target: raise ValueError("Application name was empty")
        if target in COMMON_APP_COMMANDS:
            cmd=COMMON_APP_COMMANDS[target]; cmd=["powershell.exe"] if cmd==["wt.exe"] and not shutil.which("wt.exe") else cmd; subprocess.Popen(cmd,shell=False); return
        if target in self._shortcut_apps: os.startfile(self._shortcut_apps[target]); return
        for name,path in self._shortcut_apps.items():
            if target in name or name in target: os.startfile(path); return
        if target in self._registry_apps: subprocess.Popen([self._registry_apps[target]],shell=False); return
        for name,path in self._registry_apps.items():
            if target in name or name in target: subprocess.Popen([path],shell=False); return
        for app in self._start_apps:
            name=app.get("Name","").casefold()
            if target==name or target in name or name in target:
                if appid:=app.get("AppID"): subprocess.Popen(["explorer.exe",f"shell:AppsFolder\\{appid}"],shell=False); return
        matches=get_close_matches(target,list(self._shortcut_apps)+list(self._registry_apps),n=1,cutoff=.55)
        if matches:
            name=matches[0]
            if name in self._shortcut_apps: os.startfile(self._shortcut_apps[name])
            else: subprocess.Popen([self._registry_apps[name]],shell=False)
            return
        raise ValueError(f"Unknown application: {requested_name}")
