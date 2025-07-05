#!/usr/bin/env python3
"""
Test script to verify the new UI styling
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_styles():
    """Test the new styling system."""
    root = tk.Tk()
    root.title("UI Style Test")
    root.geometry("800x600")
    root.configure(bg="#1a1b26")
    
    # Test the new color palette
    base = '#1a1b26'           # Deep navy/slate
    elevated = '#2a2b36'       # Lighter slate
    surface = '#3a3b46'        # Even lighter
    accent_primary = '#8b2635'  # Rich burgundy
    accent_secondary = '#d4af37' # Golden amber
    success = '#4ade80'        # Soft green
    error = '#f87171'          # Soft red
    text_primary = '#f4f1de'   # Warm cream
    text_secondary = '#a8a8a8' # Warm gray
    
    # Setup styles
    style = ttk.Style()
    try:
        style.theme_use('clam')
    except tk.TclError:
        pass
    
    # Configure styles
    style.configure('Test.TFrame', background=elevated)
    style.configure('Test.TLabel', background=elevated, foreground=text_primary, font=("Segoe UI", 12))
    style.configure('Test.TButton', 
                   foreground='white', 
                   font=("Segoe UI", 11, "bold"),
                   padding=(16, 8),
                   borderwidth=0,
                   relief="flat")
    
    # Create test widgets
    main_frame = ttk.Frame(root, style="Test.TFrame", padding=20)
    main_frame.pack(fill="both", expand=True)
    
    # Title
    title = ttk.Label(main_frame, text="Big Gay Downloader - New UI Test", 
                     font=("Segoe UI", 18, "bold"), foreground=text_primary)
    title.pack(pady=(0, 20))
    
    # Color palette display
    colors_frame = ttk.Frame(main_frame, style="Test.TFrame")
    colors_frame.pack(fill="x", pady=(0, 20))
    
    colors = [
        ("Base", base),
        ("Elevated", elevated),
        ("Surface", surface),
        ("Accent Primary", accent_primary),
        ("Accent Secondary", accent_secondary),
        ("Success", success),
        ("Error", error),
        ("Text Primary", text_primary),
        ("Text Secondary", text_secondary)
    ]
    
    for i, (name, color) in enumerate(colors):
        row = i // 3
        col = i % 3
        
        color_frame = ttk.Frame(colors_frame, style="Test.TFrame")
        color_frame.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
        
        # Color swatch
        swatch = tk.Canvas(color_frame, width=60, height=30, bg=color, highlightthickness=0)
        swatch.pack(pady=(0, 5))
        
        # Color name
        label = ttk.Label(color_frame, text=f"{name}\n{color}", style="Test.TLabel", justify="center")
        label.pack()
    
    # Test buttons
    button_frame = ttk.Frame(main_frame, style="Test.TFrame")
    button_frame.pack(fill="x", pady=(20, 0))
    
    # Primary button
    primary_btn = tk.Button(button_frame, text="Primary Button", 
                           bg=accent_primary, fg="white", 
                           font=("Segoe UI", 11, "bold"),
                           relief="flat", padx=20, pady=8)
    primary_btn.pack(side="left", padx=(0, 10))
    
    # Secondary button
    secondary_btn = tk.Button(button_frame, text="Secondary Button", 
                             bg=accent_secondary, fg="white", 
                             font=("Segoe UI", 11, "bold"),
                             relief="flat", padx=20, pady=8)
    secondary_btn.pack(side="left", padx=(0, 10))
    
    # Success button
    success_btn = tk.Button(button_frame, text="Success Button", 
                           bg=success, fg="white", 
                           font=("Segoe UI", 11, "bold"),
                           relief="flat", padx=20, pady=8)
    success_btn.pack(side="left", padx=(0, 10))
    
    # Error button
    error_btn = tk.Button(button_frame, text="Error Button", 
                         bg=error, fg="white", 
                         font=("Segoe UI", 11, "bold"),
                         relief="flat", padx=20, pady=8)
    error_btn.pack(side="left")
    
    # Test entry
    entry_frame = ttk.Frame(main_frame, style="Test.TFrame")
    entry_frame.pack(fill="x", pady=(20, 0))
    
    entry_label = ttk.Label(entry_frame, text="Test Entry:", style="Test.TLabel")
    entry_label.pack(anchor="w")
    
    test_entry = ttk.Entry(entry_frame, font=("Segoe UI", 11))
    test_entry.pack(fill="x", pady=(5, 0))
    test_entry.insert(0, "Test input field")
    
    print("UI Style Test Window Created")
    print("Color Palette:")
    for name, color in colors:
        print(f"  {name}: {color}")
    
    root.mainloop()

if __name__ == "__main__":
    test_styles() 