r"""Interface grafica do NMTBot — Design minimalista escuro."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from app.bot.engine import BotEngine
from app.gui.settings import get_settings
from app.utils.logger import logger

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

_ICONS_DIR = Path(__file__).resolve().parents[2] / "assets"
_ICON_ICO  = _ICONS_DIR / "nmt_bot_icon.ico"
_ICON_PNG  = _ICONS_DIR / "nmt_bot_icon.png"

# Paleta
_GREEN   = "#2fa84f"
_GREEN_H = "#279042"
_RED     = "#c0392b"
_RED_H   = "#a93226"
_GOLD    = "#f0b429"
_GRAY    = "#3a3a3a"
_DARK    = "#1e1e1e"
_MID     = "#2b2b2b"
_ACCENT  = "#4a9eff"


class NMTBotApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Bot NMT.gg")
        self.geometry("820x600")
        self.minsize(780, 560)
        self.configure(fg_color=_DARK)
        self._apply_window_icon()

        self._settings = get_settings()
        self._restore_geometry()

        self.bot: Optional[BotEngine] = None
        self._tab_items: dict = {}

        # Layout: header / conteudo / log
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self._build_log_area()

        self._load_settings_to_ui()
        self.log("Bot NMT.gg iniciado.")
        self.log("Clique em Abrir Navegador para comecar.")

        # Checa atualizacoes
        try:
            from updater import check_for_update
            check_for_update(on_update_available=self._show_update_banner, on_error=lambda e: None)
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=_MID, corner_radius=0, height=56)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        hdr.grid_propagate(False)

        # Logo / titulo
        ctk.CTkLabel(
            hdr, text="⬡ NMT BOT",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=_GOLD,
        ).grid(row=0, column=0, padx=20, pady=12, sticky="w")

        # Status pill
        self.connection_label = ctk.CTkLabel(
            hdr, text="● Desconectado",
            font=ctk.CTkFont(size=11), text_color="#ff6b6b",
        )
        self.connection_label.grid(row=0, column=1, padx=10, sticky="e")

        # Versao
        try:
            from version import __version__
            ver = f"v{__version__}"
        except ImportError:
            ver = ""
        ctk.CTkLabel(
            hdr, text=ver,
            font=ctk.CTkFont(size=10), text_color="#666",
        ).grid(row=0, column=2, padx=4, pady=12, sticky="e")

        # Botao engrenagem (configuracoes)
        ctk.CTkButton(
            hdr, text="⚙",
            width=36, height=36,
            fg_color="transparent",
            hover_color=_GRAY,
            font=ctk.CTkFont(size=18),
            command=self._open_settings_modal,
        ).grid(row=0, column=3, padx=(4, 16), pady=10)

        # Banner de atualizacao (oculto)
        self._update_banner = ctk.CTkFrame(self, fg_color="#1a4a6e", corner_radius=0, height=36)
        self._update_banner.grid_columnconfigure(0, weight=1)
        self._update_banner.grid_propagate(False)
        self._update_label = ctk.CTkLabel(
            self._update_banner, text="",
            font=ctk.CTkFont(size=11), text_color="white",
        )
        self._update_label.grid(row=0, column=0, padx=16, pady=8, sticky="w")
        ctk.CTkButton(
            self._update_banner, text="Baixar",
            width=70, height=24,
            fg_color=_ACCENT, hover_color="#2980b9",
            font=ctk.CTkFont(size=11),
            command=self._open_update_url,
        ).grid(row=0, column=1, padx=12, pady=6)
        self._update_url = ""

    # ------------------------------------------------------------------
    # Body: tabs
    # ------------------------------------------------------------------

    def _build_body(self):
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=_MID,
            segmented_button_fg_color=_DARK,
            segmented_button_selected_color=_GRAY,
            segmented_button_selected_hover_color="#4a4a4a",
            segmented_button_unselected_color=_DARK,
            segmented_button_unselected_hover_color=_GRAY,
            text_color="white",
            text_color_disabled="#666",
        )
        self.tabview.grid(row=1, column=0, padx=16, pady=(12, 6), sticky="nsew")

        self.tab_main    = self.tabview.add("Principal")
        self.tab_stats   = self.tabview.add("Estatísticas")
        self.tab_console = self.tabview.add("Console")

        self._build_main_tab()
        self._build_stats_tab()
        self._build_console_tab()

    # ------------------------------------------------------------------
    # Aba Principal
    # ------------------------------------------------------------------

    def _build_main_tab(self):
        tab = self.tab_main
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)

        # --- Secao: Navegador ---
        sec1 = self._section(tab, "NAVEGADOR", row=0)

        # Checkboxes
        chk_frame = ctk.CTkFrame(sec1, fg_color="transparent")
        chk_frame.grid(row=1, column=0, columnspan=2, padx=16, pady=(4, 8), sticky="w")

        self.headless_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            chk_frame, text="Headless (sem janela visivel)",
            variable=self.headless_var,
            font=ctk.CTkFont(size=12),
            checkbox_width=18, checkbox_height=18,
        ).grid(row=0, column=0, padx=(0, 24), pady=2, sticky="w")

        self.dismiss_offers_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            chk_frame, text="Dispensar ofertas automaticamente",
            variable=self.dismiss_offers_var,
            font=ctk.CTkFont(size=12),
            checkbox_width=18, checkbox_height=18,
        ).grid(row=0, column=1, pady=2, sticky="w")

        # Botoes principais
        btn_frame = ctk.CTkFrame(sec1, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        self.start_button = ctk.CTkButton(
            btn_frame,
            text="Abrir Navegador",
            command=self.on_start_clicked,
            fg_color=_GREEN, hover_color=_GREEN_H,
            height=44, font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
        )
        self.start_button.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.stop_button = ctk.CTkButton(
            btn_frame,
            text="Parar Bot",
            command=self.stop_bot,
            state="disabled",
            fg_color=_RED, hover_color=_RED_H,
            height=44, font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
        )
        self.stop_button.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        # Seletor de aba
        tab_frame = ctk.CTkFrame(sec1, fg_color="transparent")
        tab_frame.grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="ew")
        tab_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            tab_frame, text="Aba:",
            font=ctk.CTkFont(size=12), text_color="#aaa",
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")

        self.tab_menu = ctk.CTkOptionMenu(
            tab_frame,
            values=["(nenhuma selecionada)"],
            command=self._on_tab_selected,
            state="disabled",
            fg_color=_GRAY, button_color=_GRAY,
            font=ctk.CTkFont(size=12),
            height=32,
        )
        self.tab_menu.grid(row=0, column=1, sticky="ew")

        self.refresh_tabs_button = ctk.CTkButton(
            tab_frame, text="↺",
            command=self._refresh_tabs,
            state="disabled",
            width=32, height=32,
            fg_color=_GRAY, hover_color="#4a4a4a",
            font=ctk.CTkFont(size=16),
        )
        self.refresh_tabs_button.grid(row=0, column=2, padx=(6, 0))

        # --- Secao: Status ---
        sec2 = self._section(tab, "STATUS", row=4)

        self.quick_status = ctk.CTkLabel(
            sec2, text="Pronto. Clique em Abrir Navegador.",
            font=ctk.CTkFont(size=12), text_color="#aaa",
            anchor="w",
        )
        self.quick_status.grid(row=1, column=0, columnspan=2, padx=16, pady=(4, 4), sticky="ew")

        # Mini stats na tela principal
        mini = ctk.CTkFrame(sec2, fg_color="transparent")
        mini.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="ew")
        for i in range(4):
            mini.grid_columnconfigure(i, weight=1)

        def mini_stat(parent, col, label, attr):
            f = ctk.CTkFrame(parent, fg_color=_DARK, corner_radius=8)
            f.grid(row=0, column=col, padx=4, sticky="ew")
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=10), text_color="#666").grid(
                row=0, column=0, padx=10, pady=(8, 0))
            lbl = ctk.CTkLabel(f, text="—", font=ctk.CTkFont(size=16, weight="bold"))
            lbl.grid(row=1, column=0, padx=10, pady=(0, 8))
            setattr(self, attr, lbl)

        mini_stat(mini, 0, "RODADA", "mini_round_lbl")
        mini_stat(mini, 1, "FIGURAS", "mini_figures_lbl")
        mini_stat(mini, 2, "TIMER", "mini_timer_lbl")
        mini_stat(mini, 3, "ERROS", "mini_errors_lbl")

        # --- Secao: Ganhos NMT ---
        sec3 = self._section(tab, "GANHOS NMT", row=6)

        nmt = ctk.CTkFrame(sec3, fg_color="transparent")
        nmt.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="ew")
        for i in range(3):
            nmt.grid_columnconfigure(i, weight=1)

        def nmt_card(parent, col, label, attr, color="white"):
            f = ctk.CTkFrame(parent, fg_color=_DARK, corner_radius=8)
            f.grid(row=0, column=col, padx=4, sticky="ew")
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=10), text_color="#666").grid(
                row=0, column=0, padx=14, pady=(10, 0))
            lbl = ctk.CTkLabel(f, text="—", font=ctk.CTkFont(size=20, weight="bold"), text_color=color)
            lbl.grid(row=1, column=0, padx=14, pady=(0, 10))
            setattr(self, attr, lbl)

        nmt_card(nmt, 0, "TOTAL NMT", "nmt_total_label", _GOLD)
        nmt_card(nmt, 1, "VITORIAS",  "nmt_wins_label",  _GREEN)
        nmt_card(nmt, 2, "ULTIMO",    "nmt_last_label",  "#aaa")

    # ------------------------------------------------------------------
    # Aba Estatísticas
    # ------------------------------------------------------------------

    def _build_stats_tab(self):
        tab = self.tab_stats
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)

        self.stats_labels = {}

        def stat_card(row, col, label, key, fmt="{}"):
            f = ctk.CTkFrame(tab, fg_color=_DARK, corner_radius=8)
            f.grid(row=row, column=col, padx=8, pady=6, sticky="nsew")
            f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=10), text_color="#666").grid(
                row=0, column=0, padx=12, pady=(10, 0))
            lbl = ctk.CTkLabel(f, text="0", font=ctk.CTkFont(size=26, weight="bold"))
            lbl.grid(row=1, column=0, padx=12, pady=(0, 10))
            self.stats_labels[key] = (lbl, fmt)

        stat_card(0, 0, "FIGURAS COLOCADAS", "figures_placed")
        stat_card(0, 1, "RODADAS VISTAS",    "rounds_seen")
        stat_card(1, 0, "RODADAS PROCESSADAS","rounds_processed")
        stat_card(1, 1, "ERROS",             "errors")
        stat_card(2, 0, "UPTIME",            "uptime", self._fmt_uptime)
        stat_card(2, 1, "RODADA ATUAL",      "current_round")

        # Timer
        self.round_timer_label = ctk.CTkLabel(
            tab, text="Rodada: — | Timer: —",
            font=ctk.CTkFont(size=11), text_color="#666",
        )
        self.round_timer_label.grid(row=3, column=0, columnspan=2, padx=8, pady=(4, 0), sticky="w")

        # Reset
        ctk.CTkButton(
            tab, text="Resetar Estatísticas",
            command=self._reset_stats,
            fg_color=_RED, hover_color=_RED_H,
            height=36, corner_radius=8,
        ).grid(row=4, column=0, columnspan=2, padx=8, pady=12, sticky="ew")

    # ------------------------------------------------------------------
    # Aba Console
    # ------------------------------------------------------------------

    def _build_console_tab(self):
        tab = self.tab_console
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        self.console_box = ctk.CTkTextbox(
            tab,
            state="disabled",
            fg_color=_DARK,
            text_color="#00ff88",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8,
        )
        self.console_box.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Botao limpar
        ctk.CTkButton(
            tab, text="Limpar Console",
            command=self._clear_console,
            fg_color=_GRAY, hover_color="#4a4a4a",
            height=30, corner_radius=6,
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, padx=0, pady=(6, 0), sticky="e")

    # ------------------------------------------------------------------
    # Area de log inferior (mini status bar)
    # ------------------------------------------------------------------

    def _build_log_area(self):
        bar = ctk.CTkFrame(self, fg_color=_MID, corner_radius=0, height=28)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_propagate(False)

        self.status_bar_label = ctk.CTkLabel(
            bar, text="Pronto.",
            font=ctk.CTkFont(size=11), text_color="#aaa",
            anchor="w",
        )
        self.status_bar_label.grid(row=0, column=0, padx=16, pady=4, sticky="ew")

    # ------------------------------------------------------------------
    # Modal de Configuracoes (engrenagem)
    # ------------------------------------------------------------------

    def _open_settings_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Configurações")
        modal.geometry("440x560")
        modal.resizable(False, False)
        modal.grab_set()
        modal.configure(fg_color=_DARK)

        ctk.CTkLabel(
            modal, text="Configurações",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(padx=24, pady=(20, 4), anchor="w")

        scroll = ctk.CTkScrollableFrame(modal, fg_color=_MID, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=16, pady=8)
        scroll.grid_columnconfigure(1, weight=1)

        self.config_vars = {}
        row = 0

        def add_entry(label, key, tooltip="", type_="float"):
            nonlocal row
            ctk.CTkLabel(
                scroll, text=label, font=ctk.CTkFont(size=12),
            ).grid(row=row, column=0, padx=12, pady=(8, 2), sticky="w")
            var = ctk.StringVar()
            ctk.CTkEntry(scroll, textvariable=var, width=120, height=30).grid(
                row=row, column=1, padx=12, pady=(8, 2), sticky="e")
            if tooltip:
                ctk.CTkLabel(
                    scroll, text=tooltip, font=ctk.CTkFont(size=10), text_color="#666",
                ).grid(row=row+1, column=0, columnspan=2, padx=12, pady=(0, 4), sticky="w")
            self.config_vars[key] = (var, type_)
            row += 2 if tooltip else 1

        def section(label):
            nonlocal row
            ctk.CTkLabel(
                scroll, text=label,
                font=ctk.CTkFont(size=11, weight="bold"), text_color=_ACCENT,
            ).grid(row=row, column=0, columnspan=2, padx=12, pady=(16, 4), sticky="w")
            row += 1

        section("ENGINE")
        add_entry("Loop interval (s)",    "loop_interval",          "Tempo entre iteracoes", "float")
        add_entry("Poll interval (s)",    "poll_interval",          "Intervalo de leitura",  "float")
        add_entry("Max figuras/rodada",   "max_figures_per_round",  "Maximo por rodada",     "int")

        section("HUMANIZER (delays)")
        add_entry("Base delay min (ms)",  "humanize_base_delay_min",  "Minimo", "int")
        add_entry("Base delay max (ms)",  "humanize_base_delay_max",  "Maximo", "int")
        add_entry("Click delay min (ms)", "humanize_click_delay_min", "Minimo", "int")
        add_entry("Click delay max (ms)", "humanize_click_delay_max", "Maximo", "int")
        add_entry("Round delay min (ms)", "humanize_round_delay_min", "Minimo", "int")
        add_entry("Round delay max (ms)", "humanize_round_delay_max", "Maximo", "int")

        section("CLOUDFLARE")
        add_entry("Auto timeout (s)",   "cloudflare_auto_timeout",   "", "float")
        add_entry("Manual timeout (s)", "cloudflare_manual_timeout", "", "float")

        # Carrega valores atuais
        s = self._settings
        for key, (var, type_) in self.config_vars.items():
            if type_ == "int":
                var.set(str(s.get_int(key, s._DEFAULTS.get(key, 0))))
            else:
                var.set(str(s.get_float(key, s._DEFAULTS.get(key, 0.0))))

        # Botoes
        btn_row = ctk.CTkFrame(modal, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 16))
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_row, text="Cancelar",
            command=modal.destroy,
            fg_color=_GRAY, hover_color="#4a4a4a",
            height=36, corner_radius=8,
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            btn_row, text="Salvar",
            command=lambda: [self._save_config(), modal.destroy()],
            fg_color=_GREEN, hover_color=_GREEN_H,
            height=36, corner_radius=8,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    # ------------------------------------------------------------------
    # Helper: secao com titulo
    # ------------------------------------------------------------------

    def _section(self, parent, title, row):
        # Linha separadora com titulo
        lbl = ctk.CTkLabel(
            parent, text=title,
            font=ctk.CTkFont(size=10, weight="bold"), text_color="#555",
            anchor="w",
        )
        lbl.grid(row=row, column=0, columnspan=2, padx=16, pady=(16, 4), sticky="ew")

        frame = ctk.CTkFrame(parent, fg_color=_MID, corner_radius=10)
        frame.grid(row=row+1, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        return frame

    # ------------------------------------------------------------------
    # Settings / UI sync
    # ------------------------------------------------------------------

    def _load_settings_to_ui(self):
        s = self._settings
        self.headless_var.set(s.get_bool("headless", False))

    def _save_config(self):
        self._settings.set("headless", self.headless_var.get())
        for key, (var, type_) in self.config_vars.items():
            raw = var.get()
            if not raw:
                continue
            try:
                if type_ == "int":
                    self._settings.set(key, int(raw))
                else:
                    self._settings.set(key, float(raw))
            except ValueError:
                pass
        self._settings.save()
        self.log("Configuracoes salvas.")

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def _fmt_uptime(self, seconds):
        if seconds < 60:
            return f"{int(seconds)}s"
        m, s = divmod(int(seconds), 60)
        if m < 60:
            return f"{m}m {s}s"
        h, m = divmod(m, 60)
        return f"{h}h {m}m"

    def _update_stats_ui(self, stats: dict):
        # Aba Estatisticas
        for key, (lbl, fmt) in self.stats_labels.items():
            val = stats.get(key, 0)
            try:
                txt = fmt(val) if callable(fmt) else fmt.format(val)
            except Exception:
                txt = str(val)
            lbl.configure(text=txt)

        cr = stats.get("current_round", "—")
        ct = stats.get("current_timer", 0)
        self.round_timer_label.configure(text=f"Rodada: {cr} | Timer: {ct}s")

        # Mini stats na tela principal
        self.mini_round_lbl.configure(text=str(cr))
        self.mini_figures_lbl.configure(text=str(stats.get("figures_placed", 0)))
        self.mini_timer_lbl.configure(text=f"{ct}s")
        self.mini_errors_lbl.configure(text=str(stats.get("errors", 0)))

        # Ganhos NMT
        nmt_total = stats.get("nmt_total", 0.0)
        nmt_wins  = stats.get("nmt_wins", 0)
        nmt_last  = stats.get("nmt_last", "—")
        self.nmt_total_label.configure(text=f"{nmt_total:.4f}")
        self.nmt_wins_label.configure(text=str(nmt_wins))
        self.nmt_last_label.configure(text=str(nmt_last))

    def _on_bot_stats(self, stats: dict):
        self.after(0, lambda: self._update_stats_ui(stats))

    def _reset_stats(self):
        if self.bot:
            with self.bot._stats_lock:
                self.bot._stats = {
                    "figures_placed": 0, "rounds_seen": 0,
                    "rounds_processed": 0, "errors": 0,
                    "start_time": self.bot._stats.get("start_time", time.time()),
                    "current_round": "—", "current_timer": 0,
                    "last_action_time": 0.0,
                    "nmt_total": 0.0, "nmt_wins": 0, "nmt_last": "—",
                }
            self._update_stats_ui(self.bot.stats)
        self.log("Estatisticas resetadas.")

    # ------------------------------------------------------------------
    # Fluxo principal
    # ------------------------------------------------------------------

    def on_start_clicked(self):
        if self.bot is None:
            self._open_browser_flow()
            return
        if self.bot.is_running:
            self.log("Bot ja esta em execucao.")
            return
        if self.bot.browser_ready:
            self._start_automation_flow()
            return
        self.log("Chrome ainda nao esta pronto.")

    def _open_browser_flow(self):
        s = self._settings
        self.bot = BotEngine(
            headless=self.headless_var.get(),
            loop_interval=s.get_float("loop_interval", 5.0),
            poll_interval=s.get_float("poll_interval", 3.0),
            auto_dismiss_offers=self.dismiss_offers_var.get(),
            on_status=self._emit,
        )
        self.bot.set_on_stats(self._on_bot_stats)
        self.bot.set_on_browser_ready(self._on_browser_ready)
        self.bot.open_browser()

        self.start_button.configure(state="disabled")
        self._set_status("Abrindo Chrome...", "orange")
        self.quick_status.configure(text="Resolva o login no Chrome e selecione a aba.")

    def _on_browser_ready(self):
        self.after(0, self._refresh_tabs)
        self.after(0, lambda: self.tab_menu.configure(state="normal"))
        self.after(0, lambda: self.refresh_tabs_button.configure(state="normal"))
        self.after(0, lambda: self.start_button.configure(state="disabled", text="Iniciar Bot"))
        self.after(0, lambda: self._set_status("Conectado", _GREEN))
        self.after(0, lambda: self.quick_status.configure(
            text="Chrome conectado. Selecione a aba e clique em Iniciar Bot."
        ))

    def _refresh_tabs(self):
        if not self.bot or not self.bot.browser.is_alive():
            return
        tabs = self.bot.list_tabs()
        if not tabs:
            self.tab_menu.configure(values=["(nenhuma aba aberta)"])
            return
        labels = [f"{t['index']} — {t['title'][:40]}" for t in tabs]
        self.tab_menu.configure(values=labels)
        self.tab_menu.set(labels[0])
        self._tab_items = {label: t["index"] for label, t in zip(labels, tabs)}
        self.log(f"{len(tabs)} aba(s) encontrada(s).")

    def _on_tab_selected(self, label: str):
        if not self.bot:
            return
        index = self._tab_items.get(label)
        if index is None:
            return
        if self.bot.select_tab(index):
            self.start_button.configure(state="normal")
            self.quick_status.configure(text=f"Aba {index} selecionada. Clique em Iniciar Bot.")
        else:
            self.log("Nao foi possivel selecionar essa aba.")

    def _start_automation_flow(self):
        self.log("Iniciando automacao...")
        self.bot.start()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._set_status("Automatizando", _GREEN)
        self.quick_status.configure(text="Bot rodando automaticamente.")
        self.log("Automacao iniciada.")

    def stop_bot(self):
        if not self.bot or not self.bot.is_running:
            return
        self.log("Parando bot...")
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def _stop_worker(self):
        try:
            self.bot.stop()
        except Exception as exc:
            self.after(0, lambda: self.log(f"Erro ao parar: {exc}"))
            return
        self.after(0, self._on_bot_stopped)

    def _on_bot_stopped(self):
        self.bot = None
        self._tab_items = {}
        self.tab_menu.configure(state="disabled", values=["(nenhuma selecionada)"])
        self.refresh_tabs_button.configure(state="disabled")
        self.start_button.configure(state="normal", text="Abrir Navegador")
        self.stop_button.configure(state="disabled")
        self._set_status("Desconectado", "#ff6b6b")
        self.quick_status.configure(text="Pronto. Clique em Abrir Navegador.")
        self.log("Bot parado.")

    # ------------------------------------------------------------------
    # Log / Console / Status bar
    # ------------------------------------------------------------------

    def log(self, message: str):
        logger.info(message)
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {message}"

        # Console (aba)
        self.console_box.configure(state="normal")
        self.console_box.insert("end", line + "\n")
        self.console_box.see("end")
        self.console_box.configure(state="disabled")

        # Status bar
        short = message if len(message) <= 80 else message[:77] + "..."
        self.status_bar_label.configure(text=short)

    def _emit(self, message: str):
        self.after(0, lambda: self.log(message))

    def _clear_console(self):
        self.console_box.configure(state="normal")
        self.console_box.delete("1.0", "end")
        self.console_box.configure(state="disabled")

    def _set_status(self, text: str, color: str):
        self.connection_label.configure(text=f"● {text}", text_color=color)

    # ------------------------------------------------------------------
    # Update banner
    # ------------------------------------------------------------------

    def _show_update_banner(self, new_version: str, download_url: str):
        def _show():
            self._update_url = download_url
            self._update_label.configure(
                text=f"🆕  Nova versao disponivel: v{new_version}"
            )
            self._update_banner.grid(row=0, column=0, sticky="ew", after=self.tabview)
            self.log(f"Atualizacao disponivel: v{new_version}")
        self.after(0, _show)

    def _open_update_url(self):
        import webbrowser
        if self._update_url:
            webbrowser.open(self._update_url)

    # ------------------------------------------------------------------
    # Icone / Geometria
    # ------------------------------------------------------------------

    def _apply_window_icon(self):
        try:
            if _ICON_ICO.exists():
                self.iconbitmap(str(_ICON_ICO))
        except Exception as exc:
            logger.debug(f"iconbitmap falhou: {exc}")
        try:
            if _ICON_PNG.exists():
                from tkinter import PhotoImage
                self.iconphoto(True, PhotoImage(file=str(_ICON_PNG)))
        except Exception as exc:
            logger.debug(f"iconphoto falhou: {exc}")

    def _restore_geometry(self):
        try:
            geom = self._settings.get_str("window_geometry", "")
            if geom and "x" in geom:
                self.geometry(geom)
        except Exception:
            pass

    def _on_closing(self):
        if self.bot:
            try:
                self.bot.stop()
            except Exception:
                pass
        try:
            self._settings.set("window_geometry", self.geometry())
            self._settings.save()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = NMTBotApp()
    app.protocol("WM_DELETE_WINDOW", app._on_closing)
    app.mainloop()
