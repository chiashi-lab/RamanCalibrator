import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from tkinterdnd2 import TkinterDnD, DND_FILES
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.backend_bases
from matplotlib import rcParams, patches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
from CalibrationManager import CalibrationManager
from RenishawCalibrator import RenishawCalibrator
from Raman488Calibrator import Raman488Calibrator, Raman488DataProcessor
from MapManager import MapManager
from MyTooltip import MyTooltip
from utils import is_num

font_lg = ('Arial', 24)
font_md = ('Arial', 16)
font_sm = ('Arial', 12)

rcParams['keymap.back'].remove('left')
rcParams['keymap.forward'].remove('right')
plt.rcParams['xtick.labelsize'] = 25
plt.rcParams['ytick.labelsize'] = 25

plt.rcParams['figure.subplot.top'] = 0.95
plt.rcParams['figure.subplot.bottom'] = 0.05
plt.rcParams['figure.subplot.left'] = 0.05
plt.rcParams['figure.subplot.right'] = 0.95


def parse_dnd_files(event) -> [Path]:
    if event.data[0] == '{':  # {}で区切られていることがある
        filenames = event.data.split('} {')
        filenames = list(map(lambda x: x.strip('{}'), filenames))
    else:
        filenames = event.data.split()[0]
    return list(map(Path, filenames))


def check_map_loaded(func):
    # マッピングデータが読み込まれているか確認するデコレータ
    # 読み込まれていない場合，エラーメッセージを表示する
    def wrapper(*args, **kwargs):
        if not args[0].map_manager.is_loaded:
            messagebox.showerror('Error', 'Choose map data.')
            return
        return func(*args, **kwargs)

    return wrapper


def check_ref_loaded(func):
    # リファレンスデータが読み込まれているか確認するデコレータ
    # 読み込まれていない場合，エラーメッセージを表示する
    def wrapper(*args, **kwargs):
        if not args[0].calibrator.is_ref_loaded:
            messagebox.showerror('Error', 'Choose reference data.')
            return
        return func(*args, **kwargs)

    return wrapper


