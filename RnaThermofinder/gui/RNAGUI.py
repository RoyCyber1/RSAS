import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk, messagebox, scrolledtext
from .settings_dialog import SettingsDialog  # Your existing analysis settings
from .sequence_settings_dialog import SequenceSettingsDialog

# ✨ NEW: Import CSV output settings (note the different name)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # Add project root to path
from settings_manager import SettingsManager
from .settings_dialog_csv import SettingsDialog_CSV

# Import from core
from RnaThermofinder.core import FastaParse
from RnaThermofinder.core import HairpinAnalysis



class RNAThermoFinderGUI:
    """Main GUI application for RNA Thermometer Finder"""

    def __init__(self, root):
        self.root = root
        self.root.title("RNA Thermometer Finder v2.1.0")
        self.root.geometry("1000x500")

        #Theme
        self._apply_light_theme()

        # State variables
        self.sequences = []
        self.results = []
        self.analysis_settings = {
            'au_min': 50, 'au_max': 60,
            'gc_min': 0, 'gc_max': 30,
            'gu_min': 15, 'gu_max': 25,
            'mfe_25_min': -17, 'mfe_25_max': -10,
            'mfe_37_min': -13, 'mfe_37_max': -6,
            'mfe_42_min': -7, 'mfe_42_max': -2,
        }
        self.status_var= tk.StringVar(value="Ready")
        # ✨ NEW: CSV output settings manager
        self.csv_settings_manager = SettingsManager("csv_output_settings.json")

        # Set output directory (use absolute path)
        project_root = Path(__file__).parent.parent.parent
        self.output_dir = project_root / "Data" / "Outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)


        # Initialize UI
        self._create_widgets()
        self._create_menu()

    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.root, self.analysis_settings)
        result = dialog.show()
        if result:
            self.analysis_settings = result
            self.log("✓ Settings updated")

    def _create_widgets(self):
        # Professional header with dark background
        header_frame = tk.Frame(self.root, bg=self.colors['header_bg'], height=55)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        header_frame.grid_propagate(False)

        # Title
        title_label = tk.Label(
            header_frame,
            text="RNA Thermometer Finder",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors['header_bg'],
            fg=self.colors['header_fg']
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=12)

        # Subtitle/Version
        subtitle_label = tk.Label(
            header_frame,
            text="Bioinformatics Analysis Tool  •  v2.1.0",
            font=("Segoe UI", 9),
            bg=self.colors['header_bg'],
            fg='#95a5a6'
        )
        subtitle_label.pack(side=tk.LEFT, padx=5)

        # Main frame
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)  # Changed from 1 to 2

        # File selection section with better styling
        file_label = ttk.Label(
            main_frame,
            text="Input File:",
            font=("Segoe UI", 10, "bold")
        )
        file_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(main_frame, textvariable=self.file_path_var, width=60)
        file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

        browse_btn = ttk.Button(main_frame, text="Browse", command=self.browse_file)
        browse_btn.grid(row=0, column=2, padx=(5, 0))

        # Results display label
        results_label = ttk.Label(
            main_frame,
            text="Analysis Output:",
            font=("Segoe UI", 10, "bold")
        )
        results_label.grid(row=1, column=0, sticky=tk.NW, pady=(15, 5))

        # Use ScrolledText for automatic scrollbar
        # Use ScrolledText for automatic scrollbar
        self.results_text = scrolledtext.ScrolledText(
            main_frame,
            height=30,
            width=90,
            wrap=tk.WORD,
            font=("Consolas", 9),  # Monospace for sequences
            bg=self.colors['entry_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['accent'],
            selectbackground=self.colors['select_bg'],
            selectforeground='#ffffff',
            relief='solid',
            borderwidth=1,
            highlightthickness=0,
            padx=8,
            pady=8
        )
        self.results_text.grid(
            row=2, column=0, columnspan=3,
            sticky=(tk.W, tk.E, tk.N, tk.S),
            pady=(0, 10)
        )

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)

        # Buttons
        # Button frame with better spacing
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=15)

        # Buttons with icons
        self.analyze_btn = ttk.Button(
            button_frame,
            text="🧬 Analyze",
            command=self.run_analysis
        )
        self.analyze_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Clear",
            command=self.clear_output
        ).pack(side=tk.LEFT, padx=5)

        self.export_btn = ttk.Button(
            button_frame,
            text="💾 Export",
            command=self.export_results,
            state=tk.DISABLED
        )
        self.export_btn.pack(side=tk.LEFT, padx=5)

        # Separator for settings buttons
        separator = ttk.Separator(button_frame, orient=tk.VERTICAL)
        separator.pack(side=tk.LEFT, fill=tk.Y, padx=15, pady=3)

        ttk.Button(
            button_frame,
            text="⚙️ Analysis Settings",
            command=self.open_settings
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="📊 CSV Output",
            command=self.open_csv_settings
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🧬 Sequence Options",
            command=self.open_sequence_settings
        ).pack(side=tk.LEFT, padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))

        # 🎨 REPLACE YOUR OLD STATUS BAR CODE WITH THIS:
        # Status bar with clean styling
        self.status_frame = tk.Frame(self.root, bg=self.colors['entry_bg'])
        self.status_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))

        status_bar = tk.Label(
            self.status_frame,
            textvariable=self.status_var,
            relief=tk.FLAT,
            anchor=tk.W,
            bg=self.colors['entry_bg'],
            fg=self.colors['fg'],
            font=('Segoe UI', 9),
            padx=15,
            pady=8,
            borderwidth=1,
            bd=0
        )
        status_bar.pack(fill=tk.X)

        # Add subtle top border
        separator = tk.Frame(self.status_frame, height=1, bg=self.colors['border'])
        separator.pack(fill=tk.X, side=tk.TOP)

    def _create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open", command=self.browse_file)
        file_menu.add_command(label="Export Results", command=self.export_results)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="⚙️ Analysis Settings", command=self.open_settings)
        settings_menu.add_command(label="📊 CSV Output", command=self.open_csv_settings)
        settings_menu.add_command(label="🧬 Sequence Options", command=self.open_sequence_settings)

    def _apply_light_theme(self):
        """Apply professional scientific light theme"""

        # Color scheme - Clean scientific interface (like NCBI, Ensembl)
        self.colors = {
            'bg': '#ffffff',  # Pure white background
            'fg': '#2c3e50',  # Dark blue-gray text
            'accent': '#2980b9',  # Professional blue (scientific tools)
            'button_bg': '#ecf0f1',  # Light gray buttons
            'button_fg': '#2c3e50',  # Dark text on buttons
            'entry_bg': '#f8f9fa',  # Very light gray for inputs
            'entry_fg': '#2c3e50',  # Dark text
            'select_bg': '#3498db',  # Bright blue selection
            'border': '#bdc3c7',  # Medium gray borders
            'error': '#e74c3c',  # Clear red for errors
            'success': '#27ae60',  # Scientific green
            'warning': '#f39c12',  # Orange warning
            'highlight': '#16a085',  # Teal for RNA/DNA
            'header_bg': '#34495e',  # Dark header background
            'header_fg': '#ffffff'  # White header text
        }

        # Configure root window
        self.root.configure(bg=self.colors['bg'])

        # Configure ttk styles
        style = ttk.Style()
        style.theme_use('clam')

        # Configure TFrame
        style.configure('TFrame', background=self.colors['bg'])

        # Configure TLabel - Professional, readable
        style.configure('TLabel',
                        background=self.colors['bg'],
                        foreground=self.colors['fg'],
                        font=('Segoe UI', 10))

        # Configure TButton - Clean, professional
        style.configure('TButton',
                        background=self.colors['button_bg'],
                        foreground=self.colors['button_fg'],
                        borderwidth=1,
                        bordercolor=self.colors['border'],
                        focuscolor=self.colors['accent'],
                        font=('Segoe UI', 9, 'bold'),
                        padding=8,
                        relief='raised')

        style.map('TButton',
                  background=[('active', self.colors['accent']),
                              ('pressed', '#2471a3'),
                              ('disabled', '#e0e0e0')],
                  foreground=[('active', '#ffffff'),
                              ('pressed', '#ffffff'),
                              ('disabled', '#95a5a6')])

        # Configure TEntry
        style.configure('TEntry',
                        fieldbackground=self.colors['entry_bg'],
                        foreground=self.colors['entry_fg'],
                        insertcolor=self.colors['accent'],
                        borderwidth=1,
                        relief='solid',
                        bordercolor=self.colors['border'])

        # Configure TProgressbar - Professional blue
        style.configure('TProgressbar',
                        background=self.colors['accent'],
                        troughcolor=self.colors['entry_bg'],
                        borderwidth=1,
                        bordercolor=self.colors['border'],
                        thickness=8)

        # Configure LabelFrame
        style.configure('TLabelframe',
                        background=self.colors['bg'],
                        foreground=self.colors['accent'],
                        borderwidth=1,
                        relief='solid',
                        bordercolor=self.colors['border'])

        style.configure('TLabelframe.Label',
                        background=self.colors['bg'],
                        foreground=self.colors['accent'],
                        font=('Segoe UI', 10, 'bold'))

    def browse_file(self):
        """Open file dialog for sequence selection"""
        filename = filedialog.askopenfilename(
            title="Select sequence file",
            filetypes=[
                ("FASTA files", "*.fasta *.fa"),
                ("CSV files", "*.csv"),
                ("TSV files", "*.tsv"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.file_path_var.set(filename)

    def log(self, message):
        """Add message to output text widget"""
        self.results_text.insert(tk.END, message + "\n")
        self.results_text.see(tk.END)
        self.root.update_idletasks()

    def browse_output(self):
        """Open directory dialog for output selection"""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir = Path(directory)
            self.output_var.set(str(directory))
            self.log(f"Output directory: {directory}")

    def _update_log(self, message):
        """Internal method to update log (runs in main thread)"""
        self.results_text.insert(tk.END, message + "\n")
        self.results_text.see(tk.END)
        self.root.update_idletasks()

    def clear_output(self):
        """Clear the output text"""
        self.results_text.delete(1.0, tk.END)
        self.results = []
        self.sequences = []
        self.status_var.set("Ready")
        self.export_btn.config(state=tk.DISABLED)

    def open_csv_settings(self):
        """Open CSV output settings dialog"""
        dialog = SettingsDialog_CSV(self.root, self.csv_settings_manager)
        dialog.show()
        # Settings are automatically saved when user clicks "Save Settings"
        self.log("✓ CSV output settings available")

    def open_sequence_settings(self):
        """Open sequence processing settings dialog"""
        try:
            csv_settings = SettingsManager("csv_output_settings.json")
            dialog = SequenceSettingsDialog(self.root, csv_settings)
            dialog.show()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open sequence settings: {e}")




    def run_analysis(self):
        """Execute RNA thermometer analysis in a separate thread"""
        file_path = self.file_path_var.get()

        if not file_path:
            messagebox.showwarning("No File", "Please select a FASTA file first")
            return

        if not Path(file_path).exists():
            messagebox.showerror("Error", "Selected file does not exist")
            return

        # Disable button and start progress
        self.analyze_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        self.clear_output()
        self.status_var.set("Loading sequences...")

        # Run in separate thread to keep GUI responsive
        thread = threading.Thread(target=self._perform_analysis, args=(file_path,))
        thread.daemon = True
        thread.start()

    def _perform_analysis(self, file_path):
        """Perform the actual RNA analysis (runs in separate thread)"""
        try:
            self.status_var.set("Parsing FASTA file...")

            # # Parse FASTA file (convert to RNA)
            # self.sequences = FastaParse.read_fasta(file_path, convert_to_rna=True)
            # self.log(f"Loaded {len(self.sequences)} sequences\n")

            # Detect file type by extension
            file_path_lower = file_path.lower()
            if file_path_lower.endswith((".fa", ".fasta")):
                # Parse FASTA
                self.sequences = FastaParse.read_fasta(file_path, convert_to_rna=True, validate=True)
            elif file_path_lower.endswith(".csv")or file_path_lower.endswith(".tsv"):
                # Parse CSV or TSV
                self.sequences = FastaParse.read_csv_tsv_sequences(file_path, skip_rows=33, seq_col=10, convert_to_rna=True)
            else:
                raise ValueError(f"Unsupported file type: {file_path}")


            self.status_var.set(f"Analyzing {len(self.sequences)} sequences...")

            # Run analysis with log callback (NO PARENTHESES!)

            # Control how many sequences processed
            #max_sequences = 200  # process only 100 sequences
            #self.sequences = self.sequences[:max_sequences]

            self.results = HairpinAnalysis.calculate_results_final(
                self.sequences,
                self.output_dir,
                self.analysis_settings,
                self.log,  # ← Pass function reference, not self.log()
                self.csv_settings_manager
            )

            self.status_var.set(f"✅ Analysis complete! Processed {len(self.sequences)} sequences")
            self.export_btn.config(state=tk.NORMAL)

        except Exception as e:
            self.status_var.set("❌ Error occurred")
            self.log(f"\n❌ ERROR: {str(e)}")

            # Show detailed error
            import traceback
            error_details = traceback.format_exc()
            self.log(error_details)
            messagebox.showerror("Analysis Error", f"An error occurred:\n{str(e)}")

        finally:
            # Re-enable button and stop progress
            self.root.after(0, lambda: self.analyze_btn.config(state=tk.NORMAL))
            self.root.after(0, self.progress.stop)




    def _display_results(self):
        """Display results in text widget"""
        self.results_text.delete(1.0, tk.END)
        if self.results:
            self.log(f"Displaying {len(self.results)} results")
            for result in self.results:
                self.log(str(result))
        else:
            self.log("No results to display")

    def _open_folder(self, folder_path: Path):
        """Open folder in file explorer (cross-platform)"""
        import sys
        import subprocess

        try:
            if sys.platform == 'win32':  # Windows
                os.startfile(folder_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', folder_path])
            else:  # Linux
                subprocess.call(['xdg-open', folder_path])
        except Exception as e:
            self.log(f"Could not open folder: {str(e)}")


    def export_results(self):
        """Export results to user-selected location"""
        if not self.results:
            messagebox.showwarning("No Results", "Run analysis first")
            return

        try:
            # Ask user where to save the file
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"rna_results_{timestamp}.csv"

            output_file = filedialog.asksaveasfilename(
                title="Save Results As",
                defaultextension=".csv",
                filetypes=[
                    ("CSV files", "*.csv"),
                    ("All files", "*.*")
                ],
                initialfile=default_filename,
                initialdir=str(Path.home() / "Downloads")  # Start in Downloads
            )

            # User cancelled
            if not output_file:
                return

            # Copy the CSV from output directory to selected location
            source_csv = self.output_dir / "rna_results.csv"
            if source_csv.exists():
                import shutil
                shutil.copy2(source_csv, output_file)

                self.log(f"\n✅ Results exported to: {output_file}")
                messagebox.showinfo(
                    "Export Success",
                    f"Results exported successfully!\n\n{Path(output_file).name}"
                )

                # Ask if user wants to open the folder
                if messagebox.askyesno("Open Folder?", "Would you like to open the folder containing the file?"):
                    self._open_folder(Path(output_file).parent)
            else:
                messagebox.showerror("Error", "Results file not found. Please run analysis first.")

        except Exception as e:
            self.log(f"❌ Export failed: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export:\n{str(e)}")


def main():
    """Entry point for GUI application"""
    root = tk.Tk()
    app = RNAThermoFinderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

