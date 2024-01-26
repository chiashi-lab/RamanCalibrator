import os
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from tkinterdnd2 import TkinterDnD, DND_FILES
import matplotlib.pyplot as plt
import matplotlib.backend_bases
from matplotlib import rcParams, patches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
from RenishawCalibrator import RenishawCalibrator
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
        self.master.title('Renishaw Calibrator')

        self.calibrator = RenishawCalibrator()

        self.row = self.col = 0

        self.ax: list[plt.Axes] = []

        self.line = None
        self.selection_patches = []

        self.folder_raw = './'
        self.folder_ref = './'

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
        self.canvas = FigureCanvasTkAgg(fig, self.master)
        self.canvas.get_tk_widget().grid(row=0, column=0, rowspan=3)
        toolbar = NavigationToolbar2Tk(self.canvas, self.master, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=3, column=0)
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
        self.filename_raw = tk.StringVar(value='please drag & drop!')
        self.filename_ref = tk.StringVar(value='please drag & drop!')
        label_filename_raw = ttk.Label(frame_data, textvariable=self.filename_raw)
        label_filename_ref = ttk.Label(frame_data, textvariable=self.filename_ref)
        self.tooltip_raw = MyTooltip(label_filename_raw, '')
        self.tooltip_ref = MyTooltip(label_filename_ref, '')
        label_ref.bind('<Button-1>', self.show_ref)
        label_filename_ref.bind('<Button-1>', self.show_ref)
        self.material = tk.StringVar(value=self.calibrator.get_material_list()[0])
        self.dimension = tk.StringVar(value=self.calibrator.get_dimension_list()[0])
        self.function = tk.StringVar(value=self.calibrator.get_function_list()[0])
        optionmenu_material = ttk.OptionMenu(frame_data, self.material, self.material.get(), *self.calibrator.get_material_list())
        optionmenu_dimension = ttk.OptionMenu(frame_data, self.dimension, self.dimension.get(), *self.calibrator.get_dimension_list())
        optionmenu_function = ttk.OptionMenu(frame_data, self.function, self.function.get(), *self.calibrator.get_function_list())
        optionmenu_material['menu'].config(font=font_md)
        optionmenu_dimension['menu'].config(font=font_md)
        optionmenu_function['menu'].config(font=font_md)
        self.button_calibrate = ttk.Button(frame_data, text='CALIBRATE', command=self.calibrate, state=tk.DISABLED)
        label_raw.grid(row=0, column=0)
        label_filename_raw.grid(row=0, column=1, columnspan=2)
        label_ref.grid(row=1, column=0)
        label_filename_ref.grid(row=1, column=1, columnspan=2)
        optionmenu_material.grid(row=2, column=0)
        optionmenu_dimension.grid(row=2, column=1)
        optionmenu_function.grid(row=2, column=2)
        self.button_calibrate.grid(row=3, column=0, columnspan=3)

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

        # frame plot
        label_map_range = tk.Label(frame_plot, text='Map Range')
        self.map_range = tk.StringVar(value='G(1570~1610)')
        self.optionmenu_map_range = ttk.OptionMenu(frame_plot, self.map_range, 'G(1570~1610)', '2D(2550~2750)',
                                                  command=self.change_map_range)
        self.optionmenu_map_range.config(state=tk.DISABLED)
        self.optionmenu_map_range['menu'].config(font=font_md)
        self.map_range_1 = tk.DoubleVar(value=1570)
        self.map_range_2 = tk.DoubleVar(value=1610)
        entry_map_range_1 = ttk.Entry(frame_plot, textvariable=self.map_range_1, justify=tk.CENTER, font=font_md, width=6)
        entry_map_range_2 = ttk.Entry(frame_plot, textvariable=self.map_range_2, justify=tk.CENTER, font=font_md, width=6)
        label_cmap_range = tk.Label(frame_plot, text='Color Range')
        self.cmap_range_1 = tk.DoubleVar(value=0)
        self.cmap_range_2 = tk.DoubleVar(value=10000)
        self.entry_cmap_range_1 = tk.Entry(frame_plot, textvariable=self.cmap_range_1, justify=tk.CENTER, font=font_md, width=6, state=tk.DISABLED)
        self.entry_cmap_range_2 = tk.Entry(frame_plot, textvariable=self.cmap_range_2, justify=tk.CENTER, font=font_md, width=6, state=tk.DISABLED)
        self.button_apply = ttk.Button(frame_plot, text='APPLY', command=self.imshow, state=tk.DISABLED)
        self.map_color = tk.StringVar(value='hot')
        label_map_color = tk.Label(frame_plot, text='Color Map')
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
        label_alpha = tk.Label(frame_plot, text='Alpha')
        self.alpha = tk.DoubleVar(value=1)
        entry_alpha = tk.Entry(frame_plot, textvariable=self.alpha, justify=tk.CENTER, font=font_md, width=6)
        self.spec_autoscale = tk.BooleanVar(value=True)
        checkbox_spec_autoscale = ttk.Checkbutton(frame_plot, text='Spectrum Auto Scale', variable=self.spec_autoscale)
        self.map_autoscale = tk.BooleanVar(value=True)
        checkbox_map_autoscale = ttk.Checkbutton(frame_plot, text='Color Map Auto Scale', variable=self.map_autoscale, command=self.on_map_autoscale)
        self.button_show_ref = ttk.Button(frame_plot, text='SHOW REFERENCE', command=self.show_ref, takefocus=False, state=tk.DISABLED)

        label_map_range.grid(row=0, column=0, rowspan=2)
        self.optionmenu_map_range.grid(row=0, column=1, columnspan=2, sticky=tk.EW)
        self.button_apply.grid(row=0, column=3, rowspan=5, sticky=tk.NS)
        entry_map_range_1.grid(row=1, column=1)
        entry_map_range_2.grid(row=1, column=2)
        label_cmap_range.grid(row=2, column=0)
        self.entry_cmap_range_1.grid(row=2, column=1)
        self.entry_cmap_range_2.grid(row=2, column=2)
        label_map_color.grid(row=3, column=0)
        self.optionmenu_map_color.grid(row=3, column=1, columnspan=2, sticky=tk.EW)
        label_alpha.grid(row=4, column=0)
        entry_alpha.grid(row=4, column=1)
        checkbox_map_autoscale.grid(row=5, column=0, columnspan=4)
        checkbox_spec_autoscale.grid(row=6, column=0, columnspan=4)
        self.button_show_ref.grid(row=7, column=0, columnspan=4, sticky=tk.EW)

        # canvas_drop
        self.canvas_drop = tk.Canvas(self.master, width=self.width_canvas, height=self.height_canvas)
        self.canvas_drop.create_rectangle(0, 0, self.width_canvas, self.height_canvas / 2, fill='lightgray')
        self.canvas_drop.create_rectangle(0, self.height_canvas / 2, self.width_canvas, self.height_canvas, fill='gray')
        self.canvas_drop.create_text(self.width_canvas / 2, self.height_canvas / 4, text='① 2D Map .wdf File',
                                     font=('Arial', 30))
        self.canvas_drop.create_text(self.width_canvas / 2, self.height_canvas * 3 / 4, text='② Reference .wdf File',
                                     font=('Arial', 30))

    def calibrate(self) -> None:
        self.calibrator.set_dimension(int(self.dimension.get()[0]))
        self.calibrator.set_material(self.material.get())
        self.calibrator.set_function(self.function.get())
        self.calibrator.reset_data()
        ok = self.calibrator.calibrate()
        if not ok:
            messagebox.showerror('Error', 'Peaks not found.')
            return
        self.ax[1].cla()
        self.calibrator.show_fit_result(self.ax[1])
        self.canvas.draw()
        self.line = None

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
        # column majorに変換
        iy, ix = self.calibrator.row2col(self.row, self.col)
        if event.key == 'up' and iy < self.calibrator.shape[0] - 1:
            iy += 1
        elif event.key == 'down' and 0 < iy:
            iy -= 1
        elif event.key == 'right' and ix < self.calibrator.shape[1] - 1:
            ix += 1
        elif event.key == 'left' and 0 < ix:
            ix -= 1
        else:
            return
        self.row, self.col = self.calibrator.col2row(iy, ix)
        self.update_plot()

    def change_map_range(self, event=None) -> None:
        if self.map_range.get() == 'G(1570~1610)':
            self.map_range_1.set(1570)
            self.map_range_2.set(1610)
        elif self.map_range.get() == '2D(2550~2750)':
            self.map_range_1.set(2550)
            self.map_range_2.set(2750)
        self.imshow()

    def on_map_autoscale(self, event=None) -> None:
        if self.map_autoscale.get():
            self.entry_cmap_range_1.config(state=tk.DISABLED)
            self.entry_cmap_range_2.config(state=tk.DISABLED)
        else:
            self.entry_cmap_range_1.config(state=tk.NORMAL)
            self.entry_cmap_range_2.config(state=tk.NORMAL)

    def imshow(self, event=None) -> None:
        self.ax[0].cla()
        self.horizontal_line = self.ax[0].axhline(color='k', lw=1, ls='--')
        self.vertical_line = self.ax[0].axvline(color='k', lw=1, ls='--')
        try:
            cmap_range = [self.cmap_range_1.get(), self.cmap_range_2.get()] if not self.map_autoscale.get() else None
            self.calibrator.imshow(
                self.ax[0],
                [self.map_range_1.get(), self.map_range_2.get()],
                self.map_color.get(),
                cmap_range,
                self.alpha.get()
            )
            self.update_selection()
        except ValueError as e:
            print('ValueError', e)

    def show_ref(self, event=None):
        if self.filename_ref.get() == 'please drag & drop!':
            return
        plt.autoscale(True)
        if self.line is not None:
            self.line[0].remove()
        else:
            self.ax[1].cla()

        self.line = self.ax[1].plot(
            self.calibrator.xdata,
            self.calibrator.ydata,
            label=self.material.get(), color='k')
        self.ax[1].legend()
        self.canvas.draw()

    def update_plot(self) -> None:
        # マッピング上のクロスヘアを移動
        x, y = self.calibrator.idx2coord(self.row, self.col)
        self.horizontal_line.set_ydata(y)
        self.vertical_line.set_xdata(x)

        if not (0 <= self.row < self.calibrator.shape[0] and 0 <= self.col < self.calibrator.shape[1]):
            return

        if self.spec_autoscale.get():
            plt.autoscale(True)
            self.ax[1].cla()
        else:
            if self.line is not None:
                plt.autoscale(False)  # The very first time requires autoscale
                self.line[0].remove()
            else:  # for after calibration
                self.ax[1].cla()
        iy, ix = self.calibrator.row2col(self.row, self.col)
        self.line = self.ax[1].plot(
            self.calibrator.xdata,
            self.calibrator.map_data[self.row][self.col],
            label=f'({ix}, {iy})', color='r', linewidth=0.8)
        self.ax[1].legend(fontsize=18)
        self.canvas.draw()

    def update_selection(self):
        for r in self.selection_patches:
            r.remove()
        self.selection_patches = []
        for child in self.treeview.get_children():
            idx2, idx1 = self.treeview.item(child)['values']
            row, col = self.calibrator.col2row(idx1, idx2)
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
        self.row, self.col = self.calibrator.col2row(*self.treeview.item(self.treeview.focus())['values'][::-1])
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

        # wdfファイルのみ受け付ける
        if filename.split('.')[-1] != 'wdf':
            messagebox.showerror('Error', 'Only .wdf files are acceptable.')
            return

        # どこにdropしたかでマッピングファイルなのか、標準サンプルファイルなのか仕分ける
        master_geometry = list(map(int, self.master.winfo_geometry().split('+')[1:]))
        dropped_place = (event.y_root - master_geometry[1] - 30) / self.height_canvas

        if os.name == 'posix':
            threshold = 1
        else:
            threshold = 0.5

        if dropped_place > threshold:  # reference data
            has_same_xdata = self.calibrator.load_ref(filename)
            if not has_same_xdata:
                messagebox.showerror('Error', 'X-axis data does not match. Choose reference data with same measurement condition as the map data.')
                return
            self.filename_ref.set(os.path.basename(filename))
            self.folder_ref = os.path.dirname(filename)
            for material in self.calibrator.get_material_list():
                if material in filename:
                    self.material.set(material)
            self.button_calibrate.config(state=tk.ACTIVE)
            self.button_show_ref.config(state=tk.ACTIVE)
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
            self.update_plot()
            self.tooltip_raw.set(filename)

    def drop_enter(self, event: TkinterDnD.DnDEvent) -> None:
        self.canvas_drop.place(anchor='nw', x=0, y=0)

    def drop_leave(self, event: TkinterDnD.DnDEvent) -> None:
        self.canvas_drop.place_forget()

    def reset(self) -> None:
        # マッピングデータのリセット
        self.calibrator.reset()
        self.filename_raw.set('please drag & drop!')
        self.filename_ref.set('please drag & drop!')
        self.folder_raw = './'
        self.folder_ref = './'
        self.button_calibrate.config(state=tk.DISABLED)
        self.button_show_ref.config(state=tk.DISABLED)
        self.button_apply.config(state=tk.DISABLED)
        self.optionmenu_map_range.config(state=tk.DISABLED)
        self.optionmenu_map_color.config(state=tk.DISABLED)
        self.row = 0
        self.col = 0
        self.treeview.delete(*self.treeview.get_children())

    @check_loaded
    def add(self) -> None:
        # 保存リストに追加する
        index = self.calibrator.row2col(self.row, self.col)[::-1]

        # 既に追加されている場合は追加しない
        for child in self.treeview.get_children():
            if self.treeview.item(child)['values'] == list(index):
                return
        self.treeview.insert('', tk.END, text='', values=index)
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
            idx_to_delete = [list(self.calibrator.row2col(self.row, self.col))[::-1]]

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
            ix, iy = self.treeview.item(child)['values']
            row, col = self.calibrator.col2row(iy, ix)
            spectrum = self.calibrator.map_data[row][col]
            abs_path_raw = os.path.join(self.folder_raw, self.filename_raw.get())
            if self.filename_ref.get() == 'please drag & drop!':
                abs_path_ref = ''
            else:
                abs_path_ref = os.path.join(self.folder_ref, self.filename_ref.get())
            filename = os.path.join(folder_to_save, f'{str(ix)}_{str(iy)}.txt')
            with open(filename, 'w') as f:
                f.write(f'# abs_path_raw: {abs_path_raw}\n')
                f.write(f'# abs_path_ref: {abs_path_ref}\n')
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
