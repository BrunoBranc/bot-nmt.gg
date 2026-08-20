r"""Interface grafica do NMTBot.

CustomTkinter app com:
  - Botao Abrir Navegador: abre o Chromium no nmt.gg e deixa o usuario
    resolver Cloudflare/login manualmente.
  - Botao Iniciar bot (START): inicia a automacao 100% autonoma.
  - Painel de configuracoes persistidas.
  - Painel de estatisticas em tempo real.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from app.bot.engine import BotEngine
from app.gui.settings import get_settings
from app.utils.logger import logger

_ICONS_DIR = Path(__file__).resolve().parents[2] / "assets"
_ICON_ICO = _ICONS_DIR / "nmt_bot_icon.ico"
_ICON_PNG = _ICONS_DIR / "nmt_bot_icon.png"


class NMTBotApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Bot NMT.gg")
        self.geometry("950x650")
        self.minsize(850, 550)

        self._apply_window_icon()

        self._settings = get_settings()
        self._restore_geometry()

        self.bot: Optional[BotEngine] = None
        self._stats_timer = None
        self._tab_items: dict = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=25, pady=(25, 5), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="Bot NMT.gg",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).grid(row=0, column=0, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(
            header,
            text="Suporte via discord: @capzluck",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        ).grid(row=1, column=0, padx=10, sticky="w")

        # Status da conexao
        self.connection_label = ctk.CTkLabel(
            header,
            text="* Desconectado",
            font=ctk.CTkFont(size=11),
            text_color="orange",
        )
        self.connection_label.grid(row=0, column=1, padx=10, sticky="e")

        # Abas principais
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=2, column=0, padx=25, pady=10, sticky="nsew")

        self.tab_control = self.tabview.add("Controle")
        self.tab_config = self.tabview.add("Configurações")
        self.tab_stats = self.tabview.add("Estatísticas")

        self._build_control_tab()
        self._build_config_tab()
        self._build_stats_tab()

        # Log inferior
        self.status = ctk.CTkTextbox(self, state="disabled", height=120)
        self.status.grid(row=3, column=0, padx=25, pady=(0, 20), sticky="ew")

        self._load_settings_to_ui()

        self.log("Aplicacao iniciada.")
        self.log("Clique em Abrir Navegador para abrir o nmt.gg.")    # ------------------------------------------------------------------
    # UI Builders
    # ------------------------------------------------------------------
    def _build_control_tab(self) -> None:
        tab = self.tab_control
        tab.grid_columnconfigure(0, weight=1)

        # Headless
        self.headless_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            tab,
            text="Headless (sem janela visivel)",
            variable=self.headless_var,
        ).grid(row=0, column=0, padx=12, pady=12, sticky="w")

        # Botoes
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=1, column=0, padx=12, pady=12, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        self.start_button = ctk.CTkButton(
            btn_frame,
            text="Abrir Navegador",
            command=self.on_start_clicked,
            fg_color="#2fa84f",
            hover_color="#279042",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.start_button.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        self.stop_button = ctk.CTkButton(
            btn_frame,
            text="Parar bot",
            command=self.stop_bot,
            state="disabled",
            fg_color="#a8302f",
            hover_color="#8a2726",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.stop_button.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        # Seletor de aba do Chrome
        tab_row = ctk.CTkFrame(tab, fg_color="transparent")
        tab_row.grid(row=2, column=0, padx=12, pady=(4, 8), sticky="ew")
        tab_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tab_row, text="Aba do Chrome:").grid(row=0, column=0, padx=(12, 8), pady=6, sticky="w")
        self.tab_menu = ctk.CTkOptionMenu(
            tab_row,
            values=["(nenhuma selecionada)"],
            command=self._on_tab_selected,
            state="disabled",
        )
        self.tab_menu.grid(row=0, column=1, padx=8, pady=6, sticky="ew")

        refresh_btn = ctk.CTkButton(
            tab_row,
            text="Atualizar abas",
            command=self._refresh_tabs,
            state="disabled",
            width=100,
        )
        refresh_btn.grid(row=0, column=2, padx=8, pady=6)
        self.refresh_tabs_button = refresh_btn

        # Status rapido
        self.quick_status = ctk.CTkLabel(
            tab,
            text="Pronto. Clique em Abrir Navegador.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.quick_status.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="w")

    def _build_config_tab(self) -> None:
        tab = self.tab_config
        tab.grid_columnconfigure(1, weight=1)

        row = 0
        self.config_vars = {}

        def add_entry(label, key, row, tooltip="", type_="float"):
            ctk.CTkLabel(tab, text=label).grid(row=row, column=0, padx=12, pady=6, sticky="w")
            if type_ == "bool":
                var = ctk.BooleanVar()
                widget = ctk.CTkCheckBox(tab, text="", variable=var)
                widget.grid(row=row, column=1, padx=12, pady=6, sticky="w")
            else:
                var = ctk.StringVar()
                widget = ctk.CTkEntry(tab, textvariable=var, width=140)
                widget.grid(row=row, column=1, padx=12, pady=6, sticky="w")
                if tooltip:
                    ctk.CTkLabel(
                        tab, text=tooltip, font=ctk.CTkFont(size=10), text_color="gray"
                    ).grid(row=row, column=2, padx=8, sticky="w")
            self.config_vars[key] = (var, type_)
            return row + 1

        ctk.CTkLabel(tab, text="Engine", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=12, pady=(12, 6), sticky="w"
        )
        row += 1
        row = add_entry("Loop interval (s)", "loop_interval", row, "Tempo entre iteracoes", "float")
        row = add_entry("Poll interval (s)", "poll_interval", row, "Intervalo de leitura", "float")
        row = add_entry("Max figuras/rodada", "max_figures_per_round", row, "Maximo por rodada", "int")

        ctk.CTkLabel(tab, text="Humanizer (delays)", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=12, pady=(12, 6), sticky="w"
        )
        row += 1
        row = add_entry("Base delay min (ms)", "humanize_base_delay_min", row, "Minimo", "int")
        row = add_entry("Base delay max (ms)", "humanize_base_delay_max", row, "Maximo", "int")
        row = add_entry("Click delay min (ms)", "humanize_click_delay_min", row, "Minimo", "int")
        row = add_entry("Click delay max (ms)", "humanize_click_delay_max", row, "Maximo", "int")
        row = add_entry("Round delay min (ms)", "humanize_round_delay_min", row, "Minimo", "int")
        row = add_entry("Round delay max (ms)", "humanize_round_delay_max", row, "Maximo", "int")

        ctk.CTkLabel(tab, text="Cloudflare", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=12, pady=(12, 6), sticky="w"
        )
        row += 1
        row = add_entry("Auto timeout (s)", "cloudflare_auto_timeout", row, "Tempo auto", "float")
        row = add_entry("Manual timeout (s)", "cloudflare_manual_timeout", row, "Tempo manual", "float")

        save_btn = ctk.CTkButton(
            tab,
            text="Salvar configurações",
            command=self._save_config,
            fg_color="#2fa84f",
            hover_color="#279042",
        )
        save_btn.grid(row=row + 1, column=0, columnspan=3, padx=12, pady=20, sticky="ew")
    def _build_stats_tab(self) -> None:
        tab = self.tab_stats
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)

        self.stats_labels = {}

        def add_stat_card(row, col, label, key, fmt="{}"):
            frame = ctk.CTkFrame(tab)
            frame.grid(row=row, column=col, padx=12, pady=8, sticky="nsew")
            frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=11), text_color="gray").grid(
                row=0, column=0, padx=12, pady=(10, 0)
            )
            val_lbl = ctk.CTkLabel(frame, text="0", font=ctk.CTkFont(size=24, weight="bold"))
            val_lbl.grid(row=1, column=0, padx=12, pady=(0, 10))
            self.stats_labels[key] = (val_lbl, fmt)

        add_stat_card(0, 0, "Figuras colocadas", "figures_placed", "{}")
        add_stat_card(0, 1, "Rodadas vistas", "rounds_seen", "{}")
        add_stat_card(1, 0, "Rodadas processadas", "rounds_processed", "{}")
        add_stat_card(1, 1, "Erros", "errors", "{}")
        add_stat_card(2, 0, "Uptime", "uptime", self._fmt_uptime)
        add_stat_card(2, 1, "Rodada atual", "current_round", "{}")

        # --- Ganhos NMT ---
        ctk.CTkLabel(
            tab, text="Ganhos NMT", font=ctk.CTkFont(weight="bold")
        ).grid(row=3, column=0, columnspan=2, padx=12, pady=(16, 4), sticky="w")

        nmt_frame = ctk.CTkFrame(tab)
        nmt_frame.grid(row=4, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="ew")
        nmt_frame.grid_columnconfigure(0, weight=1)
        nmt_frame.grid_columnconfigure(1, weight=1)
        nmt_frame.grid_columnconfigure(2, weight=1)

        # Total NMT ganho
        ctk.CTkLabel(nmt_frame, text="Total NMT ganho", font=ctk.CTkFont(size=11), text_color="gray").grid(
            row=0, column=0, padx=12, pady=(10, 0)
        )
        self.nmt_total_label = ctk.CTkLabel(
            nmt_frame, text="0.0000", font=ctk.CTkFont(size=22, weight="bold"), text_color="#f0b429"
        )
        self.nmt_total_label.grid(row=1, column=0, padx=12, pady=(0, 10))

        # Vitorias
        ctk.CTkLabel(nmt_frame, text="Vitorias", font=ctk.CTkFont(size=11), text_color="gray").grid(
            row=0, column=1, padx=12, pady=(10, 0)
        )
        self.nmt_wins_label = ctk.CTkLabel(
            nmt_frame, text="0", font=ctk.CTkFont(size=22, weight="bold"), text_color="#2fa84f"
        )
        self.nmt_wins_label.grid(row=1, column=1, padx=12, pady=(0, 10))

        # Ultimo ganho
        ctk.CTkLabel(nmt_frame, text="Ultimo ganho", font=ctk.CTkFont(size=11), text_color="gray").grid(
            row=0, column=2, padx=12, pady=(10, 0)
        )
        self.nmt_last_label = ctk.CTkLabel(
            nmt_frame, text="-", font=ctk.CTkFont(size=13), text_color="gray"
        )
        self.nmt_last_label.grid(row=1, column=2, padx=12, pady=(0, 10))

        ctk.CTkLabel(tab, text="Rodada / Timer", font=ctk.CTkFont(weight="bold")).grid(
            row=5, column=0, padx=12, pady=(12, 4), sticky="w"
        )
        self.round_timer_label = ctk.CTkLabel(tab, text="Rodada: - | Timer: -s", font=ctk.CTkFont(size=12))
        self.round_timer_label.grid(row=6, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="w")

        reset_btn = ctk.CTkButton(
            tab,
            text="Resetar estatísticas",
            command=self._reset_stats,
            fg_color="#a8302f",
            hover_color="#8a2726",
        )
        reset_btn.grid(row=7, column=0, columnspan=2, padx=12, pady=12, sticky="ew")

    # ------------------------------------------------------------------
    # Settings / UI sync
    # ------------------------------------------------------------------
    def _load_settings_to_ui(self) -> None:
        s = self._settings
        self.headless_var.set(s.get_bool("headless", False))
        for key, (var, type_) in self.config_vars.items():
            if type_ == "int":
                var.set(str(s.get_int(key, self._settings._DEFAULTS.get(key, 0))))
            else:
                var.set(str(s.get_float(key, self._settings._DEFAULTS.get(key, 0.0))))

    def _save_config(self) -> None:
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
    # Stats UI
    # ------------------------------------------------------------------
    def _fmt_uptime(self, seconds):
        if seconds < 60:
            return f"{int(seconds)}s"
        m = int(seconds // 60)
        s = int(seconds % 60)
        if m < 60:
            return f"{m}m {s}s"
        h = m // 60
        m = m % 60
        return f"{h}h {m}m"

    def _update_stats_ui(self, stats: dict) -> None:
        for key, (lbl, fmt) in self.stats_labels.items():
            val = stats.get(key, 0)
            try:
                txt = fmt(val) if callable(fmt) else fmt.format(val)
            except Exception:
                txt = str(val)
            lbl.configure(text=txt)
        cr = stats.get("current_round", "-")
        ct = stats.get("current_timer", 0)
        self.round_timer_label.configure(text=f"Rodada: {cr} | Timer: {ct}s")

        # Atualiza painel de ganhos NMT
        nmt_total = stats.get("nmt_total", 0.0)
        nmt_wins  = stats.get("nmt_wins", 0)
        nmt_last  = stats.get("nmt_last", "-")
        self.nmt_total_label.configure(text=f"{nmt_total:.4f}")
        self.nmt_wins_label.configure(text=str(nmt_wins))
        self.nmt_last_label.configure(text=str(nmt_last))

    def _on_bot_stats(self, stats: dict) -> None:
        self.after(0, lambda: self._update_stats_ui(stats))

    def _reset_stats(self) -> None:
        if self.bot:
            with self.bot._stats_lock:
                self.bot._stats = {
                    "figures_placed": 0,
                    "rounds_seen": 0,
                    "rounds_processed": 0,
                    "errors": 0,
                    "start_time": self.bot._stats.get("start_time", time.time()),
                    "current_round": "-",
                    "current_timer": 0,
                    "last_action_time": 0.0,
                    "nmt_total": 0.0,
                    "nmt_wins": 0,
                    "nmt_last": "-",
                }
            self._update_stats_ui(self.bot.stats)
        self.log("Estatisticas resetadas.")
    # ------------------------------------------------------------------
    # Fluxo: Abrir Navegador -> Iniciar bot (START)
    # ------------------------------------------------------------------
    def on_start_clicked(self) -> None:
        """Botao principal: Abrir Chrome quando parado; Iniciar quando pronto."""
        if self.bot is None:
            self._open_browser_flow()
            return
        if self.bot.is_running:
            self.log("Bot ja esta em execucao.")
            return
        if self.bot.browser_ready:
            self._start_automation_flow()
            return
        self.log("Chrome ainda nao esta pronto. Abra, conecte e selecione a aba.")

    def _open_browser_flow(self) -> None:
        """Fase 1: abre/conecta ao Chrome real do usuario."""
        s = self._settings
        headless = self.headless_var.get()
        self.log("Abrindo Chrome...")

        self.bot = BotEngine(
            headless=headless,
            loop_interval=s.get_float("loop_interval", 5.0),
            poll_interval=s.get_float("poll_interval", 3.0),
            on_status=self._emit,
        )
        self.bot.set_on_stats(self._on_bot_stats)
        self.bot.set_on_browser_ready(self._on_browser_ready)
        self.bot.open_browser()

        self.start_button.configure(state="disabled")
        self.connection_label.configure(text="* Conectando...", text_color="orange")
        self.quick_status.configure(text="Abrindo Chrome...")
        self.log("Resolva o Cloudflare/login na janela do Chrome, atualize as abas e selecione uma.")

    def _on_browser_ready(self) -> None:
        """Callback: Chrome conectado - popula a lista de abas."""
        self.after(0, self._refresh_tabs)
        self.after(0, lambda: self.tab_menu.configure(state="normal"))
        self.after(0, lambda: self.refresh_tabs_button.configure(state="normal"))
        self.after(0, lambda: self.start_button.configure(state="disabled", text="Iniciar bot"))
        self.after(0, lambda: self.connection_label.configure(text="* Conectado", text_color="green"))
        self.after(
            0,
            lambda: self.quick_status.configure(
                text="Chrome conectado. Selecione a aba e clique em Iniciar bot."
            ),
        )

    def _refresh_tabs(self) -> None:
        """Atualiza o seletor com as abas abertas no Chrome."""
        if not self.bot or not self.bot.browser.is_alive():
            return
        tabs = self.bot.list_tabs()
        if not tabs:
            self.tab_menu.configure(values=["(nenhuma aba aberta)"])
            return
        labels = [f"{t['index']} - {t['title'][:45]} ({t['url'][:50]})" for t in tabs]
        self.tab_menu.configure(values=labels)
        self.tab_menu.set(labels[0])
        self._tab_items = {label: t["index"] for label, t in zip(labels, tabs)}
        self.log(f"{len(tabs)} aba(s) encontrada(s) no Chrome.")

    def _on_tab_selected(self, label: str) -> None:
        """Quando o usuario escolhe a aba, define no bot e habilita START."""
        if not self.bot:
            return
        index = self._tab_items.get(label)
        if index is None:
            return
        if self.bot.select_tab(index):
            self.start_button.configure(state="normal")
            self.quick_status.configure(text=f"Aba {index} selecionada. Clique em Iniciar bot.")
        else:
            self.log("Nao foi possivel selecionar essa aba.")

    def _start_automation_flow(self) -> None:
        """Fase 2: Chrome pronto + aba selecionada - inicia a automacao."""
        self.log("Iniciando automacao...")
        self.bot.start()

        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.connection_label.configure(text="* Automatizando", text_color="green")
        self.quick_status.configure(text="Automatizando...")
        self.log("Automacao iniciada.")

    def stop_bot(self) -> None:
        if not self.bot or not self.bot.is_running:
            self.log("Bot nao esta em execucao.")
            return
        self.log("Parando bot...")
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def _stop_worker(self) -> None:
        try:
            self.bot.stop()
        except Exception as exc:
            self.after(0, lambda: self.log(f"Erro ao parar bot: {exc}"))
            return
        self.after(0, self._on_bot_stopped)

    def _on_bot_stopped(self) -> None:
        self.bot = None
        self._tab_items = {}
        self.tab_menu.configure(state="disabled", values=["(nenhuma selecionada)"])
        self.refresh_tabs_button.configure(state="disabled")
        self.start_button.configure(state="normal", text="Abrir Chrome")
        self.stop_button.configure(state="disabled")
        self.connection_label.configure(text="* Desconectado", text_color="orange")
        self.quick_status.configure(text="Pronto. Clique em Abrir Chrome.")
        self.log("Bot parado.")
    # ------------------------------------------------------------------
    # Icones / Log / Geometry
    # ------------------------------------------------------------------
    def _apply_window_icon(self) -> None:
        try:
            if _ICON_ICO.exists():
                self.iconbitmap(str(_ICON_ICO))
        except Exception as exc:
            logger.debug(f"iconbitmap falhou ({exc})")
        try:
            if _ICON_PNG.exists():
                from tkinter import PhotoImage
                img = PhotoImage(file=str(_ICON_PNG))
                self.iconphoto(True, img)
        except Exception as exc:
            logger.debug(f"iconphoto falhou: {exc}")

    def log(self, message: str) -> None:
        logger.info(message)
        self.status.configure(state="normal")
        self.status.insert("end", message + "\n")
        self.status.see("end")
        self.status.configure(state="disabled")

    def _emit(self, message: str) -> None:
        self.after(0, lambda: self.log(message))

    def _restore_geometry(self) -> None:
        try:
            geom = self._settings.get_str("window_geometry", "")
            if geom and "x" in geom:
                self.geometry(geom)
        except Exception:
            pass

    def _on_closing(self) -> None:
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
