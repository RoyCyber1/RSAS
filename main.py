"""
RSAS: RNA Structure Analysis Suite — Main Entry Point
"""

import multiprocessing
import customtkinter as ctk
from RnaThermofinder.gui.RNAGUI import RSASApp

if __name__ == "__main__":
    multiprocessing.freeze_support()
    ctk.set_appearance_mode("System")   # Follow OS light/dark preference
    ctk.set_default_color_theme("blue") # Scientific blue accent
    root = ctk.CTk()
    app = RSASApp(root)
    root.mainloop()
