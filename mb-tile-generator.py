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
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# --- Configuration ---
DEFAULT_ROWS = 9
DEFAULT_COLS = 9

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SCAD_PATH = os.path.join(WORKSPACE_DIR, "multiboard-tile.scad")
OPENSCAD_CMD = "/Applications/OpenScad.app/Contents/MacOS/OpenSCAD"
EXPORT_CMD_TEMPLATE = '"{openscad}" /dev/stdin --export-format binstl -o "{out}"'

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
        row_items = ", ".join(f'{abbr}' for abbr in row)
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

        # Always start with a default 8x8 layout with borders
        # self.layout = create_default_layout(8, 8)
        self.layout = []
        self.rows = tk.IntVar(value=DEFAULT_ROWS)
        self.cols = tk.IntVar(value=DEFAULT_COLS)

        self._vars = []  # matrix of StringVar for dropdowns

        # track last-clicked cell (for preset buttons)
        self._last_clicked = None

        

        self._build_ui()
        
        self._apply_preset_to_all(self._preset_patterns['ALL'])
        self._populate_grid()


        

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

        # Icon-style buttons: refresh icon for resize, square icon for presets
        # Keep behavior the same but use compact glyphs so the UI is icon-based.
        ttk.Button(frm_top, text='↻', command=self._on_shape_change).pack(side='left', padx=(0, 12))
        # Presets dropdown button (opens a popup with preset icons)
        ttk.Button(frm_top, text='▢', command=self._open_presets_popup).pack(side='left', padx=(0, 12))
        # Export icon button: use a document + arrow glyph; behavior unchanged
        ttk.Button(frm_top, text='→ stl', command=self._export_stl).pack(side='left', padx=6)
        ttk.Button(frm_top, text='→ scad', command=self._export_scad).pack(side='left', padx=6)

        # preset patterns for different border configurations
        self._preset_patterns = {
            # top row
            'LTR': {'top':True, 'left':True, 'right':True, 'bottom':False},
            'LT':  {'top':True, 'left':True, 'right':False, 'bottom':False},
            'T':   {'top':True, 'left':False, 'right':False, 'bottom':False},
            'TR':  {'top':True, 'right':True, 'left':False, 'bottom':False},
            # second row
            'LR':  {'left':True, 'right':True, 'top':False, 'bottom':False},
            'L':   {'left':True, 'top':False, 'right':False, 'bottom':False},
            'NONE':{'top':False,'bottom':False,'left':False,'right':False},
            'R':   {'right':True,'top':False,'left':False,'bottom':False},
            # third row
            'LBR': {'left':True,'bottom':True,'right':True,'top':False},
            'LB':  {'left':True,'bottom':True,'top':False,'right':False},
            'B':   {'bottom':True,'top':False,'left':False,'right':False},
            'BR':  {'bottom':True,'right':True,'top':False,'left':False},
            # fourth row
            'ALL': {'top':True,'bottom':True,'left':True,'right':True},
            'LTB': {'left':True,'top':True,'bottom':True,'right':False},
            'BT':  {'top':True,'bottom':True,'left':False,'right':False},
            'TRB': {'top':True,'right':True,'bottom':True,'left':False},
        }

        # horizontal rule below menu
        self._menu_sep = ttk.Separator(self, orient='horizontal')
        self._menu_sep.pack(fill='x', padx=8, pady=6)

        # center frame for grid
        self.canvas = tk.Canvas(self)
        self.canvas.pack(fill='both', expand=True, padx=8, pady=8)

        self.grid_frame = ttk.Frame(self.canvas)
        # create window and keep a reference for centering
        # use 'nw' anchor so x = (canvas_width - grid_width)//2 becomes the left margin,
        # which centers the grid horizontally when we set the window x coordinate.
        self._grid_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor='nw')
        # reposition the grid window to center on canvas resize
        self.canvas.bind('<Configure>', self._on_canvas_config)

        # bottom log
        self.log = tk.Text(self, height=8)
        self.log.pack(fill='x', padx=8, pady=(0, 8))
        self._log('Started with default layout with borders')

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

        # apply preset abbreviation to every cell in the current grid
        r = self.rows.get()
        c = self.cols.get()
        for i in range(r):
            for j in range(c):
                # ensure layout is big enough
                while len(self.layout) <= i:
                    self.layout.append(['O'] * c)
                while len(self.layout[i]) <= j:
                    self.layout[i].append('O')

                # determine value for this cell
                # inner cells -> NORMAL ('O')
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
                    # corners first
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
                # left click records last-click and opens palette
                cv.bind('<Button-1>', lambda e, ii=i, jj=j: (self._on_cell_click(ii, jj), self._open_palette(ii, jj)))
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

    def _on_cell_click(self, i, j):
        try:
            self._last_clicked = (i, j)
            self._log(f'Selected cell {i},{j}')
        except Exception:
            pass

    # ...existing code...

    def _cycle_cell(self, i, j):
        # move to next abbreviation in ABBREVS
        cur = self.layout[i][j]
        try:
            idx = ABBREVS.index(cur)
        except ValueError:
            idx = 0
        nxt = ABBREVS[(idx + 1) % len(ABBREVS)]
        self.layout[i][j] = nxt
        # update menubutton image
        try:
            btn = self._canvases[i][j]
            btn.config(image=self._images[nxt])
        except Exception:
            # fallback: nothing
            pass

    def _open_palette(self, i, j):
        # Create the palette hidden to avoid flashing at the default location,
        # build it, compute a centered position, then show it.
        top = tk.Toplevel(self)
        top.withdraw()
        top.title('Select style')
        top.transient(self)
        top.resizable(False, False)
        # ordered grid of icons: directional layout in a 4x3 grid
        ordered = [
            'TL', 'T', 'TR',
            'L',  'O', 'R', 
            'BL', 'B', 'BR',
            'LR', 'X', 'TB'
        ]
        cols = 3
        rows = 4
        
        for idx, abbr in enumerate(ordered):
            r = idx // cols
            c = idx % cols
            cv = tk.Canvas(top, width=48, height=48, highlightthickness=1, relief='ridge')
            cv.grid(row=r, column=c, padx=4, pady=4)
            self._draw_icon_on_canvas(cv, abbr)
            cv.bind('<Button-1>', lambda e, a=abbr: (self._set_palette_choice(top, i, j, a)))

        # compute the popup preferred size, then position it so that it is
        # horizontally centered on the clicked cell and its top is aligned
        # with the bottom of the clicked cell. If that placement would put
        # the popup off-screen, move it left/up to fit (prefer placing above
        # the cell if there's no room below).
        top.update_idletasks()
        top_w = top.winfo_reqwidth()
        top_h = top.winfo_reqheight()

        # get clicked cell geometry on screen
        try:
            cell_widget = self._canvases[i][j]
            cell_widget.update_idletasks()
            cell_x = cell_widget.winfo_rootx()
            cell_y = cell_widget.winfo_rooty()
            cell_w = cell_widget.winfo_width()
            cell_h = cell_widget.winfo_height()
        except Exception:
            # fallback: center on main window
            main_x = self.winfo_rootx(); main_y = self.winfo_rooty()
            main_w = self.winfo_width(); main_h = self.winfo_height()
            pos_x = main_x + max(0, (main_w // 2) - (top_w // 2))
            pos_y = main_y + max(0, (main_h // 2) - (top_h // 2))
            top.geometry(f"{top_w}x{top_h}+{pos_x}+{pos_y}")
            top.deiconify(); top.grab_set(); top.focus_force()
            return

        # ideal placement: horizontally center on the cell, and place the
        # popup top at the bottom of the cell
        ideal_x = cell_x + (cell_w // 2) - (top_w // 2)
        ideal_y = cell_y + cell_h

        # clamp to screen; if there's not enough room below, prefer placing
        # the popup above the cell; ensure we don't go off the left/top edges
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        margin = 8

        pos_x = ideal_x
        pos_y = ideal_y

        # move left if overflowing right edge
        if pos_x + top_w > screen_w - margin:
            pos_x = screen_w - top_w - margin
        if pos_x < margin:
            pos_x = margin

        # if bottom would overflow screen, try placing above the cell
        if pos_y + top_h > screen_h - margin:
            above_y = cell_y - top_h
            if above_y >= margin:
                pos_y = above_y
            else:
                # clamp to bottom-most position that fits
                pos_y = max(margin, screen_h - top_h - margin)

        if pos_y < margin:
            pos_y = margin

        top.geometry(f"{top_w}x{top_h}+{pos_x}+{pos_y}")
        top.deiconify(); top.grab_set(); top.focus_force()

    def _open_presets_popup(self):
        # popup that shows preset icons; clicking applies the preset to all cells
        top = tk.Toplevel(self)
        top.withdraw()
        top.title('Presets')
        top.transient(self)
        top.resizable(False, False)

        # Arrange presets in a 4x4 icon-only grid per user's requested layout.
        # Converted abbreviation grid (left-to-right, top-to-bottom):
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
            # get pattern from preset patterns, fallback to no borders if not found
            pattern = self._preset_patterns.get(abbr, {'top':False,'bottom':False,'left':False,'right':False})
            cv = tk.Canvas(top, width=48, height=48, highlightthickness=1, relief='ridge')
            cv.grid(row=r, column=c, padx=4, pady=4)
            # draw the preset icon using same drawing routine
            self._draw_preset_icon(cv, pattern)
            def make_cb(a=abbr, pat=pattern):
                return lambda e: (self._apply_preset_to_all(pat), top.destroy())
            cv.bind('<Button-1>', make_cb())

        # compute size and center horizontally; align top to the menu separator bottom
        top.update_idletasks()
        top_w = top.winfo_reqwidth()
        top_h = top.winfo_reqheight()
        main_x = self.winfo_rootx(); main_w = self.winfo_width()
        # horizontal center
        pos_x = main_x + max(0, (main_w // 2) - (top_w // 2))
        # vertical: place directly below the separator (menu rule)
        try:
            sep = self._menu_sep
            sep.update_idletasks()
            sep_bottom = sep.winfo_rooty() + sep.winfo_height()
            pos_y = sep_bottom
        except Exception:
            # fallback to centered vertically if separator not available
            main_y = self.winfo_rooty(); main_h = self.winfo_height()
            pos_y = main_y + max(0, (main_h // 2) - (top_h // 2))

        top.geometry(f"{top_w}x{top_h}+{pos_x}+{pos_y}")
        top.deiconify(); top.grab_set(); top.focus_force()

    def _set_palette_choice(self, top, i, j, abbr):
        # Set the chosen abbreviation and redraw the canvas cell
        self.layout[i][j] = abbr
        try:
            self._draw_icon_on_canvas(self._canvases[i][j], abbr)
        except Exception:
            pass
        top.destroy()

    def _on_shape_change(self):
        try:
            r = int(self.rows.get())
            c = int(self.cols.get())
        except Exception:
            messagebox.showerror('Invalid', 'Rows and Cols must be integers')
            return
        
        # Create new layout with proper border logic
        #self.layout = create_default_layout(r, c)
        if ( self._last_pattern is not None ):
            self._apply_preset_to_all(self._last_pattern)
        self._populate_grid()

    def _gather_layout(self):
        # Our grid is stored in self.layout as abbreviations already; return a copy
        return [list(row) for row in self.layout]

    def _export_scad(self):
        # prompt for output SCAD path
        out_path = filedialog.asksaveasfilename(defaultextension='.scad', filetypes=[('OpenSCAD Script', '*.scad')], title='Save SCAD script as')
        if not out_path:
            return

        # generate script that calls mb_tile() with current layout
        layout = self._gather_layout()
        script = build_layout_scad_script(layout)

        # extract layout info comments from the main scad file
        scad_content = load_scad_text()
        layout_comments = ''
        try:
            start_marker = '// layout info'
            end_marker = '// end layout info'
            start_index = scad_content.find(start_marker)
            if start_index != -1:
                end_index = scad_content.find(end_marker, start_index)
                if end_index != -1:
                    # also include the end_marker line
                    end_index = scad_content.find('\n', end_index)
                    layout_comments = scad_content[start_index:end_index + 1]
        except Exception:
            pass # ignore if markers are not found or any other error

        final_script = layout_comments + "\n\n" + script
        
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(final_script)
            self._log('Exported', out_path)
            messagebox.showinfo('Done', f'Exported {out_path}')
        except Exception as ex:
            messagebox.showerror('Error', f'Failed to save SCAD file: {ex}')

    def _export_stl(self):
        # prompt for output STL path
        out_path = filedialog.asksaveasfilename(defaultextension='.stl', filetypes=[('STL', '*.stl')], title='Save STL as')
        if not out_path:
            return

        # generate script that calls mb_tile() with current layout
        layout = self._gather_layout()
        script = build_layout_scad_script(layout)
        
        cmd = EXPORT_CMD_TEMPLATE.format(openscad=OPENSCAD_CMD, out=out_path)
        self._log('Running OpenSCAD with mb_tile() script')
        self._log('Script:', script.replace('\n', ' '))
        self._log('Command:', cmd)
        
        try:
            # run the command with script passed via stdin
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