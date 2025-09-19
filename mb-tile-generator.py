#!/usr/bin/env python3
"""
Single-file tkinter GUI to edit the LAYOUT parameter in multiboard-tile.scad
Features:
- configure rows and columns
- pick a style for each cell from the project's abbreviations (O, R, L, BR, ...)
- save LAYOUT back into `multiboard-tile.scad`
- run OpenSCAD to export an STL using the exact command the user requested

Usage: run this script from the project folder or anywhere; it writes to the SCAD file by absolute path.
"""

import os
import re
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# --- Configuration ---
DEFAULT_ROWS = 9
DEFAULT_COLS = 9

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SCAD_PATH = os.path.join(WORKSPACE_DIR, "multiboard-tile.scad")
OPENSCAD_CMD = "/Applications/OpenScad.app/Contents/MacOS/OpenSCAD"
EXPORT_CMD_TEMPLATE = '"{openscad}" /dev/stdin --export-format binstl -o "{out}"'
LAYOUT_START_RE = re.compile(r"LAYOUT\s*=\s*\(")

# Abbreviations and their full style names (from multiboard-tile.scad)
ABBREVS = ["O", "R", "L", "BR", "BL", "TR", "TL", "B", "T", "X", "LR", "TB"]
ABBREV_TO_NAME = {
    "O": "NORMAL",
    "R": "RIGHT_EDGE",
    "L": "LEFT_EDGE",
    "BR": "BOTTOM_RIGHT_CORNER",
    "BL": "BOTTOM_LEFT_CORNER",
    "TR": "TOP_RIGHT_CORNER",
    "TL": "TOP_LEFT_CORNER",
    "B": "BOTTOM_EDGE",
    "T": "TOP_EDGE",
    "X": "SKIP",
    "LR": "LEFT_RIGHT_EDGES",
    "TB": "TOP_BOTTOM_EDGES",
}

# --- File parsing utilities ---

def find_layout_block(text):
    """Find the LAYOUT = [ ... ]; block and return (start_index, end_index) spanning the bracketed content.
    If not found return (None, None).
    """
    m = LAYOUT_START_RE.search(text)
    if not m:
        return None, None
    start = m.start()
    # find the opening bracket position
    open_pos = text.find('[', m.end()-1)
    if open_pos == -1:
        return None, None
    # walk to find matching closing bracket
    depth = 0
    i = open_pos
    while i < len(text):
        ch = text[i]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                # find semicolon after closing bracket if present
                end = i+1
                # extend to include following semicolon and optional whitespace/newlines
                while end < len(text) and text[end] in ' \t\r\n;':
                    end += 1
                return start, end
        i += 1
    return None, None


def extract_layout_tokens(text):
    """Return list-of-lists of abbreviations found inside the layout block.
    We look for tokens that match the known abbreviations (TL, O, etc.).
    """
    s, e = find_layout_block(text)
    if s is None:
        return None
    block = text[s:e]
    # find lines that look like rows: [ ... ],
    # extract tokens of 1-2 uppercase letters (e.g. TL, O, BR)
    rows = []
    for row_match in re.finditer(r"\[([^\]]*)\]", block):
        row_text = row_match.group(1)
        # pull tokens like TL or BR or single letters
        tokens = re.findall(r"\b[A-Z]{1,2}\b", row_text)
        if tokens:
            rows.append(tokens)
    return rows


def build_layout_scad_script(layout):
    """Given layout as list-of-lists of abbreviations, produce a script that calls mb_tile()."""
    # Convert layout to proper OpenSCAD array format
    rows = []
    for row in layout:
        row_items = ", ".join(abbr for abbr in row)
        rows.append(f"    [ {row_items} ]")
    layout_array = "[\n" + ",\n".join(rows) + "\n]"
    
    script = f'include <{SCAD_PATH}>;\nmb_tile({layout_array});'
    return script


