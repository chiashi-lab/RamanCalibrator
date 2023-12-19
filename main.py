import os
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from tkinterdnd2 import TkinterDnD, DND_FILES
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.backend_bases
from matplotlib import rcParams, patches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
from RamanCalibrator import RamanCalibrator
from MyTooltip import MyTooltip

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


def check_loaded(func):
    # マッピングデータが読み込まれているか確認するデコレータ
    # 読み込まれていない場合，エラーメッセージを表示する
    def wrapper(self, *args, **kwargs):
        if self.filename_raw.get() == 'please drag & drop!':
            messagebox.showerror('Error', 'Choose map data.')
            return
        return func(self, *args, **kwargs)

    return wrapper


class MainWindow(tk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.master = master
        self.master.title('Raman Calibrator')
        self.master.bind('<Control-Key-z>', self.undo)

        self.x0, self.y0, self.x1, self.y1 = 0, 0, 0, 0
        self.rectangles = []
        self.texts = []
        self.ranges = []
        self.drawing = False
        self.rect_drawing = None

        self.new_window = None
        self.widgets_assign = {}

        self.showing_ref = False

        self.calibrator = RamanCalibrator()

        self.row = self.col = 0

        self.ax: list[plt.Axes] = []

        self.line = None
        self.selection_patches = []

        self.folder_raw = './'
        self.folder_ref = './'
        self.folder_bg = './'

        self.create_widgets()

    def create_widgets(self) -> None:
        style = ttk.Style()
        style.theme_use('winnative')
        style.configure('TButton', font=font_md, width=14, padding=[0, 4, 0, 4], foreground='black')
        style.configure('R.TButton', font=font_md, width=14, padding=[0, 4, 0, 4], foreground='red')
        style.configure('TLabel', font=font_sm, foreground='black')
        style.configure('TEntry', padding=[0, 4, 0, 4], foreground='black')
        style.configure('TCheckbutton', font=font_md, foreground='black')
        style.configure('TMenubutton', font=font_md, foreground='black')
        style.configure('Treeview', font=font_md, foreground='black')
        style.configure('Treeview.Heading', font=font_md, foreground='black')
        # canvas
        self.width_canvas = 1200
        self.height_canvas = 600
        dpi = 50
        if os.name == 'posix':
            self.width_canvas /= 2
            self.height_canvas /= 2
        fig, self.ax = plt.subplots(1, 2, figsize=(self.width_canvas / dpi, self.height_canvas / dpi), dpi=dpi)
        fig.canvas.mpl_connect('button_press_event', self.on_press)
        fig.canvas.mpl_connect('motion_notify_event', self.draw_preview)
        fig.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas = FigureCanvasTkAgg(fig, self.master)
        self.canvas.get_tk_widget().grid(row=0, column=0, rowspan=3)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.master, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=3, column=0)
        fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.canvas.mpl_connect('key_press_event', self.key_pressed)
        self.canvas.mpl_connect('key_press_event', key_press_handler)

        # frames
        frame_data = ttk.LabelFrame(self.master, text='Data')
        frame_download = ttk.LabelFrame(self.master, text='Download')
        frame_plot = ttk.LabelFrame(self.master, text='Plot')
        frame_data.grid(row=0, column=1)
        frame_download.grid(row=1, column=1)
        frame_plot.grid(row=2, column=1)

        # frame_data
        label_raw = ttk.Label(frame_data, text='Raw:')
        label_ref = ttk.Label(frame_data, text='Reference:')
        label_bg = ttk.Label(frame_data, text='Background:')
        self.filename_raw = tk.StringVar(value='please drag & drop!')
        self.filename_ref = tk.StringVar(value='please drag & drop!')
        self.filename_bg = tk.StringVar(value='please drag & drop!')
        label_filename_raw = ttk.Label(frame_data, textvariable=self.filename_raw)
        label_filename_ref = ttk.Label(frame_data, textvariable=self.filename_ref)
        label_filename_bg = ttk.Label(frame_data, textvariable=self.filename_bg)
        self.tooltip_raw = MyTooltip(label_filename_raw, '')
        self.tooltip_ref = MyTooltip(label_filename_ref, '')
        self.tooltip_bg = MyTooltip(label_filename_bg, '')
        label_ref.bind('<Button-1>', self.show_ref)
        label_filename_ref.bind('<Button-1>', self.show_ref)
        label_bg.bind('<Button-1>', self.show_bg)
        label_filename_bg.bind('<Button-1>', self.show_bg)
        self.material = tk.StringVar(value=self.calibrator.get_material_list()[0])
        self.dimension = tk.StringVar(value=self.calibrator.get_dimension_list()[0])
        self.function = tk.StringVar(value=self.calibrator.get_function_list()[0])
        optionmenu_material = ttk.OptionMenu(frame_data, self.material, self.material.get(), *self.calibrator.get_material_list())
        optionmenu_dimension = ttk.OptionMenu(frame_data, self.dimension, self.dimension.get(), *self.calibrator.get_dimension_list())
        optionmenu_function = ttk.OptionMenu(frame_data, self.function, self.function.get(), *self.calibrator.get_function_list())
        optionmenu_material['menu'].config(font=font_md)
        optionmenu_dimension['menu'].config(font=font_md)
        optionmenu_function['menu'].config(font=font_md)
        button_assign_manually = ttk.Button(frame_data, text='ASSIGN', command=self.open_assign_window, takefocus=False)
        self.button_calibrate = ttk.Button(frame_data, text='CALIBRATE', command=self.calibrate, state=tk.DISABLED, takefocus=False)
        self.if_correct_bg = tk.BooleanVar(value=False)
        checkbox_correct_bg = ttk.Checkbutton(frame_data, text='Correct Background', variable=self.if_correct_bg, command=self.handle_bg_and_crr, takefocus=False)
        self.if_remove_cosmic_ray = tk.BooleanVar(value=False)
        checkbox_remove_cosmic_ray = ttk.Checkbutton(frame_data, text='Remove Cosmic Ray', variable=self.if_remove_cosmic_ray, command=self.handle_bg_and_crr, takefocus=False)
        label_raw.grid(row=0, column=0)
        label_filename_raw.grid(row=0, column=1, columnspan=2)
        label_ref.grid(row=1, column=0)
        label_filename_ref.grid(row=1, column=1, columnspan=2)
        label_bg.grid(row=2, column=0)
        label_filename_bg.grid(row=2, column=1, columnspan=2)
        optionmenu_material.grid(row=3, column=0)
        optionmenu_dimension.grid(row=3, column=1)
        optionmenu_function.grid(row=3, column=2)
        button_assign_manually.grid(row=4, column=0)
        self.button_calibrate.grid(row=4, column=1, columnspan=2)
        checkbox_correct_bg.grid(row=5, column=0, columnspan=3)
        checkbox_remove_cosmic_ray.grid(row=6, column=0, columnspan=3)

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
        checkbox_show_selection_in_map = ttk.Checkbutton(frame_download, text='Show in Map', variable=self.show_selection_in_map, command=self.update_selection, takefocus=False)
        self.treeview.grid(row=0, column=0, columnspan=3)
        self.button_add.grid(row=1, column=0)
        self.button_delete.grid(row=2, column=0)
        self.button_add_all.grid(row=1, column=1)
        self.button_delete_all.grid(row=2, column=1)
        self.button_save.grid(row=1, column=2, rowspan=2, sticky=tk.NS)
        checkbox_show_selection_in_map.grid(row=3, column=0, columnspan=3)

        # frame plot
        self.map_range = tk.StringVar(value='G(1570~1610)')
        self.optionmenu_map_range = ttk.OptionMenu(frame_plot, self.map_range, self.map_range.get(), 'G(1570~1610)', '2D(2550~2750)', command=self.change_map_range)
        self.optionmenu_map_range.config(state=tk.DISABLED)
        self.optionmenu_map_range['menu'].config(font=font_md)
        self.map_range_1 = tk.DoubleVar(value=1570)
        self.map_range_2 = tk.DoubleVar(value=1610)
        entry_map_range_1 = ttk.Entry(frame_plot, textvariable=self.map_range_1, justify=tk.CENTER, font=font_md, width=6)
        entry_map_range_2 = ttk.Entry(frame_plot, textvariable=self.map_range_2, justify=tk.CENTER, font=font_md, width=6)
        self.button_apply = ttk.Button(frame_plot, text='APPLY', command=self.imshow, state=tk.DISABLED, takefocus=False)
        self.map_color = tk.StringVar(value='hot')
        self.optionmenu_map_color = ttk.OptionMenu(frame_plot, self.map_color, self.map_color.get(),
                                           *sorted(['viridis', 'plasma', 'inferno', 'magma', 'cividis',
                                                    'Wistia', 'hot', 'binary', 'bone', 'cool', 'copper',
                                                    'gray', 'pink', 'spring', 'summer', 'autumn', 'winter',
                                                    'RdBu', 'Spectral', 'bwr', 'coolwarm', 'hsv', 'twilight',
                                                    'CMRmap', 'cubehelix', 'brg', 'gist_rainbow', 'rainbow',
                                                    'jet', 'nipy_spectral', 'gist_ncar']),
                                                   command=self.imshow)
        self.optionmenu_map_color.config(state=tk.DISABLED)
        self.optionmenu_map_color['menu'].config(font=font_md)
        self.autoscale = tk.BooleanVar(value=True)
        checkbox_autoscale = ttk.Checkbutton(frame_plot, text='Auto Scale', variable=self.autoscale, takefocus=False)
        self.optionmenu_map_range.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        entry_map_range_1.grid(row=1, column=0)
        entry_map_range_2.grid(row=1, column=1)
        self.button_apply.grid(row=0, column=2, rowspan=3, sticky=tk.NS)
        self.optionmenu_map_color.grid(row=2, column=0, columnspan=2, sticky=tk.EW)
        checkbox_autoscale.grid(row=3, column=0, columnspan=3)

        # canvas_drop
        self.canvas_drop = tk.Canvas(self.master, width=self.width_canvas, height=self.height_canvas)
        self.canvas_drop.create_rectangle(0, 0, self.width_canvas, self.height_canvas / 3, fill='lightgray')
        self.canvas_drop.create_rectangle(0, self.height_canvas / 3, self.width_canvas, self.height_canvas * 2 / 3, fill='gray')
        self.canvas_drop.create_rectangle(0, self.height_canvas * 2 / 3, self.width_canvas, self.height_canvas, fill='darkgray')
        self.canvas_drop.create_text(self.width_canvas / 2, self.height_canvas / 6, text='2D Map .hdf5 File', font=('Arial', 30))
        self.canvas_drop.create_text(self.width_canvas / 2, self.height_canvas / 2, text='Reference .hdf5 File', font=('Arial', 30))
        self.canvas_drop.create_text(self.width_canvas / 2, self.height_canvas * 5 / 6, text='Background .hdf5 File', font=('Arial', 30))

    def open_assign_window(self):
        self.new_window = tk.Toplevel(self.master)
        self.new_window.title('Assign Peaks')

        self.frame_assign = ttk.Frame(self.new_window)
        self.frame_assign.pack(fill=tk.BOTH, expand=True)

        label_description = ttk.Label(self.frame_assign, text='適用したい場合はウィンドウを開いたままにしてください．')
        label_index = ttk.Label(self.frame_assign, text='Index')
        label_x = ttk.Label(self.frame_assign, text='x')
        label_description.grid(row=0, column=0, columnspan=2)
        label_index.grid(row=1, column=0)
        label_x.grid(row=1, column=1)

        self.refresh_assign_window()

    def refresh_assign_window(self):
        # clear
        for w in self.widgets_assign.values():
            for ww in w:
                ww.destroy()
        self.widgets_assign = {}
        # create
        self.calibrator.set_material(self.material.get())
        x_true = self.calibrator.get_true_x()
        auto_x_true = self.assign_peaks_automatically()
        for i, (r, auto) in enumerate(zip(self.ranges, auto_x_true)):
            label_index = ttk.Label(self.frame_assign, text=str(self.ranges.index(r)))
            combobox_x = ttk.Combobox(self.frame_assign, values=list(x_true), justify=tk.CENTER)
            combobox_x.set(auto)
            label_index.grid(row=i + 2, column=0)
            combobox_x.grid(row=i + 2, column=1)
            self.widgets_assign[i] = (label_index, combobox_x)

    def assign_peaks_automatically(self):
        x_true = self.calibrator.get_true_x()
        found_x_true = []
        for x0, y0, x1, y1 in self.ranges:
            x_mid = (x0 + x1) / 2
            diff = np.abs(x_true - x_mid)
            idx = np.argmin(diff)
            found_x_true.append(x_true[idx])
        return found_x_true

    def assign_peaks(self):
        if self.new_window is None or not self.new_window.winfo_exists():
            return self.assign_peaks_automatically()
        assigned_x_true = []
        for widgets in self.widgets_assign.values():
            x = widgets[1].get()
            assigned_x_true.append(float(x))
        return assigned_x_true

    def calibrate(self) -> None:
        self.calibrator.set_dimension(int(self.dimension.get()[0]))
        self.calibrator.set_material(self.material.get())
        self.calibrator.set_function(self.function.get())
        self.calibrator.reset_data()
        ok = self.calibrator.calibrate(mode='manual', ranges=self.ranges, x_true=self.assign_peaks())
        if not ok:
            messagebox.showerror('Error', 'Peaks not found.')
            return
        self.ax[1].cla()
        for r in self.rectangles:
            self.ax[1].add_patch(r)
        self.calibrator.show_fit_result(self.ax[1])
        self.canvas.draw()
        self.line = None
        self.showing_ref = True

    def handle_bg_and_crr(self):
        # 必ずCRRのあとにbgの処理を行う
        if self.if_remove_cosmic_ray.get():
            self.remove_cosmic_ray()
        else:
            self.undo_remove_cosmic_ray()

        if self.if_correct_bg.get():
            self.subtract_bg()
        else:
            self.undo_subtract_bg()

    def subtract_bg(self):
        try:
            self.calibrator.subtract_bg()
        except ValueError as e:
            messagebox.showerror('Error', str(e))
        self.imshow()

    def undo_subtract_bg(self):
        self.calibrator.undo_subtract_bg()
        self.imshow()

    def remove_cosmic_ray(self):
        try:
            self.calibrator.remove_cosmic_ray(0.2)
        except ValueError as e:
            messagebox.showerror('Error', str(e))
        self.imshow()

    def undo_remove_cosmic_ray(self):
        self.calibrator.undo_remove_cosmic_ray()
        self.imshow()

    def on_click(self, event: matplotlib.backend_bases.MouseEvent) -> None:
        # クリックした点のスペクトルを表示する
        if self.filename_raw.get() == 'please drag & drop!':
            return
        if event.xdata is None or event.ydata is None:
            return
        if not self.calibrator.is_inside(event.xdata, event.ydata):
            return
        self.row, self.col = self.calibrator.coord2idx(event.xdata, event.ydata)
        self.update_plot()

    def key_pressed(self, event: matplotlib.backend_bases.KeyEvent) -> None:
        # 矢印キーで表示するスペクトルを変えられる
        if event.key == 'enter':
            self.imshow()
            return
        if event.key in ['up', 'w'] and self.row < self.calibrator.shape[0] - 1:
            self.row += 1
        elif event.key in ['down', 's'] and 0 < self.row:
            self.row -= 1
        elif event.key in ['right', 'd'] and self.col < self.calibrator.shape[1] - 1:
            self.col += 1
        elif event.key in ['left', 'a'] and 0 < self.col:
            self.col -= 1
        else:
            return
        self.update_plot()

    def change_map_range(self, event=None) -> None:
        if self.map_range.get() == 'G(1570~1610)':
            self.map_range_1.set(1570)
            self.map_range_2.set(1610)
        elif self.map_range.get() == '2D(2550~2750)':
            self.map_range_1.set(2550)
            self.map_range_2.set(2750)
        self.imshow()

    def imshow(self, event=None) -> None:
        self.ax[0].cla()
        self.horizontal_line = self.ax[0].axhline(color='k', lw=1, ls='--')
        self.vertical_line = self.ax[0].axvline(color='k', lw=1, ls='--')
        try:
            self.calibrator.imshow(self.ax[0], [self.map_range_1.get(), self.map_range_2.get()], self.map_color.get())
            self.update_plot()
            self.update_selection()
        except ValueError as e:
            messagebox.showerror('Error', str(e))

    def show_ref(self, event=None):
        if self.filename_ref.get() == 'please drag & drop!':
            return
        plt.autoscale(True)
        if self.line is not None:
            self.line[0].remove()
        else:
            self.ax[1].cla()

        for rect in self.rectangles:
            self.ax[1].add_patch(rect)
        for text in self.texts:
            self.ax[1].add_artist(text)

        self.line = self.ax[1].plot(
            self.calibrator.xdata,
            self.calibrator.ydata,
            label=self.material.get(), color='k')
        self.ax[1].legend()
        self.canvas.draw()

        self.showing_ref = True

    def show_bg(self, event=None):
        if self.filename_bg.get() == 'please drag & drop!':
            return
        plt.autoscale(True)
        if self.line is not None:
            self.line[0].remove()
        else:
            self.ax[1].cla()

        for rect in self.rectangles:
            self.ax[1].add_patch(rect)
        for text in self.texts:
            self.ax[1].add_artist(text)

        self.line = self.ax[1].plot(
            self.calibrator.xdata,
            self.calibrator.bg_data,
            label='Background', color='k')
        self.ax[1].legend()
        self.canvas.draw()

    def update_plot(self) -> None:
        # マッピング上のクロスヘアを移動
        x, y = self.calibrator.idx2coord(self.row, self.col)
        self.horizontal_line.set_ydata(y)
        self.vertical_line.set_xdata(x)

        if not (0 <= self.row < self.calibrator.shape[0] and 0 <= self.col < self.calibrator.shape[1]):
            return

        if self.showing_ref or self.line is None or self.autoscale.get():
            plt.autoscale(True)
            self.ax[1].cla()
        else:
            plt.autoscale(False)  # The very first time requires autoscale
            self.line[0].remove()
        self.line = self.ax[1].plot(
            self.calibrator.xdata,
            self.calibrator.map_data[self.row][self.col],
            label=f'({self.col}, {self.row})', color='r', linewidth=0.8)
        self.ax[1].legend(fontsize=18)
        self.canvas.draw()

        self.showing_ref = False

    def update_selection(self):
        for r in self.selection_patches:
            r.remove()
        self.selection_patches = []
        for child in self.treeview.get_children():
            col, row = self.treeview.item(child)['values']
            x, y = self.calibrator.idx2coord(row, col)
            x1 = x - self.calibrator.x_pad / 2
            y1 = y - self.calibrator.y_pad / 2
            r = patches.Rectangle((x1, y1), self.calibrator.x_pad, self.calibrator.y_pad, fill=False, edgecolor='white', lw=1)
            self.ax[0].add_patch(r)
            self.selection_patches.append(r)

        if not self.show_selection_in_map.get():
            for r in self.selection_patches:
                r.set_visible(False)
        else:
            for r in self.selection_patches:
                r.set_visible(True)
        self.canvas.draw()

    def select_from_treeview(self, event=None):
        if self.treeview.focus() == '':
            return
        self.col, self.row = self.treeview.item(self.treeview.focus())['values']
        self.update_plot()

    def drop(self, event: TkinterDnD.DnDEvent) -> None:
        # ドラッグ&ドロップされたファイルを処理
        # 誘導用の長方形を見えないように
        self.canvas_drop.place_forget()

        # パスによって形式が違う
        # 複数個選択しても1個しか読み込まない
        if event.data[0] == '{':
            filename = event.data.split('} {')[0].strip('{').strip('}')
        else:
            filename = event.data.split()[0]

        # hdf5ファイルのみ受け付ける
        if filename.split('.')[-1] != 'hdf5':
            messagebox.showerror('Error', 'Only .hdf5 files are acceptable.')
            return

        # どこにdropしたかでマッピングファイルなのか、標準サンプルファイルなのか仕分ける
        master_geometry = list(map(int, self.master.winfo_geometry().split('+')[1:]))
        dropped_place = (event.y_root - master_geometry[1] - 30) / self.height_canvas

        if os.name == 'posix':
            threshold = 2 / 3
        else:
            threshold = 1 / 3

        if dropped_place > threshold * 2:  # background data
            self.calibrator.load_bg(filename)
            self.filename_bg.set(os.path.basename(filename))
            self.folder_bg = os.path.dirname(filename)
            self.show_bg()
            self.tooltip_bg.set(filename)
        elif dropped_place > threshold:  # reference data
            self.calibrator.load_ref(filename)
            self.filename_ref.set(os.path.basename(filename))
            self.folder_ref = os.path.dirname(filename)
            for material in self.calibrator.get_material_list():
                if material in filename:
                    self.material.set(material)
            self.button_calibrate.config(state=tk.ACTIVE)
            self.rectangles = []
            self.texts = []
            self.ranges = []
            self.refresh_assign_window()
            self.show_ref()
            self.tooltip_ref.set(filename)
        else:  # raw data
            self.reset()
            ok = self.calibrator.load_raw(filename)
            if not ok:
                messagebox.showerror('Error', 'Choose map data.')
                return
            self.filename_raw.set(os.path.basename(filename))
            self.folder_raw = os.path.dirname(filename)

            self.optionmenu_map_range.config(state=tk.ACTIVE)
            self.button_apply.config(state=tk.ACTIVE)
            self.optionmenu_map_color.config(state=tk.ACTIVE)
            self.imshow()
            self.tooltip_raw.set(filename)

    def drop_enter(self, event: TkinterDnD.DnDEvent) -> None:
        self.canvas_drop.place(anchor='nw', x=0, y=0)

    def drop_leave(self, event: TkinterDnD.DnDEvent) -> None:
        self.canvas_drop.place_forget()

    def reset(self) -> None:
        # マッピングデータのリセット
        self.calibrator.clear()
        self.if_correct_bg.set(False)
        self.filename_raw.set('please drag & drop!')
        self.filename_ref.set('please drag & drop!')
        self.filename_bg.set('please drag & drop!')
        self.folder_raw = './'
        self.folder_ref = './'
        self.folder_bg = './'
        self.button_calibrate.config(state=tk.DISABLED)
        self.button_apply.config(state=tk.DISABLED)
        self.optionmenu_map_range.config(state=tk.DISABLED)
        self.optionmenu_map_color.config(state=tk.DISABLED)
        self.row = 0
        self.col = 0
        self.treeview.delete(*self.treeview.get_children())

    @check_loaded
    def add(self) -> None:
        # 保存リストに追加する
        # 既に追加されている場合は追加しない
        for child in self.treeview.get_children():
            if self.treeview.item(child)['values'] == [self.col, self.row]:
                return
        self.treeview.insert('', tk.END, text='', values=[self.col, self.row])
        self.treeview.yview_moveto(1)
        self.update_selection()

    @check_loaded
    def add_all(self) -> None:
        # 全ての点を保存リストに追加
        all_indices = [[idx2, idx1] for idx2 in range(self.calibrator.shape[1]) for idx1 in
                       range(self.calibrator.shape[0])]
        self.treeview.delete(*self.treeview.get_children())
        for index in all_indices:
            self.treeview.insert('', tk.END, text='', values=index)
        self.update_selection()

    @check_loaded
    def delete(self, event=None) -> None:
        # 保存リストから削除
        # 右クリックから呼ばれた場合、ダイアログを表示
        if event is not None:
            if not messagebox.askyesno('Confirmation', 'Delete these?'):
                return

        idx_to_delete = [self.treeview.item(iid)['values'] for iid in self.treeview.selection()]
        # 何も選択されていない場合、現在の点を削除
        if len(idx_to_delete) == 0:
            idx_to_delete = [[self.col, self.row]]

        for child in self.treeview.get_children():
            if self.treeview.item(child)['values'] in idx_to_delete:
                self.treeview.delete(child)

        self.update_selection()

    @check_loaded
    def delete_all(self) -> None:
        # 保存リストから全て削除
        if not messagebox.askyesno('Confirmation', 'Delete all?'):
            return
        self.treeview.delete(*self.treeview.get_children())
        self.update_selection()

    def save(self) -> None:
        # 保存リスト内のファイルを保存
        if not self.treeview.get_children():
            return

        # フォルダを選択
        # ファイル名はスペクトルのインデックスになる
        folder_to_save = filedialog.askdirectory(initialdir=self.folder_raw)
        if not folder_to_save:
            return

        xdata = self.calibrator.xdata
        for child in self.treeview.get_children():
            col, row = self.treeview.item(child)['values']
            spectrum = self.calibrator.map_data[row][col]
            abs_path_raw = os.path.join(self.folder_raw, self.filename_raw.get())
            if self.filename_ref.get() == 'please drag & drop!':
                abs_path_ref = ''
            else:
                abs_path_ref = os.path.join(self.folder_ref, self.filename_ref.get())
            filename = os.path.join(folder_to_save, f'{str(col)}_{str(row)}.txt')
            with open(filename, 'w') as f:
                f.write(f'# abs_path_raw: {abs_path_raw}\n')
                f.write(f'# abs_path_ref: {abs_path_ref}\n')
                f.write(f'# calibration: {self.calibrator.calibration_info}\n\n')

                for x, y in zip(xdata, spectrum):
                    f.write(f'{x},{y}\n')

    def on_press(self, event):
        if event.xdata is None or event.ydata is None:
            return
        if event.inaxes == self.ax[0]:
            return
        if not self.showing_ref:
            return
        # Toolbarのズーム機能を使っている状態では動作しないようにする
        if self.toolbar._buttons['Zoom'].var.get():
            return
        self.x0 = event.xdata
        self.y0 = event.ydata

        self.drawing = True

    def on_release(self, event):
        if event.xdata is None or event.ydata is None:
            return
        if event.inaxes == self.ax[0]:
            return
        if not self.showing_ref:
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
        self.ax[1].add_patch(r)
        t = self.ax[1].text(x1, y1, str(len(self.rectangles)), color='r', fontsize=20)
        self.rectangles.append(r)
        self.texts.append(t)
        self.ranges.append((x0, y0, x1, y1))
        self.canvas.draw()
        if self.new_window is not None and self.new_window.winfo_exists():
            self.refresh_assign_window()

    def draw_preview(self, event):
        if event.xdata is None or event.ydata is None:
            return
        if event.inaxes == self.ax[0]:
            return
        if not self.showing_ref:
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
        self.ax[1].add_patch(self.rect_drawing)
        self.canvas.draw()

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
        self.canvas.draw()

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