class PeakSelector:
    def __init__(self, master) -> None:
        self.master = master
        self.ax = master.ax_ref
        self.toolbar = master.toolbar
        self.x0, self.y0, self.x1, self.y1 = 0, 0, 0, 0
        self.rectangles = []
        self.texts = []
        self.ranges = []
        self.drawing = False
        self.rect_drawing = None
        self.new_window = None
        self.widgets_assign = {}

        self.is_opened = False

        self.master.bind('<Control-Key-z>', self.undo)

    def open_assign_window(self, master):
        if self.new_window is not None and self.new_window.winfo_exists():
            self.new_window.lift()
            return
        self.new_window = tk.Toplevel(master.master)
        self.new_window.title('Assign Peaks')

        self.new_window.protocol('WM_DELETE_WINDOW', self.close_assign_window)

        self.frame_assign = ttk.Frame(self.new_window)
        self.frame_assign.pack(fill=tk.BOTH, expand=True)

        label_description = ttk.Label(self.frame_assign, text='適用したい場合はウィンドウを開いたままにしてください．')
        label_index = ttk.Label(self.frame_assign, text='Index')
        label_x = ttk.Label(self.frame_assign, text='x')
        label_description.grid(row=0, column=0, columnspan=2)
        label_index.grid(row=1, column=0)
        label_x.grid(row=1, column=1)

        self.refresh_assign_window()
        self.is_opened = True

    def close_assign_window(self):
        if self.new_window is not None and self.new_window.winfo_exists():
            self.new_window.destroy()
        self.new_window = None
        self.is_opened = False

    def refresh_assign_window(self, *args):
        # clear
        for w in self.widgets_assign.values():
            for ww in w:
                ww.destroy()
        self.widgets_assign = {}
        # create
        self.master.calibrator.set_material(self.master.material.get())
        x_true = self.master.calibrator.get_true_x()
        auto_x_true = self.assign_peaks_automatically()
        for i, (r, auto) in enumerate(zip(self.ranges, auto_x_true)):
            label_index = ttk.Label(self.frame_assign, text=str(self.ranges.index(r)))
            combobox_x = ttk.Combobox(self.frame_assign, values=list(x_true), justify=tk.CENTER)
            combobox_x.set(auto)
            label_index.grid(row=i + 2, column=0)
            combobox_x.grid(row=i + 2, column=1)
            self.widgets_assign[i] = (label_index, combobox_x)

    def get_range_and_x(self):
        return self.ranges, self.assign_peaks()

    def assign_peaks_automatically(self):
        x_true = self.master.calibrator.get_true_x()
        found_x_true = []
        for x0, y0, x1, y1 in self.ranges:
            x_mid = (x0 + x1) / 2
            diff = np.abs(x_true - x_mid)
            idx = np.argmin(diff)
            found_x_true.append(x_true[idx])
        return found_x_true

    def assign_peaks(self):
        found_x_true = []
        for widgets in self.widgets_assign.values():
            x = widgets[1].get()
            found_x_true.append(float(x))
        return found_x_true

    def on_press(self, event):
        if not self.is_opened:
            return
        if event.inaxes != self.ax:
            return
        if event.button != 1:
            return
        if self.toolbar._buttons['Zoom'].var.get():
            return
        self.x0 = event.xdata
        self.y0 = event.ydata
        self.x1 = event.xdata
        self.y1 = event.ydata
        self.drawing = True

    def on_release(self, event):
        if not self.is_opened:
            return
        if event.xdata is None or event.ydata is None:
            return
        if event.inaxes != self.ax:
            return
        # Toolbarのズーム機能を使っている状態では動作しないようにする
        if self.toolbar._buttons['Zoom'].var.get():
            return

        # プレビュー用の矩形を消す
        if self.rect_drawing is not None:
            self.rect_drawing.remove()
            self.rect_drawing = None

        self.drawing = False

        self.x1 = event.xdata
        self.y1 = event.ydata
        if self.x0 == self.x1 or self.y0 == self.y1:
            return
        if self.is_overlapped(self.x0, self.x1):
            messagebox.showerror('Error', 'Overlapped.')
            return
        x0, x1 = sorted([self.x0, self.x1])
        y0, y1 = sorted([self.y0, self.y1])
        r = patches.Rectangle((x0, y0), x1 - x0, y1 - y0, linewidth=1, edgecolor='r',
                              facecolor='none')
        self.ax.add_patch(r)
        t = self.ax.text(x1, y1, str(len(self.rectangles)), color='r', fontsize=20)
        self.rectangles.append(r)
        self.texts.append(t)
        self.ranges.append((x0, y0, x1, y1))
        self.master.canvas.draw()
        if self.new_window is not None and self.new_window.winfo_exists():
            self.refresh_assign_window()

    def draw_preview(self, event):
        if not self.is_opened:
            return
        if event.xdata is None or event.ydata is None:
            return
        if not self.drawing:
            return
        # Toolbarのズーム機能を使っている状態では動作しないようにする
        if self.toolbar._buttons['Zoom'].var.get():
            return
        if self.rect_drawing is not None:
            self.rect_drawing.remove()
        x1 = event.xdata
        y1 = event.ydata
        self.rect_drawing = patches.Rectangle((self.x0, self.y0), x1 - self.x0, y1 - self.y0, linewidth=0.5,
                                              edgecolor='r', linestyle='dashed', facecolor='none')
        self.ax.add_patch(self.rect_drawing)
        self.master.canvas.draw()

    def is_overlapped(self, x0, x1):
        for x0_, y0_, x1_, y1_ in self.ranges:
            if x0_ <= x0 <= x1_ or x0_ <= x1 <= x1_:
                return True
            if x0 <= x0_ <= x1 or x0 <= x1_ <= x1:
                return True
        return False

    def undo(self, event):
        if len(self.rectangles) == 0:
            return
        self.rectangles[-1].remove()
        self.rectangles.pop()
        self.texts[-1].remove()
        self.texts.pop()
        self.ranges.pop()
        self.master.canvas.draw()

    def draw(self):
        for r, t in zip(self.rectangles, self.texts):
            self.ax.add_patch(r)
            self.ax.add_artist(t)
        self.master.canvas.draw()

    def reset(self):
        for i in range(len(self.rectangles)):
            self.rectangles[i].remove()
            self.texts[i].remove()
        self.rectangles = []
        self.texts = []
        self.ranges = []
        self.close_assign_window()


