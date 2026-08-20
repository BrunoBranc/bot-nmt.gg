from app.gui.main_window import NMTBotApp


if __name__ == "__main__":
    app = NMTBotApp()
    app.protocol("WM_DELETE_WINDOW", app._on_closing)
    app.mainloop()
