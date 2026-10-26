#!/usr/bin/env python3
"""adbtui - a terminal menu (TUI) for ADB and fastboot.

Standard library only. Every action shows the exact command it runs,
so this is still a CLI - just with a convenient menu on top.

Controls: Up/Down / j k - navigate, Enter - run, 1-9 - jump to item,
          r - refresh device list, q / Esc - back.
"""
import curses
import glob
import os
import re
import readline
import shlex
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager


def _complete_path(text, state):
    matches = glob.glob(os.path.expanduser(text) + "*")
    matches = [m + "/" if os.path.isdir(m) else m for m in matches]
    return matches[state] if state < len(matches) else None


readline.set_completer_delims(" \t\n")
readline.set_completer(_complete_path)
readline.parse_and_bind("tab: complete")


class App:
    def __init__(self, scr):
        self.scr = scr
        self.serial = None
        self.adb_devs = []
        self.fb_devs = []
        curses.curs_set(0)
        self.has_color = False
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            self.has_color = True
        except curses.error:
            pass

    def put(self, y, x, text, attr=0):
        h, w = self.scr.getmaxyx()
        if 0 <= y < h and x < w:
            limit = w - x - (1 if y == h - 1 else 0)
            try:
                self.scr.addnstr(y, x, text, limit, attr)
            except curses.error:
                pass

    def color(self, n):
        return curses.color_pair(n) if self.has_color else 0

    @staticmethod
    def _parse(out):
        devs = []
        for line in out.splitlines():
            if not line.strip() or line.startswith(("*", "List of")):
                continue
            parts = line.split()
            if len(parts) >= 2:
                devs.append((parts[0], parts[1]))
        return devs

    def refresh_status(self):
        self.adb_devs, self.fb_devs = [], []
        try:
            out = subprocess.run(["adb", "devices"], capture_output=True,
                                 text=True, timeout=8).stdout
            self.adb_devs = self._parse(out)
        except Exception:
            pass
        try:
            out = subprocess.run(["fastboot", "devices"], capture_output=True,
                                 text=True, timeout=8).stdout
            self.fb_devs = self._parse(out)
        except Exception:
            pass

    def serial_for(self, tool):
        devs = self.adb_devs if tool == "adb" else self.fb_devs
        return self.serial if self.serial in [d[0] for d in devs] else None

    def cmd(self, tool, *args):
        c = [tool]
        s = self.serial_for(tool)
        if s:
            c += ["-s", s]
        return c + [str(a) for a in args]

    @staticmethod
    def capture(cmd, timeout=60):
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True,
                               timeout=timeout)
            return p.returncode, p.stdout
        except subprocess.TimeoutExpired:
            return -1, f"Timed out ({timeout}s)."
        except FileNotFoundError as e:
            return -1, f"Program not found: {e.filename}"

    def show(self, cmd, title="Output", timeout=60):
        rc, out = self.capture(cmd, timeout)
        self.pager(title, f"$ {shlex.join(cmd)}\n\n{out.rstrip()}\n\n[exit code: {rc}]")

    @contextmanager
    def shell(self):
        curses.def_prog_mode()
        curses.endwin()
        try:
            yield
        finally:
            curses.reset_prog_mode()
            self.scr.clear()
            self.scr.refresh()
            curses.curs_set(0)

    def interactive(self, cmd, pause=True):
        with self.shell():
            print(f"\033[1;36m$ {shlex.join(cmd)}\033[0m\n")
            try:
                subprocess.run(cmd)
            except KeyboardInterrupt:
                print("\n(interrupted)")
            except FileNotFoundError as e:
                print(f"Program not found: {e.filename}")
            if pause:
                try:
                    input("\n[Enter] to return to the menu ")
                except (EOFError, KeyboardInterrupt):
                    pass

    def form(self, fields, danger=None, word="yes", required=True):
        """Asks for values in the plain terminal (with Tab path completion).
        Returns a list of answers, or None if cancelled."""
        with self.shell():
            print("\033[2J\033[H", end="")
            vals = []
            try:
                for label, default in fields:
                    suffix = f" [{default}]" if default else ""
                    v = input(f"{label}{suffix}: ").strip()
                    vals.append(v or default)
                if required and not all(vals):
                    return None
                if danger:
                    print(f"\n\033[1;31m{danger(vals)}\033[0m")
                    if input(f"Type '{word}' to continue: ").strip() != word:
                        print("Cancelled.")
                        time.sleep(0.8)
                        return None
            except (EOFError, KeyboardInterrupt):
                return None
        return vals

    def need_file(self, path):
        p = os.path.expanduser(path)
        if not os.path.isfile(p):
            self.pager("Error", f"No such file:\n{p}")
            return None
        return p

    def pager(self, title, text):
        lines = [l.replace("\r", "").expandtabs(4) for l in text.splitlines()] or ["(no output)"]
        top = 0
        while True:
            h, w = self.scr.getmaxyx()
            body = max(1, h - 2)
            top = max(0, min(top, max(0, len(lines) - body)))
            self.scr.erase()
            self.put(0, 0, f" {title} ".ljust(w), curses.A_REVERSE | curses.A_BOLD)
            for i, line in enumerate(lines[top:top + body]):
                self.put(1 + i, 0, line)
            self.put(h - 1, 0, " Up/Down PgUp/PgDn Space g/G scroll · q/Esc close ".ljust(w),
                     curses.A_REVERSE)
            k = self.scr.getch()
            if k in (ord("q"), 27):
                return
            elif k in (curses.KEY_DOWN, ord("j")):
                top += 1
            elif k in (curses.KEY_UP, ord("k")):
                top -= 1
            elif k in (curses.KEY_NPAGE, ord(" ")):
                top += body - 1
            elif k == curses.KEY_PPAGE:
                top -= body - 1
            elif k in (ord("g"), curses.KEY_HOME):
                top = 0
            elif k in (ord("G"), curses.KEY_END):
                top = len(lines)

    def draw_menu(self, title, items, sel, back):
        h, w = self.scr.getmaxyx()
        self.scr.erase()
        self.put(0, 0, f" {title} ".ljust(w), curses.A_REVERSE | curses.A_BOLD)

        def fmt(devs):
            return ", ".join(f"{a} [{b}]" for a, b in devs) or "none"

        self.put(2, 0, "ADB:       " + fmt(self.adb_devs), self.color(1))
        self.put(3, 0, "Fastboot:  " + fmt(self.fb_devs), self.color(1))
        self.put(4, 0, "Selected:  " + (self.serial or "auto (default device)"))
        serials = {d[0] for d in self.adb_devs + self.fb_devs}
        if len(serials) > 1 and not self.serial:
            self.put(5, 0, "Multiple devices - pick one in 'Select device'.",
                     self.color(2) | curses.A_BOLD)

        first, body = 7, max(1, h - 9)
        start = max(0, min(sel - body // 2, len(items) - body))
        for row, i in enumerate(range(start, min(len(items), start + body))):
            prefix = f" {i + 1}. " if i < 9 else "    "
            attr = curses.A_REVERSE if i == sel else 0
            self.put(first + row, 0, (prefix + items[i][0]).ljust(min(w - 1, 60)), attr)
        self.put(h - 1, 0, f" Up/Down/jk select · Enter run · r refresh · q {back} ".ljust(w),
                 curses.A_REVERSE)
        self.scr.refresh()

    def menu(self, title, items, back="back"):
        sel, dirty = 0, True
        while True:
            if dirty:
                self.refresh_status()
                dirty = False
            self.draw_menu(title, items, sel, back)
            k = self.scr.getch()
            if k in (curses.KEY_UP, ord("k")):
                sel = (sel - 1) % len(items)
            elif k in (curses.KEY_DOWN, ord("j")):
                sel = (sel + 1) % len(items)
            elif k in (10, 13, curses.KEY_ENTER):
                if items[sel][1]() == "back":
                    return
                dirty = True
            elif k in (ord("q"), 27):
                return
            elif k == ord("r"):
                dirty = True
            elif ord("1") <= k <= ord("9") and k - ord("1") < len(items):
                sel = k - ord("1")

    def set_serial(self, s):
        self.serial = s
        return "back"

    def select_device(self):
        self.refresh_status()
        seen, items = set(), [("Automatic (no -s)", lambda: self.set_serial(None))]
        for tool, devs in (("adb", self.adb_devs), ("fastboot", self.fb_devs)):
            for s, st in devs:
                if s in seen:
                    continue
                seen.add(s)
                items.append((f"{s}  [{tool}: {st}]", lambda s=s: self.set_serial(s)))
        self.menu("Select device", items)

    def restart_server(self):
        _, a = self.capture(["adb", "kill-server"])
        rc, b = self.capture(["adb", "start-server"])
        self.pager("ADB server", f"$ adb kill-server\n{a}\n$ adb start-server\n{b}\n[code: {rc}]")

    def custom(self, tool):
        v = self.form([(f"Command (without '{tool}')", "")])
        if v:
            try:
                args = shlex.split(v[0])
            except ValueError as e:
                self.pager("Error", str(e))
                return
            self.interactive(self.cmd(tool, *args))

    def adb_items(self):
        reboot = lambda *a: (lambda: self.show(self.cmd("adb", "reboot", *a), "Reboot"))
        return [
            ("List devices (adb devices -l)",
             lambda: self.show(["adb", "devices", "-l"], "adb devices -l")),
            ("Device info", self.adb_info),
            ("Shell (adb shell)",
             lambda: self.interactive(self.cmd("adb", "shell"), pause=False)),
            ("Logcat (Ctrl+C to stop)",
             lambda: self.interactive(self.cmd("adb", "logcat", "-v", "color"), pause=False)),
            ("Install APK", self.adb_install),
            ("Uninstall app", self.adb_uninstall),
            ("List packages", self.adb_packages),
            ("Push file to device", self.adb_push),
            ("Pull file from device", self.adb_pull),
            ("Take screenshot", self.adb_screenshot),
            ("Sideload ZIP", self.adb_sideload),
            ("Wireless: pair (adb pair)",
             lambda: self.pair()),
            ("Wireless: connect (adb connect)", self.adb_connect),
            ("Reboot: system", reboot()),
            ("Reboot: bootloader", reboot("bootloader")),
            ("Reboot: recovery", reboot("recovery")),
            ("Reboot: fastbootd", reboot("fastboot")),
            ("Custom adb command", lambda: self.custom("adb")),
        ]

    def adb_info(self):
        rc, out = self.capture(self.cmd("adb", "shell", "getprop"))
        props = dict(re.findall(r"\[(.*?)\]: \[(.*?)\]", out))
        if not props:
            self.pager("Device info", out or "No response.")
            return
        rows = [("Model", "ro.product.model"), ("Manufacturer", "ro.product.manufacturer"),
                ("Codename", "ro.product.device"), ("Android", "ro.build.version.release"),
                ("SDK", "ro.build.version.sdk"), ("Build", "ro.build.display.id"),
                ("Security patch", "ro.build.version.security_patch"),
                ("Bootloader", "ro.bootloader"), ("Slot", "ro.boot.slot_suffix"),
                ("Bootloader locked", "ro.boot.flash.locked"),
                ("Verified boot", "ro.boot.verifiedbootstate")]
        lines = [f"{label:<18}{props.get(key) or '-'}" for label, key in rows]
        _, bat = self.capture(self.cmd("adb", "shell", "dumpsys", "battery"))
        for line in bat.splitlines():
            s = line.strip()
            if s.split(":")[0] in ("level", "status", "temperature", "AC powered", "USB powered"):
                lines.append(f"[battery] {s}")
        self.pager("Device info", "\n".join(lines))

    def adb_install(self):
        v = self.form([("Path to .apk", "")])
        if v and (p := self.need_file(v[0])):
            self.interactive(self.cmd("adb", "install", "-r", p))

    def adb_uninstall(self):
        v = self.form([("Package name (e.g. com.example.app)", ""),
                       ("Keep data? [y/N]", "n")],
                      danger=lambda v: f"Will uninstall: {v[0]}", word="yes")
        if v:
            args = ["uninstall"] + (["-k"] if v[1].lower().startswith("y") else []) + [v[0]]
            self.interactive(self.cmd("adb", *args))

    def adb_packages(self):
        v = self.form([("Filter (empty = all)", ""),
                       ("User apps only? [y/N]", "n")], required=False)
        if v is None:
            return
        args = ["shell", "pm", "list", "packages"]
        if v[1].lower().startswith("y"):
            args.append("-3")
        if v[0]:
            args.append(v[0])
        self.show(self.cmd("adb", *args), "Packages")

    def adb_push(self):
        v = self.form([("Local file", ""), ("Target on device", "/sdcard/Download/")])
        if v and (p := self.need_file(v[0])):
            self.interactive(self.cmd("adb", "push", p, v[1]))

    def adb_pull(self):
        v = self.form([("Path on device", ""), ("Destination directory", ".")])
        if v:
            self.interactive(self.cmd("adb", "pull", v[0], os.path.expanduser(v[1])))

    def adb_screenshot(self):
        name = f"screenshot-{time.strftime('%Y%m%d-%H%M%S')}.png"
        cmd = self.cmd("adb", "exec-out", "screencap", "-p")
        try:
            with open(name, "wb") as f:
                p = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=30)
            if p.returncode != 0:
                os.remove(name)
                self.pager("Screenshot", f"Error:\n{p.stderr.decode(errors='replace')}")
            else:
                self.pager("Screenshot", f"$ {shlex.join(cmd)} > {name}\n\nSaved: {os.path.abspath(name)}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.pager("Screenshot", f"Error: {e}")

    def adb_sideload(self):
        v = self.form([("Path to .zip", "")])
        if v and (p := self.need_file(v[0])):
            self.interactive(self.cmd("adb", "sideload", p))

    def pair(self):
        v = self.form([("host:port from the pairing screen", "")])
        if v:
            self.interactive(["adb", "pair", v[0]])

    def adb_connect(self):
        v = self.form([("host:port (e.g. 192.168.1.20:5555)", "")])
        if v:
            self.show(["adb", "connect", v[0]], "adb connect")

    def fb_items(self):
        fb = lambda *a: (lambda: self.show(self.cmd("fastboot", *a), "fastboot " + " ".join(a)))
        return [
            ("List devices (fastboot devices)",
             lambda: self.show(["fastboot", "devices", "-l"], "fastboot devices -l")),
            ("All variables (getvar all)", fb("getvar", "all")),
            ("Flash image to partition", self.fb_flash),
            ("Boot image without flashing", self.fb_boot),
            ("Erase partition", self.fb_erase),
            ("Set active slot (a/b)", self.fb_slot),
            ("Unlock bootloader (flashing unlock)",
             lambda: self.fb_danger("flashing", "unlock")),
            ("Lock bootloader (flashing lock)",
             lambda: self.fb_danger("flashing", "lock")),
            ("Wipe user data (-w)", lambda: self.fb_danger("-w")),
            ("Reboot: system", fb("reboot")),
            ("Reboot: bootloader", fb("reboot", "bootloader")),
            ("Reboot: fastbootd", fb("reboot", "fastboot")),
            ("Reboot: recovery", fb("reboot", "recovery")),
            ("Custom fastboot command", lambda: self.custom("fastboot")),
        ]

    def fb_flash(self):
        v = self.form([("Partition (e.g. boot, recovery, vendor_boot)", ""),
                       ("Image file (.img)", "")],
                      danger=lambda v: f"About to run: fastboot flash {v[0]} {v[1]}\n"
                                       "A wrong image can make the device fail to boot.")
        if v and (p := self.need_file(v[1])):
            self.interactive(self.cmd("fastboot", "flash", v[0], p))

    def fb_boot(self):
        v = self.form([("Image file (.img)", "")])
        if v and (p := self.need_file(v[0])):
            self.interactive(self.cmd("fastboot", "boot", p))

    def fb_erase(self):
        v = self.form([("Partition to erase", "")],
                      danger=lambda v: f"About to run: fastboot erase {v[0]}\nThis cannot be undone.")
        if v:
            self.interactive(self.cmd("fastboot", "erase", v[0]))

    def fb_slot(self):
        v = self.form([("Slot (a or b)", "")])
        if v and v[0] in ("a", "b"):
            self.show(self.cmd("fastboot", "set_active", v[0]), "set_active")

    def fb_danger(self, *args):
        c = self.cmd("fastboot", *args)
        v = self.form([], danger=lambda _: f"About to run: {shlex.join(c)}\n"
                                           "This usually wipes ALL data on the device.",
                      word="WIPE", required=False)
        if v is not None:
            self.interactive(c)

    def main_items(self):
        return [
            ("ADB", lambda: self.menu("ADB / Fastboot  ›  ADB", self.adb_items())),
            ("Fastboot", lambda: self.menu("ADB / Fastboot  ›  Fastboot", self.fb_items())),
            ("Select device", self.select_device),
            ("Restart ADB server", self.restart_server),
        ]


def main(scr):
    app = App(scr)
    app.menu("ADB / Fastboot", app.main_items(), back="quit")


if __name__ == "__main__":
    if any(a in ("-h", "-help", "--help") for a in sys.argv[1:]):
        print(__doc__.strip())
        sys.exit(0)
    missing = [t for t in ("adb", "fastboot") if not shutil.which(t)]
    if missing:
        sys.exit(f"Missing from PATH: {', '.join(missing)}\n"
                 "Install Android SDK Platform Tools or add it to PATH.")
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(main)