def load_scad_text():
    with open(SCAD_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def save_scad_text(new_text):
    with open(SCAD_PATH, 'w', encoding='utf-8') as f:
        f.write(new_text)


def write_temp_scad_text(new_text):
    """Write the provided SCAD text to a temp file inside the workspace and return the path.
    This ensures we do not overwrite the original `multiboard-tile.scad`.
    """
    tf = tempfile.NamedTemporaryFile(mode='w', suffix='.scad', prefix='multiboard_temp_', dir=WORKSPACE_DIR, delete=False, encoding='utf-8')
    try:
        tf.write(new_text)
        tf.flush()
        return tf.name
    finally:
        tf.close()


def write_named_scad_text(path, new_text):
    """Write new_text to the provided path (creating or overwriting)."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_text)


# --- GUI ---
class LayoutEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Multiboard Tile Generator')
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - 1024) // 2
        y = (screen_h - 1024) // 2
        self.geometry(f'1024x1024+{x}+{y}')
        

        self.scad_text = ''
        try:
            self.scad_text = load_scad_text()
        except Exception as e:
            messagebox.showerror('Error', f'Could not open {SCAD_PATH}: {e}')
            self.destroy()
            return

        self.layout = []
        self.rows = tk.IntVar(value=DEFAULT_ROWS)
        self.cols = tk.IntVar(value=DEFAULT_COLS)

        self._vars = []  # matrix of StringVar for dropdowns

        # track last-clicked cell (for preset buttons)
        self._last_clicked = None
        
        self.selected_style = 'O'
        self._palette_frames = {}

        self.style = ttk.Style(self)
        self.style.configure('Selected.TFrame', relief="solid",  highlightthickness=2, highlightcolor='#00AA00', highlightbackground='#00AA00')
        self.style.configure('Default.TFrame', relief='flat', borderwidth=2)

        self._build_ui()
        
        self._apply_preset_to_all(self._preset_patterns['ALL'])
        self._populate_grid()
        self._on_palette_select(self.selected_style)


    def _build_ui(self):
        frm_top = ttk.Frame(self)
        frm_top.pack(fill='x', padx=8, pady=8)

        ttk.Label(frm_top, text='Rows:').pack(side='left')
        self.spin_rows = ttk.Spinbox(
            frm_top, from_=1, to=50, textvariable=self.rows, width=5, command=self._on_shape_change
        )
        self.spin_rows.pack(side='left', padx=(4, 12))

        ttk.Label(frm_top, text='Cols:').pack(side='left')
        self.spin_cols = ttk.Spinbox(
            frm_top, from_=1, to=50, textvariable=self.cols, width=5, command=self._on_shape_change
        )
        self.spin_cols.pack(side='left', padx=(4, 12))

        ttk.Button(frm_top, text='↻', command=self._on_shape_change).pack(side='left', padx=(0, 12))
        ttk.Button(frm_top, text='▢', command=self._open_presets_popup).pack(side='left', padx=(0, 12))
        ttk.Button(frm_top, text='→ stl', command=self._export_stl).pack(side='left', padx=6)
        ttk.Button(frm_top, text='→ scad', command=self._export_scad).pack(side='left', padx=6)

        self._preset_patterns = {
            'LTR': {'top':True, 'left':True, 'right':True, 'bottom':False},
            'LT':  {'top':True, 'left':True, 'right':False, 'bottom':False},
            'T':   {'top':True, 'left':False, 'right':False, 'bottom':False},
            'TR':  {'top':True, 'right':True, 'left':False, 'bottom':False},
            'LR':  {'left':True, 'right':True, 'top':False, 'bottom':False},
            'L':   {'left':True, 'top':False, 'right':False, 'bottom':False},
            'NONE':{'top':False,'bottom':False,'left':False,'right':False},
            'R':   {'right':True,'top':False,'left':False,'bottom':False},
            'LBR': {'left':True,'bottom':True,'right':True,'top':False},
            'LB':  {'left':True,'bottom':True,'top':False,'right':False},
            'B':   {'bottom':True,'top':False,'left':False,'right':False},
            'BR':  {'bottom':True,'right':True,'top':False,'left':False},
            'ALL': {'top':True,'bottom':True,'left':True,'right':True},
            'LTB': {'left':True,'top':True,'bottom':True,'right':False},
            'BT':  {'top':True,'bottom':True,'left':False,'right':False},
            'TRB': {'top':True,'right':True,'bottom':True,'left':False},
        }

        self._menu_sep = ttk.Separator(self, orient='horizontal')
        self._menu_sep.pack(fill='x', padx=8, pady=6)

        # Main content frame
        frm_content = ttk.Frame(self)
        frm_content.pack(fill='both', expand=True, padx=8, pady=8)

        # center frame for grid (on the left)
        self.canvas = tk.Canvas(frm_content)
        self.canvas.pack(side='left', fill='both', expand=True)

        self.grid_frame = ttk.Frame(self.canvas)
        self._grid_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor='nw')
        self.canvas.bind('<Configure>', self._on_canvas_config)

        # Palette frame (on the right)
        frm_palette = ttk.Frame(frm_content)
        frm_palette.pack(side='right', fill='y', padx=(8, 0))
        self._build_palette(frm_palette)

        # bottom log
        self.log = tk.Text(self, height=8)
        self.log.pack(fill='x', padx=8, pady=(0, 8))
        self._log('Started with default layout with borders')

    def _build_palette(self, parent_frame):
        ttk.Label(parent_frame, text="Styles").pack(side='top', pady=5)
        
        grid_frame = ttk.Frame(parent_frame)
        grid_frame.pack(side='top')

        ordered = [
            'TL', 'T', 'TR',
            'L',  'O', 'R', 
            'BL', 'B', 'BR',
            'LR', 'X', 'TB'
        ]
        cols = 3
        
        for idx, abbr in enumerate(ordered):
            r = idx // cols
            c = idx % cols
            
            frame = tk.Frame(grid_frame, width=52, height=52, highlightthickness=2, relief="solid")
            frame.grid(row=r, column=c, padx=2, pady=2)
            frame.grid_propagate(False)  # Maintain fixed size
            frame.bind('<Button-1>', lambda e, a=abbr: self._on_palette_select(a))

            cv = tk.Canvas(frame, width=48, height=48, highlightthickness=0)
            cv.place(relx=0.5, rely=0.5, anchor='center')
            cv.bind('<Button-1>', lambda e, a=abbr: self._on_palette_select(a))

            self._draw_icon_on_canvas(cv, abbr)
            self._palette_frames[abbr] = frame

    def _on_palette_select(self, abbr):
        self.selected_style = abbr
        self._log(f'Selected style: {abbr}')

        for a, frame in self._palette_frames.items():
            if a == abbr:
                #frame.configure(style='Selected.TFrame')
                frame.configure(highlightcolor='#00AA00', highlightbackground='#00AA00')
            else:
                frame.configure(highlightcolor='#ffffff', highlightbackground='#ffffff')
                #frame.configure(style='Default.TFrame')

    def _apply_style_to_cell(self, i, j):
        if self.selected_style:
            self.layout[i][j] = self.selected_style
            try:
                self._draw_icon_on_canvas(self._canvases[i][j], self.selected_style)
            except Exception:
                pass
            self._log(f'Applied style {self.selected_style} to cell {i},{j}')
        else:
            self._log('No style selected in palette.')

    def _log(self, *parts):
        self.log.insert('end', ' '.join(str(p) for p in parts) + '\n')
        self.log.see('end')

    # --- Preset helpers ---
    def _draw_preset_icon(self, canvas, pattern):
        """Draw a small icon showing which borders are present in pattern dict."""
        canvas.delete('all')
        w = int(canvas['width']); h = int(canvas['height']); pad = 6
        canvas.create_rectangle(0, 0, w, h, fill='white', outline='')
        canvas.create_rectangle(pad, pad, w - pad, h - pad, outline='black')
        def line(pos):
            if pos == 'top':
                canvas.create_line(pad + 4, pad + 4, w - pad - 4, pad + 4, width=3, fill='black')
            if pos == 'bottom':
                canvas.create_line(pad + 4, h - pad - 4, w - pad - 4, h - pad - 4, width=3, fill='black')
            if pos == 'left':
                canvas.create_line(pad + 4, pad + 4, pad + 4, h - pad - 4, width=3, fill='black')
            if pos == 'right':
                canvas.create_line(w - pad - 4, pad + 4, w - pad - 4, h - pad - 4, width=3, fill='black')
        if pattern.get('top'):
            line('top')
        if pattern.get('bottom'):
            line('bottom')
        if pattern.get('left'):
            line('left')
        if pattern.get('right'):
            line('right')

    def _apply_preset_to_selected(self, abbr):
        # apply preset abbreviation to the last-clicked cell if any
        if not self._last_clicked:
            messagebox.showinfo('No cell', 'Click a cell first to select where to apply the preset')
            return
        i, j = self._last_clicked
        self.layout[i][j] = abbr
        try:
            self._draw_icon_on_canvas(self._canvases[i][j], abbr)
        except Exception:
            pass

    def _apply_preset_to_all(self, pattern=None):
        self._last_pattern = pattern

        # Get current grid dimensions
        r = self.rows.get()
        c = self.cols.get()
        
        # Resize layout to match current dimensions
        # Remove excess rows
        while len(self.layout) > r:
            self.layout.pop()
        
        # Ensure we have enough rows
        while len(self.layout) < r:
            self.layout.append(['O'] * c)
        
        # Fix each row to have correct number of columns
        for i in range(r):
            # Trim excess columns
            while len(self.layout[i]) > c:
                self.layout[i].pop()
            # Add missing columns
            while len(self.layout[i]) < c:
                self.layout[i].append('O')

        # Apply the preset pattern to all cells
        for i in range(r):
            for j in range(c):
                # Determine value for this cell
                is_border = (i == 0) or (i == r - 1) or (j == 0) or (j == c - 1)
                new_abbr = 'O'
                
                if is_border and pattern:
                    top_flag = pattern.get('top', False)
                    bottom_flag = pattern.get('bottom', False)
                    left_flag = pattern.get('left', False)
                    right_flag = pattern.get('right', False)
                    is_top = (i == 0)
                    is_bottom = (i == r - 1)
                    is_left = (j == 0)
                    is_right = (j == c - 1)
                    
                    # Corners first
                    if is_top and is_left and top_flag and left_flag:
                        new_abbr = 'TL'
                    elif is_top and is_right and top_flag and right_flag:
                        new_abbr = 'TR'
                    elif is_bottom and is_left and bottom_flag and left_flag:
                        new_abbr = 'BL'
                    elif is_bottom and is_right and bottom_flag and right_flag:
                        new_abbr = 'BR'
                    elif is_top and top_flag:
                        new_abbr = 'T'
                    elif is_bottom and bottom_flag:
                        new_abbr = 'B'
                    elif is_left and left_flag:
                        new_abbr = 'L'
                    elif is_right and right_flag:
                        new_abbr = 'R'
                    else:
                        new_abbr = 'O'

                self.layout[i][j] = new_abbr
                try:
                    self._draw_icon_on_canvas(self._canvases[i][j], new_abbr)
                except Exception:
                    pass

    def _on_canvas_config(self, event):
        # center the grid_frame inside the canvas
        try:
            c_w = event.width
            g_w = self.grid_frame.winfo_reqwidth()
            x = max(0, (c_w - g_w) // 2)
            self.canvas.coords(self._grid_window, x, 0)
        except Exception:
            pass

    def _populate_grid(self):
        # clear
        for child in self.grid_frame.winfo_children():
            child.destroy()
        # We'll keep a matrix of canvases to draw icons
        self._canvases = []

        r = self.rows.get()
        c = self.cols.get()
        # ensure layout shape matches
        for i in range(r):
            row_canv = []
            for j in range(c):
                # ensure there is an abbreviation value
                try:
                    abbr = self.layout[i][j]
                    if abbr not in ABBREVS:
                        abbr = 'O'
                        self.layout[i][j] = abbr
                except Exception:
                    abbr = 'O'
                    if i >= len(self.layout):
                        # extend layout if necessary
                        while len(self.layout) <= i:
                            self.layout.append(['O'] * c)
                    while len(self.layout[i]) <= j:
                        self.layout[i].append('O')
                    self.layout[i][j] = abbr

                cv = tk.Canvas(self.grid_frame, width=48, height=48, highlightthickness=1, relief='ridge')
                cv.grid(row=i, column=j, padx=4, pady=4)
                # draw the icon for this abbreviation
                self._draw_icon_on_canvas(cv, abbr)
                # left click to apply selected style
                cv.bind('<Button-1>', lambda e, ii=i, jj=j: self._apply_style_to_cell(ii, jj))
                row_canv.append(cv)
            self._canvases.append(row_canv)

    def _draw_icon_on_canvas(self, canvas, abbr):
        # clear
        canvas.delete('all')
        w = int(canvas['width'])
        h = int(canvas['height'])
        pad = 6
        # background
        canvas.create_rectangle(0, 0, w, h, fill='white', outline='')
        # draw cell border
        canvas.create_rectangle(pad, pad, w - pad, h - pad, outline='black')

        # helper to draw edge lines
        def line(pos):
            if pos == 'top':
                canvas.create_line(pad + 4, pad + 4, w - pad - 4, pad + 4, width=3, fill='black')
            if pos == 'bottom':
                canvas.create_line(pad + 4, h - pad - 4, w - pad - 4, h - pad - 4, width=3, fill='black')
            if pos == 'left':
                canvas.create_line(pad + 4, pad + 4, pad + 4, h - pad - 4, width=3, fill='black')
            if pos == 'right':
                canvas.create_line(w - pad - 4, pad + 4, w - pad - 4, h - pad - 4, width=3, fill='black')

        # draw representations for different abbreviations
        if abbr == 'O':
            # NORMAL: small threaded hole - dot in center
            cx = w // 2
            cy = h // 2
            r = 4
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill='black')
        elif abbr == 'X':
            # SKIP: draw an X
            canvas.create_line(pad, pad, w - pad, h - pad, fill='red', width=3)
            canvas.create_line(pad, h - pad, w - pad, pad, fill='red', width=3)
        elif abbr == 'LR':
            # LEFT_RIGHT_EDGES: left and right borders only
            line('left')
            line('right')
        elif abbr == 'TB':
            # TOP_BOTTOM_EDGES: top and bottom borders only  
            line('top')
            line('bottom')
        else:
            # edges and corners
            name = ABBREV_TO_NAME.get(abbr, '')
            if 'TOP' in name:
                line('top')
            if 'BOTTOM' in name:
                line('bottom')
            if 'LEFT' in name:
                line('left')
            if 'RIGHT' in name:
                line('right')

    def _open_presets_popup(self):
        # popup that shows preset icons; clicking applies the preset to all cells
        top = tk.Toplevel(self)
        top.withdraw()
        top.title('Presets')
        top.transient(self)
        top.resizable(False, False)

        # Arrange presets in a 4x4 icon-only grid per user's requested layout.
        desired_abbrs = [
            'LTR', 'LT', 'T',  'TR',
            'LR',   'L',  'NONE',  'R',
            'LBR',  'LB', 'B',  'BR',
            'ALL',   'LTB', 'BT',  'TRB',
        ]
        cols = 4
        for idx, abbr in enumerate(desired_abbrs):
            r = idx // cols
            c = idx % cols
            pattern = self._preset_patterns.get(abbr, {'top':False,'bottom':False,'left':False,'right':False})
            cv = tk.Canvas(top, width=48, height=48, highlightthickness=1, relief='ridge')
            cv.grid(row=r, column=c, padx=4, pady=4)
            self._draw_preset_icon(cv, pattern)
            def make_cb(a=abbr, pat=pattern):
                return lambda e: (self._apply_preset_to_all(pat), top.destroy())
            cv.bind('<Button-1>', make_cb())

        top.update_idletasks()
        top_w = top.winfo_reqwidth()
        top_h = top.winfo_reqheight()
        main_x = self.winfo_rootx(); main_w = self.winfo_width()
        pos_x = main_x + max(0, (main_w // 2) - (top_w // 2))
        try:
            sep = self._menu_sep
            sep.update_idletasks()
            sep_bottom = sep.winfo_rooty() + sep.winfo_height()
            pos_y = sep_bottom
        except Exception:
            main_y = self.winfo_rooty(); main_h = self.winfo_height()
            pos_y = main_y + max(0, (main_h // 2) - (top_h // 2))

        top.geometry(f"{top_w}x{top_h}+{pos_x}+{pos_y}")
        top.deiconify(); top.grab_set(); top.focus_force()

    def _on_shape_change(self):
        try:
            r = int(self.rows.get())
            c = int(self.cols.get())
        except Exception:
            messagebox.showerror('Invalid', 'Rows and Cols must be integers')
            return
        
        if ( self._last_pattern is not None ):
            self._apply_preset_to_all(self._last_pattern)
        self._populate_grid()

    def _gather_layout(self):
        """Gather the current layout based on the current rows/cols settings."""
        r = self.rows.get()
        c = self.cols.get()
        
        result = []
        for i in range(r):
            row = []
            for j in range(c):
                # Get the value from the current layout, defaulting to 'O' if not found
                try:
                    if i < len(self.layout) and j < len(self.layout[i]):
                        abbr = self.layout[i][j]
                    else:
                        abbr = 'O'
                except:
                    abbr = 'O'
                
                # Validate the abbreviation
                if abbr not in ABBREVS:
                    abbr = 'O'
                
                row.append(abbr)
            result.append(row)
        
        return result

    def _export_scad(self):
        out_path = filedialog.asksaveasfilename(defaultextension='.scad', filetypes=[('OpenSCAD Script', '*.scad')], title='Save SCAD script as')
        if not out_path:
            return

        layout = self._gather_layout()
        script = build_layout_scad_script(layout)

        scad_content = load_scad_text()
        layout_comments = ''
        try:
            start_marker = '// layout info'
            end_marker = '// end layout info'
            start_index = scad_content.find(start_marker)
            if start_index != -1:
                end_index = scad_content.find(end_marker, start_index)
                if end_index != -1:
                    end_index = scad_content.find('\n', end_index)
                    layout_comments = scad_content[start_index:end_index + 1]
        except Exception:
            pass 

        final_script = layout_comments + "\n\n" + script
        
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(final_script)
            self._log('Exported', out_path)
            messagebox.showinfo('Done', f'Exported {out_path}')
        except Exception as ex:
            messagebox.showerror('Error', f'Failed to save SCAD file: {ex}')

    def _export_stl(self):
        out_path = filedialog.asksaveasfilename(defaultextension='.stl', filetypes=[('STL', '*.stl')], title='Save STL as')
        if not out_path:
            return

        layout = self._gather_layout()
        script = build_layout_scad_script(layout)
        
        cmd = EXPORT_CMD_TEMPLATE.format(openscad=OPENSCAD_CMD, out=out_path)
        self._log('Running OpenSCAD with mb_tile() script')
        self._log('Script:', script.replace('\n', ' '))
        self._log('Command:', cmd)
        
        try:
            proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            out, _ = proc.communicate(input=script)
            self._log(out)
            if proc.returncode == 0:
                self._log('Exported', out_path)
                messagebox.showinfo('Done', f'Exported {out_path}')
            else:
                messagebox.showerror('OpenSCAD failed', f'Exit {proc.returncode}\nSee log for details')
        except Exception as ex:
            messagebox.showerror('Error', f'Failed to run OpenSCAD: {ex}')


if __name__ == '__main__':
    app = LayoutEditor()
    app.mainloop()