class MainWindow(tk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.master = master
        self.master.title('Raman Calibrator')

        self.calibrator: CalibrationManager = CalibrationManager()
        self.map_manager: MapManager = MapManager()
        self.processor: Raman488DataProcessor = Raman488DataProcessor()

        self.row = self.col = 0

        self.ax_map: plt.Axes
        self.ax_raw: plt.Axes
        self.ax_ref: plt.Axes

        self.line = None
        self.selection_patches = []

        self.folder_raw = Path('./')
        self.folder_ref = Path('./')
        self.folder_bg = Path('./')

        self.mode = 'Renishaw'  # or 'Raman488'

        self.create_widgets()
        self.map_manager.set_ax(self.ax_map)

    def create_widgets(self) -> None:
        style = ttk.Style()
        style.theme_use('winnative')
        style.configure('TButton', font=font_md, width=12, padding=[0, 4, 0, 4], foreground='black')
        style.configure('R.TButton', font=font_md, width=12, padding=[0, 4, 0, 4], foreground='red')
        style.configure('TLabel', font=font_sm, foreground='black')
        style.configure('TEntry', padding=[0, 4, 0, 4], foreground='black')
        style.configure('TCheckbutton', font=font_md, foreground='black')
        style.configure('TMenubutton', font=font_md, foreground='black')
        style.configure('Treeview', font=font_md, foreground='black')
        style.configure('Treeview.Heading', font=font_md, foreground='black')
        # canvas
        self.width_canvas = 1300
        self.height_canvas = 900
        dpi = 50
        if os.name == 'posix':
            self.width_canvas /= 2
            self.height_canvas /= 2
        fig = plt.figure(figsize=(self.width_canvas / dpi, self.height_canvas / dpi), dpi=dpi)
        self.ax_map = fig.add_subplot(121)
        self.ax_raw = fig.add_subplot(222)
        self.ax_ref = fig.add_subplot(224)
        self.ax_map.set_title('Raman Map', fontsize=30)
        self.ax_raw.set_title('Spectrum', fontsize=30)
        self.ax_ref.set_title('Reference Spectrum', fontsize=30)
        self.canvas = FigureCanvasTkAgg(fig, self.master)
        self.canvas.get_tk_widget().grid(row=0, column=0, rowspan=10)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.master, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=10, column=0)
        # ピークの矩形選択のため

        self.peak_selector = PeakSelector(self)
        fig.canvas.mpl_connect('button_press_event', self.on_press)
        fig.canvas.mpl_connect('motion_notify_event', self.peak_selector.draw_preview)
        fig.canvas.mpl_connect('button_release_event', self.peak_selector.on_release)
        self.canvas.mpl_connect('key_press_event', self.key_pressed)
        self.canvas.mpl_connect('key_press_event', key_press_handler)

        # frames
        frame_data = ttk.LabelFrame(self.master, text='Data')
        frame_calibration = ttk.LabelFrame(self.master, text='Calibration')
        frame_download = ttk.LabelFrame(self.master, text='Download')
        frame_map = ttk.LabelFrame(self.master, text='Map')
        frame_plot = ttk.LabelFrame(self.master, text='Plot')
        frame_data.grid(row=0, column=1)
        frame_calibration.grid(row=1, column=1)
        frame_download.grid(row=2, column=1)
        frame_map.grid(row=3, column=1)
        frame_plot.grid(row=4, column=1)

        # frame_data
        label_raw = ttk.Label(frame_data, text='Raw:')
        label_ref = ttk.Label(frame_data, text='Reference:')
        self.label_bg = ttk.Label(frame_data, text='Background:')
        self.filename_raw = tk.StringVar(value='please drag & drop!')
        self.filename_ref = tk.StringVar(value='please drag & drop!')
        self.filename_bg = tk.StringVar(value='not loaded')
        label_filename_raw = ttk.Label(frame_data, textvariable=self.filename_raw)
        label_filename_ref = ttk.Label(frame_data, textvariable=self.filename_ref)
        self.label_filename_bg = ttk.Label(frame_data, textvariable=self.filename_bg)
        self.tooltip_raw = MyTooltip(label_filename_raw, '')
        self.tooltip_ref = MyTooltip(label_filename_ref, '')
        self.tooltip_bg = MyTooltip(self.label_filename_bg, '')
        self.subtract_bg = tk.BooleanVar(value=False)
        self.checkbox_subtract_bg = ttk.Checkbutton(frame_data, text='Subtract BG', variable=self.subtract_bg, command=self.process, takefocus=False)
        self.remove_cosmic_ray = tk.BooleanVar(value=False)
        self.checkbox_remove_cosmic_ray = ttk.Checkbutton(frame_data, text='Remove Cosmic Ray', variable=self.remove_cosmic_ray, command=self.process, takefocus=False)
        label_raw.grid(row=0, column=0)
        label_ref.grid(row=1, column=0)
        label_filename_raw.grid(row=0, column=1)
        label_filename_ref.grid(row=1, column=1)

        # frame_calibration
        c = CalibrationManager()  # リファレンスデータの選択肢を取得するために一時的にCalibratorを作成
        self.material = tk.StringVar(value=c.get_material_list()[0])
        self.dimension = tk.StringVar(value=c.get_dimension_list()[0])
        self.function = tk.StringVar(value=c.get_function_list()[0])
        optionmenu_material = ttk.OptionMenu(frame_calibration, self.material, self.material.get(), *c.get_material_list(), command=self.peak_selector.refresh_assign_window)
        optionmenu_dimension = ttk.OptionMenu(frame_calibration, self.dimension, self.dimension.get(), *c.get_dimension_list())
        optionmenu_function = ttk.OptionMenu(frame_calibration, self.function, self.function.get(), *c.get_function_list())
        optionmenu_material['menu'].config(font=font_md)
        optionmenu_dimension['menu'].config(font=font_md)
        optionmenu_function['menu'].config(font=font_md)
        self.button_assign_manually = ttk.Button(frame_calibration, text='ASSIGN', command=lambda: self.peak_selector.open_assign_window(self), takefocus=False)
        self.frame_assign = None
        self.button_calibrate = ttk.Button(frame_calibration, text='CALIBRATE', command=self.calibrate, state=tk.DISABLED)
        optionmenu_material.grid(row=0, column=0, columnspan=2)
        optionmenu_dimension.grid(row=1, column=0)
        optionmenu_function.grid(row=1, column=1)
        self.button_calibrate.grid(row=2, column=0, columnspan=2)

        # frame_download
        self.treeview = ttk.Treeview(frame_download, height=6, selectmode=tk.EXTENDED)
        self.treeview['columns'] = ['ix', 'iy']
        self.treeview.column('#0', width=0, stretch=tk.NO)
        self.treeview.column('ix', width=50, anchor=tk.CENTER)
        self.treeview.column('iy', width=50, anchor=tk.CENTER)
        self.treeview.heading('#0', text='')
        self.treeview.heading('ix', text='ix')
        self.treeview.heading('iy', text='iy')
        self.treeview.bind('<<TreeviewSelect>>', self.select_from_treeview)
        self.treeview.bind('<Button-2>', self.delete)
        self.treeview.bind('<Button-3>', self.delete)
        self.button_add = ttk.Button(frame_download, text='ADD', command=self.add, takefocus=False)
        self.button_delete = ttk.Button(frame_download, text='DELETE', command=self.delete, takefocus=False)
        self.button_add_all = ttk.Button(frame_download, text='ADD ALL', command=self.add_all, takefocus=False)
        self.button_delete_all = ttk.Button(frame_download, text='DELETE ALL', command=self.delete_all, takefocus=False)
        self.button_save = ttk.Button(frame_download, text='SAVE', command=self.save, takefocus=False)
        self.show_selection_in_map = tk.BooleanVar(value=True)
        checkbox_show_selection_in_map = ttk.Checkbutton(frame_download, text='Show in Map', variable=self.show_selection_in_map, command=self.update_selection)
        self.treeview.grid(row=0, column=0, columnspan=3)
        self.button_add.grid(row=1, column=0)
        self.button_delete.grid(row=2, column=0)
        self.button_add_all.grid(row=1, column=1)
        self.button_delete_all.grid(row=2, column=1)
        self.button_save.grid(row=1, column=2, rowspan=2, sticky=tk.NS)
        checkbox_show_selection_in_map.grid(row=3, column=0, columnspan=3)

        # frame_map
        vmr1 = (self.register(self.validate_map_range_1), '%P')
        vmr2 = (self.register(self.validate_map_range_2), '%P')
        vcmr1 = (self.register(self.validate_cmap_range_1), '%P')
        vcmr2 = (self.register(self.validate_cmap_range_2), '%P')
        va = (self.register(self.validate_alpha), '%P')
        label_map_range = ttk.Label(frame_map, text='Map Range')
        self.map_range = tk.StringVar(value='1570~1610')
        self.optionmenu_map_range = ttk.OptionMenu(frame_map, self.map_range, self.map_manager.map_range_list[3], *self.map_manager.map_range_list,
                                                   command=self.select_map_range_preset)
        self.optionmenu_map_range.config(state=tk.DISABLED)
        self.optionmenu_map_range['menu'].config(font=font_md)
        self.map_range_1 = tk.DoubleVar(value=1570)
        self.map_range_2 = tk.DoubleVar(value=1610)
        self.entry_map_range_1 = ttk.Entry(frame_map, textvariable=self.map_range_1, validate="key", validatecommand=vmr1, justify=tk.CENTER, font=font_md, width=6)
        self.entry_map_range_2 = ttk.Entry(frame_map, textvariable=self.map_range_2, validate="key", validatecommand=vmr2, justify=tk.CENTER, font=font_md, width=6)
        label_cmap_range = ttk.Label(frame_map, text='Color Range')
        self.cmap_range_1 = tk.DoubleVar(value=0)
        self.cmap_range_2 = tk.DoubleVar(value=10000)
        self.entry_cmap_range_1 = ttk.Entry(frame_map, textvariable=self.cmap_range_1, validate="key", validatecommand=vcmr1, justify=tk.CENTER, font=font_md, width=6)
        self.entry_cmap_range_2 = ttk.Entry(frame_map, textvariable=self.cmap_range_2, validate="key", validatecommand=vcmr2, justify=tk.CENTER, font=font_md, width=6)
        self.map_color = tk.StringVar(value='hot')
        label_map_color = ttk.Label(frame_map, text='Color Map')
        self.optionmenu_map_color = ttk.OptionMenu(frame_map, self.map_color, self.map_color.get(),
                                           *sorted(['viridis', 'plasma', 'inferno', 'magma', 'cividis',
                                                    'Wistia', 'hot', 'binary', 'bone', 'cool', 'copper',
                                                    'gray', 'pink', 'spring', 'summer', 'autumn', 'winter',
                                                    'RdBu', 'Spectral', 'bwr', 'coolwarm', 'hsv', 'twilight',
                                                    'CMRmap', 'cubehelix', 'brg', 'gist_rainbow', 'rainbow',
                                                    'jet', 'nipy_spectral', 'gist_ncar']),
                                                   command=self.on_change_cmap_settings)
        self.optionmenu_map_color.config(state=tk.DISABLED)
        self.optionmenu_map_color['menu'].config(font=font_md)
        label_alpha = ttk.Label(frame_map, text='Alpha')
        self.alpha = tk.DoubleVar(value=1)
        entry_alpha = ttk.Entry(frame_map, textvariable=self.alpha, validate='key', validatecommand=va, justify=tk.CENTER, font=font_md, width=6)
        self.map_autoscale = tk.BooleanVar(value=True)
        checkbox_map_autoscale = ttk.Checkbutton(frame_map, text='Color Map Auto Scale', command=self.on_change_cmap_settings, variable=self.map_autoscale, takefocus=False)
        self.show_crosshair = tk.BooleanVar(value=True)
        checkbox_show_crosshair = ttk.Checkbutton(frame_map, text='Show Crosshair', command=self.update_crosshair, variable=self.show_crosshair, takefocus=False)

        label_map_range.grid(row=0, column=0, rowspan=2)
        self.optionmenu_map_range.grid(row=0, column=1, columnspan=2, sticky=tk.EW)
        self.entry_map_range_1.grid(row=1, column=1)
        self.entry_map_range_2.grid(row=1, column=2)
        label_cmap_range.grid(row=2, column=0)
        self.entry_cmap_range_1.grid(row=2, column=1)
        self.entry_cmap_range_2.grid(row=2, column=2)
        label_map_color.grid(row=3, column=0)
        self.optionmenu_map_color.grid(row=3, column=1, columnspan=2, sticky=tk.EW)
        label_alpha.grid(row=4, column=0)
        entry_alpha.grid(row=4, column=1)
        checkbox_map_autoscale.grid(row=5, column=0, columnspan=4)
        checkbox_show_crosshair.grid(row=6, column=0, columnspan=4)

        # frame_plot
        self.spec_autoscale = tk.BooleanVar(value=True)
        checkbox_spec_autoscale = ttk.Checkbutton(frame_plot, text='Spectrum Auto Scale', variable=self.spec_autoscale, takefocus=False)
        checkbox_spec_autoscale.grid(row=0, column=0)

        # canvas_drop
        self.canvas_drop_Renishaw = tk.Canvas(self.master, width=self.width_canvas, height=self.height_canvas)
        self.canvas_drop_Renishaw.create_rectangle(0, 0, self.width_canvas, self.height_canvas / 2, fill='lightgray')
        self.canvas_drop_Renishaw.create_rectangle(0, self.height_canvas / 2, self.width_canvas, self.height_canvas, fill='gray')
        self.canvas_drop_Renishaw.create_text(self.width_canvas / 2, self.height_canvas / 4, text='① File to calibrate',
                                              font=('Arial', 30))
        self.canvas_drop_Renishaw.create_text(self.width_canvas / 2, self.height_canvas * 3 / 4, text='② Reference file',
                                              font=('Arial', 30))
        self.canvas_drop_Raman488 = tk.Canvas(self.master, width=self.width_canvas, height=self.height_canvas)
        self.canvas_drop_Raman488.create_rectangle(0, 0, self.width_canvas, self.height_canvas / 3, fill='lightgray')
        self.canvas_drop_Raman488.create_rectangle(0, self.height_canvas / 3, self.width_canvas, self.height_canvas * 2 / 3, fill='gray')
        self.canvas_drop_Raman488.create_rectangle(0, self.height_canvas * 2 / 3, self.width_canvas, self.height_canvas, fill='lightgray')
        self.canvas_drop_Raman488.create_text(self.width_canvas / 2, self.height_canvas / 6, text='① File to calibrate',
                                              font=('Arial', 30))
        self.canvas_drop_Raman488.create_text(self.width_canvas / 2, self.height_canvas / 2, text='② Reference file',
                                              font=('Arial', 30))
        self.canvas_drop_Raman488.create_text(self.width_canvas / 2, self.height_canvas * 5 / 6, text='③ Background file',
                                              font=('Arial', 30))

    # 入力のバリデーションの関数，煩雑なのでどうにかしたさある
    def validate_map_range_1(self, after):
        if not self.map_manager.is_loaded:
            return False
        if is_num(after):
            if float(after) < self.map_range_2.get():
                cmap_range = self.map_manager.update_map(map_range=(float(after), self.map_range_2.get()))
                self.cmap_range_1.set(round(cmap_range[0]))
                self.cmap_range_2.set(round(cmap_range[1]))
                self.canvas.draw()
            return True
        elif after == '':
            return True
        else:
            return False

    def validate_map_range_2(self, after):
        if not self.map_manager.is_loaded:
            return False
        if is_num(after):
            if self.map_range_1.get() < float(after):
                cmap_range = self.map_manager.update_map(map_range=(self.map_range_1.get(), float(after)))
                self.cmap_range_1.set(round(cmap_range[0]))
                self.cmap_range_2.set(round(cmap_range[1]))
                self.canvas.draw()
            return True
        elif after == '':
            return True
        else:
            return False

    def validate_cmap_range_1(self, after):
        if not self.map_manager.is_loaded:
            return False
        if is_num(after):
            if float(after) < self.cmap_range_2.get():
                self.map_manager.update_map(cmap_range=(float(after), self.cmap_range_2.get()))
                self.canvas.draw()
            return True
        elif after == '':
            return True
        else:
            return False

    def validate_cmap_range_2(self, after):
        if not self.map_manager.is_loaded:
            return False
        if is_num(after):
            if self.cmap_range_1.get() < float(after):
                self.map_manager.update_map((self.cmap_range_1.get(), float(after)))
                self.canvas.draw()
            return True
        elif after == '':
            return True
        else:
            return False

    def validate_alpha(self, after):
        if not self.map_manager.is_loaded:
            return False
        if is_num(after) and 0 <= float(after) <= 1:
            self.map_manager.update_map(alpha=float(after))
            self.canvas.draw()
            return True
        elif after == '':
            return True
        else:
            return False

    @check_map_loaded
    @check_ref_loaded
    def calibrate(self) -> None:
        self.calibrator.set_dimension(int(self.dimension.get()[0]))
        self.calibrator.set_material(self.material.get())
        self.calibrator.set_function(self.function.get())
        self.calibrator.reset_data()
        if self.peak_selector.is_opened:  # ピーク選択ウィンドウが開いているときは手動でアサインしたものを採用
            ranges, x_true = self.peak_selector.get_range_and_x()
            ok = self.calibrator.calibrate(mode='manual', ranges=ranges, x_true=x_true)
        else:
            ok = self.calibrator.calibrate()
        if not ok:
            messagebox.showerror('Error', 'Calibration failed.')
            return
        self.button_calibrate.config(state=tk.DISABLED)
        self.show_ref()
        self.map_manager.update_xdata(self.calibrator.xdata)
        self.update_plot()
        self.canvas.draw()

    @check_map_loaded
    def on_press(self, event: matplotlib.backend_bases.MouseEvent) -> None:
        # クリックした点のスペクトルを表示する
        if event.xdata is None or event.ydata is None:
            return
        if event.inaxes == self.ax_map:
            # ズームモード，移動モードのときは動作しないようにする
            if self.toolbar._buttons['Zoom'].var.get() or self.toolbar._buttons['Pan'].var.get():
                return
            self.map_manager.on_click(event.xdata, event.ydata)
            self.update_plot()
        elif event.inaxes == self.ax_ref:  # ピークの矩形選択のため
            self.peak_selector.on_press(event)

    @check_map_loaded
    def key_pressed(self, event: matplotlib.backend_bases.KeyEvent) -> None:
        self.map_manager.on_key_press(event.key)
        self.update_plot()

    @check_map_loaded
    def select_map_range_preset(self, *args) -> None:
        x1, x2 = map(int, self.map_range.get().split('~'))
        self.map_range_1.set(x1)
        self.map_range_2.set(x2)
        self.map_manager.update_map(map_range=(x1, x2))
        self.canvas.draw()

    @check_map_loaded
    def on_change_map_range(self, *args) -> None:
        self.map_manager.update_map(map_range=(self.map_range_1.get(), self.map_range_2.get()))
        self.canvas.draw()

    @check_map_loaded
    def on_change_cmap_settings(self, *args) -> None:
        if self.map_autoscale.get():
            self.entry_cmap_range_1.config(state=tk.DISABLED)
            self.entry_cmap_range_2.config(state=tk.DISABLED)
        else:
            self.entry_cmap_range_1.config(state=tk.NORMAL)
            self.entry_cmap_range_2.config(state=tk.NORMAL)
        cmap_range = self.map_manager.update_map(
            cmap=self.map_color.get(),
            cmap_range=(self.cmap_range_1.get(), self.cmap_range_2.get()),
            cmap_range_auto=self.map_autoscale.get(),
            alpha=self.alpha.get())
        # カラーマップの範囲を更新
        self.cmap_range_1.set(round(cmap_range[0]))
        self.cmap_range_2.set(round(cmap_range[1]))
        self.canvas.draw()

    @check_ref_loaded
    def show_ref(self, *args) -> None:
        self.calibrator.set_material(self.material.get())
        self.calibrator.plot()
        # 矩形選択したピークを描画
        self.peak_selector.draw()
        self.canvas.draw()

    @check_map_loaded
    def update_crosshair(self) -> None:
        # マッピング上のクロスヘアを移動
        self.map_manager.show_crosshair = self.show_crosshair.get()
        self.map_manager.update_crosshair()
        self.canvas.draw()

    @check_map_loaded
    def update_plot(self) -> None:
        if self.line is None:
            self.ax_raw.autoscale(True)
        elif self.spec_autoscale.get():
            self.ax_raw.autoscale(True)
            self.line[0].remove()
            self.ax_raw.cla()
            self.ax_raw.set_title('Spectrum', fontsize=30)
        else:
            self.ax_raw.autoscale(False)
            self.line[0].remove()
        iy, ix = self.map_manager.row, self.map_manager.col
        self.line = self.ax_raw.plot(
            *self.map_manager.get_spectrum(),
            label=f'({ix}, {iy})', color='r', linewidth=0.8)
        self.ax_raw.legend(fontsize=18)
        self.canvas.draw()

    @check_map_loaded
    def update_selection(self):
        for r in self.selection_patches:
            r.remove()
        self.selection_patches = []
        for child in self.treeview.get_children():
            col, row = self.treeview.item(child)['values']
            xc, yc = self.map_manager.idx2coord(row, col)  # center of the pixel
            xp, yp = self.map_manager.map_info.map_pixel  # pixel size
            x0 = xc - xp / 2
            y0 = yc - yp / 2
            r = patches.Rectangle((x0, y0), xp, yp, fill=False, edgecolor='white', lw=1)
            self.ax_map.add_patch(r)
            self.selection_patches.append(r)

        if not self.show_selection_in_map.get():
            for r in self.selection_patches:
                r.set_visible(False)
        else:
            for r in self.selection_patches:
                r.set_visible(True)
        self.canvas.draw()

    def select_from_treeview(self, *args):
        if self.treeview.focus() == '':
            return
        self.row, self.col = self.treeview.item(self.treeview.focus())['values'][::-1]
        self.update_crosshair()
        self.update_plot()

    def drop(self, event) -> None:
        # ドラッグ&ドロップされたファイルを処理
        # 誘導用の長方形を見えないように
        self.canvas_drop_Renishaw.place_forget()
        self.canvas_drop_Raman488.place_forget()

        # 複数個選択しても1個しか読み込まない
        paths = parse_dnd_files(event)
        filepath = paths[0]

        # どこにdropしたかでマッピングファイルなのか、標準サンプルファイルなのか仕分ける
        master_geometry = list(map(int, self.master.winfo_geometry().split('+')[1:]))
        dropped_place = (event.y_root - master_geometry[1] - 30) / self.height_canvas

        if os.name == 'posix':
            threshold = 1
        else:
            threshold = 0.5

        if self.mode == 'Renishaw':
            if dropped_place < threshold:
                self.load_raw(filepath)
            else:
                self.load_ref(filepath)
        elif self.mode == 'Raman488':
            if dropped_place < threshold * 2 / 3:
                self.load_raw(filepath)
            elif dropped_place < threshold * 4 / 3:
                self.load_ref(filepath)
            else:
                self.load_bg(filepath)

    def load_raw(self, filepath: Path) -> None:
        self.reset()

        if filepath.suffix == '.wdf':
            self.calibrator = RenishawCalibrator()
            self.mode = 'Renishaw'
            self.forget_Raman488_widgets()
            self.peak_selector.close_assign_window()
        elif filepath.suffix == '.hdf5':
            self.mode = 'Raman488'
            self.calibrator = Raman488Calibrator()
            self.remember_Raman488_widgets()
        else:
            messagebox.showerror('Error', 'Only .wdf or .hdf5 files are acceptable.')
            return

        self.calibrator.set_ax(self.ax_ref)
        ok, map_info = self.calibrator.load_raw(filepath)
        if not ok:
            messagebox.showerror('Error', 'Choose map data.')
            return
        self.map_manager.load(map_info)

        if self.mode == 'Raman488':
            self.processor = Raman488DataProcessor(map_info=map_info)

        self.filename_raw.set(filepath.name)
        self.folder_raw = filepath.parent
        self.optionmenu_map_range.config(state=tk.ACTIVE)
        self.optionmenu_map_color.config(state=tk.ACTIVE)
        self.map_manager.clear_and_show()
        self.on_change_cmap_settings()
        self.update_plot()
        self.tooltip_raw.set(filepath)

    def load_ref(self, filepath: Path) -> None:
        if self.calibrator.reader_raw is None:
            messagebox.showerror('Error', 'Choose map data first.')
            return

        # ファイル形式を確認
        if self.mode == 'Renishaw':
            if filepath.suffix != '.wdf':
                messagebox.showerror('Error', 'Only .wdf files are acceptable.')
                return
        elif self.mode == 'Raman488':
            if filepath.suffix != '.hdf5':
                messagebox.showerror('Error', 'Only .hdf5 files are acceptable.')
                return

        self.calibrator.reset_ref()
        has_same_xdata = self.calibrator.load_ref(filepath)
        if not has_same_xdata:
            messagebox.showerror('Error',
                                 'X-axis data does not match. Choose reference data with same measurement condition as the map data.')
            return
        self.filename_ref.set(filepath.name)
        self.folder_ref = filepath.parent
        for material in self.calibrator.get_material_list():
            if material in filepath.name:
                self.material.set(material)
        self.button_calibrate.config(state=tk.ACTIVE)

        self.peak_selector.reset()

        self.show_ref()
        self.tooltip_ref.set(filepath)

    def load_bg(self, filepath: Path) -> None:
        self.filename_bg.set(filepath.name)
        self.folder_bg = filepath.parent
        self.tooltip_bg.set(filepath)
        self.processor.load_bg(filepath)
        self.subtract_bg.set(True)
        self.process()

    def drop_enter(self, event: TkinterDnD.DnDEvent) -> None:
        if self.mode == 'Renishaw':
            self.canvas_drop_Renishaw.place(anchor='nw', x=0, y=0)
        elif self.mode == 'Raman488':
            self.canvas_drop_Raman488.place(anchor='nw', x=0, y=0)

    def drop_leave(self, event: TkinterDnD.DnDEvent) -> None:
        self.canvas_drop_Renishaw.place_forget()
        self.canvas_drop_Raman488.place_forget()

    def forget_Raman488_widgets(self) -> None:
        self.checkbox_subtract_bg.grid_forget()
        self.label_bg.grid_forget()
        self.label_filename_bg.grid_forget()
        self.checkbox_remove_cosmic_ray.grid_forget()
        self.button_assign_manually.grid_forget()

    def remember_Raman488_widgets(self) -> None:
        self.label_bg.grid(row=2, column=0)
        self.label_filename_bg.grid(row=2, column=1)
        self.checkbox_subtract_bg.grid(row=3, column=0, columnspan=2)
        self.checkbox_remove_cosmic_ray.grid(row=4, column=0, columnspan=2)
        self.button_assign_manually.grid(row=1, column=0)

    def process(self) -> None:
        # バックグラウンド，宇宙線除去
        if self.subtract_bg.get() and self.processor.bg_data is None:
            messagebox.showerror('Error', 'Choose background data.')
            self.subtract_bg.set(False)
            return
        self.processor.set_processed_data(is_bg_subtracted=self.subtract_bg.get(), is_cosmic_ray_removed=self.remove_cosmic_ray.get())
        self.update_plot()
        self.canvas.draw()

    def reset(self) -> None:
        self.calibrator.close()
        self.calibrator.reset()
        self.calibrator = CalibrationManager()
        self.processor.reset()
        self.map_manager.reset()
        self.map_manager.map_range = (self.map_range_1.get(), self.map_range_2.get())
        self.filename_raw.set('please drag & drop!')
        self.filename_ref.set('please drag & drop!')
        self.filename_bg.set('not loaded')
        self.folder_raw = Path('./')
        self.folder_ref = Path('./')
        self.folder_bg = Path('./')
        self.forget_Raman488_widgets()
        self.button_calibrate.config(state=tk.DISABLED)
        self.row = 0
        self.col = 0

        self.treeview.delete(*self.treeview.get_children())

    @check_map_loaded
    def add(self) -> None:
        # 保存リストに追加する
        index = (self.map_manager.col, self.map_manager.row)  # (x, y)

        # 既に追加されている場合は追加しない
        for child in self.treeview.get_children():
            if self.treeview.item(child)['values'] == list(index):
                return
        self.treeview.insert('', tk.END, text='', values=index)
        self.treeview.yview_moveto(1)
        self.update_selection()

    @check_map_loaded
    def add_all(self) -> None:
        # 全ての点を保存リストに追加
        all_indices = [[idx2, idx1] for idx2 in range(self.map_manager.map_info.shape[1]) for idx1 in
                       range(self.map_manager.map_info.shape[0])]
        self.treeview.delete(*self.treeview.get_children())
        for index in all_indices:
            self.treeview.insert('', tk.END, text='', values=index)
        self.update_selection()

    @check_map_loaded
    def delete(self, event=None) -> None:
        # 保存リストから削除
        # 右クリックから呼ばれた場合、ダイアログを表示
        if event is not None:
            if not messagebox.askyesno('Confirmation', 'Delete these?'):
                return

        idx_to_delete = [self.treeview.item(iid)['values'] for iid in self.treeview.selection()]
        # 何も選択されていない場合、現在の点を削除
        if len(idx_to_delete) == 0:
            idx_to_delete = [(self.col, self.row)]

        for child in self.treeview.get_children():
            if self.treeview.item(child)['values'] in idx_to_delete:
                self.treeview.delete(child)

        self.update_selection()

    @check_map_loaded
    def delete_all(self) -> None:
        # 保存リストから全て削除
        if not messagebox.askyesno('Confirmation', 'Delete all?'):
            return
        self.treeview.delete(*self.treeview.get_children())
        self.update_selection()

    def construct_filename(self, ix: int, iy: int) -> str:
        filepath = Path(self.filename_raw.get())
        ny, nx = self.map_manager.map_info.shape
        # 0埋め
        ix = str(ix).zfill(len(str(nx)))
        iy = str(iy).zfill(len(str(ny)))
        return filepath.with_name(f'{filepath.stem}_{ix}_{iy}.txt').name

    def save(self) -> None:
        # 保存リスト内のファイルを保存
        if not self.treeview.get_children():
            return

        # フォルダを選択
        # ファイル名はスペクトルのインデックスになる
        folder_to_save = filedialog.askdirectory(initialdir=self.folder_raw)
        if not folder_to_save:
            return
        folder_to_save = Path(folder_to_save)

        xdata = self.map_manager.map_info.xdata
        for child in self.treeview.get_children():
            col, row = self.treeview.item(child)['values']
            spectrum = self.map_manager.map_info.map_data[row][col]
            abs_path_raw = self.folder_raw / self.filename_raw.get()
            if self.calibrator.is_calibrated:
                abs_path_ref = self.folder_ref / self.filename_ref.get()
            else:
                abs_path_ref = ''
            if self.subtract_bg.get():
                abs_path_bg = self.folder_bg / self.filename_bg.get()
            else:
                abs_path_bg = ''
            filepath = folder_to_save / self.construct_filename(ix=col, iy=row)
            if filepath.exists():
                if not messagebox.askyesno('Confirmation', f'{filepath.name} already exists. Overwrite?'):
                    continue
            with filepath.open('w') as f:
                f.write(f'# abs_path_raw: {abs_path_raw}\n')
                f.write(f'# abs_path_ref: {abs_path_ref}\n')
                if self.mode == 'Raman488':
                    f.write(f'# abs_path_bg: {abs_path_bg}\n')
                    f.write(f'# cosmic_ray_removed: {"Yes" if self.remove_cosmic_ray.get() else "No"}\n')
                f.write(f'# calibration: {self.calibrator.calibration_info}\n\n')

                for x, y in zip(xdata, spectrum):
                    f.write(f'{x},{y}\n')

    def quit(self) -> None:
        self.calibrator.close()
        self.master.quit()
        self.master.destroy()


def main():
    root = TkinterDnD.Tk()
    app = MainWindow(master=root)
    root.protocol('WM_DELETE_WINDOW', app.quit)
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<DropEnter>>', app.drop_enter)
    root.dnd_bind('<<DropLeave>>', app.drop_leave)
    root.dnd_bind('<<Drop>>', app.drop)
    app.mainloop()


if __name__ == '__main__':
    main()
