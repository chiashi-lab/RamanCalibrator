import os
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinterdnd2 import TkinterDnD, DND_FILES
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.backend_bases
from matplotlib import rcParams
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
from RenishawCalibrator import RenishawCalibrator

rcParams['keymap.back'].remove('left')
rcParams['keymap.forward'].remove('right')


class MainWindow(tk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.master = master
        self.width_master = 1350
        self.height_master = 450
        self.master.geometry(f'{self.width_master}x{self.height_master}')

        self.calibrator = RenishawCalibrator()
        self.ready_to_show = False
        self.row = self.col = 0

        self.line = None

        self.folder = './'

        self.create_widgets()

    def create_widgets(self) -> None:
        # canvas
        self.width_canvas = 1000
        self.height_canvas = 400
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
        plt.subplots_adjust(left=0.01, right=0.99, bottom=0.05, top=0.99)
        fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.canvas.mpl_connect('key_press_event', self.key_pressed)
        self.canvas.mpl_connect('key_press_event', key_press_handler)

        # frames
        frame_data = tk.LabelFrame(self.master, text='Data')
        frame_download = tk.LabelFrame(self.master, text='Download')
        frame_plot = tk.LabelFrame(self.master, text='Plot')
        frame_data.grid(row=0, column=1)
        frame_download.grid(row=1, column=1)
        frame_plot.grid(row=2, column=1)

        # frame_data
        label_raw = tk.Label(frame_data, text='Raw:')
        self.filename_raw = tk.StringVar(value='please drag & drop!')
        self.label_filename_raw = tk.Label(frame_data, textvariable=self.filename_raw)
        label_ref = tk.Label(frame_data, text='Reference:')
        self.filename_ref = tk.StringVar(value='please drag & drop!')
        self.label_filename_ref = tk.Label(frame_data, textvariable=self.filename_ref)
        print(self.calibrator.get_material_list())
        self.material = tk.StringVar(value=self.calibrator.get_material_list()[0])
        optionmenu_material = tk.OptionMenu(frame_data, self.material, *self.calibrator.get_material_list())
        self.dimension = tk.StringVar(value='1 (Linear)')
        optionmenu_dimension = tk.OptionMenu(frame_data, self.dimension, *self.calibrator.get_dimension_list())
        self.function = tk.StringVar(value='Lorentzian')
        optionmenu_function = tk.OptionMenu(frame_data, self.function, *self.calibrator.get_function_list())
        self.button_calibrate = tk.Button(frame_data, text='CALIBRATE', command=self.calibrate, state=tk.DISABLED)

        label_raw.grid(row=0, column=0)
        self.label_filename_raw.grid(row=0, column=1)
        label_ref.grid(row=1, column=0)
        self.label_filename_ref.grid(row=1, column=1)
        optionmenu_material.grid(row=2, column=0)
        optionmenu_dimension.grid(row=2, column=1)
        optionmenu_function.grid(row=2, column=2)
        self.button_calibrate.grid(row=3, column=0, columnspan=3)

        # frame_download
        self.file_to_download = tk.Variable(value=[])
        self.listbox = tk.Listbox(frame_download, listvariable=self.file_to_download, selectmode=tk.MULTIPLE, width=8,
                                  height=6, justify=tk.CENTER)
        self.listbox.bind('<Button-2>', self.delete)
        self.listbox.bind('<Button-3>', self.delete)
        scrollbar = tk.Scrollbar(frame_download)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)
        self.button_add = tk.Button(frame_download, text='ADD', command=self.add)
        self.button_add_all = tk.Button(frame_download, text='ADD ALL', command=self.add_all)
        self.button_save = tk.Button(frame_download, text='SAVE', command=self.save)

        self.listbox.grid(row=0, column=0, columnspan=3)
        scrollbar.grid(row=0, column=2)
        self.button_add.grid(row=1, column=0)
        self.button_add_all.grid(row=1, column=1)
        self.button_save.grid(row=1, column=2)

        # frame plot
        self.map_range = tk.StringVar(value='G(1570~1610)')
        self.optionmenu_map_range = tk.OptionMenu(frame_plot, self.map_range, 'G(1570~1610)', '2D(2550~2750)',
                                                  command=self.change_map_range)
        self.optionmenu_map_range.config(state=tk.DISABLED)
        self.map_range_1 = tk.DoubleVar(value=1570)
        self.map_range_2 = tk.DoubleVar(value=1610)
        entry_map_range_1 = tk.Entry(frame_plot, textvariable=self.map_range_1, width=7, justify=tk.CENTER)
        entry_map_range_2 = tk.Entry(frame_plot, textvariable=self.map_range_2, width=7, justify=tk.CENTER)
        self.button_apply = tk.Button(frame_plot, text='APPLY', command=self.imshow, width=7, state=tk.DISABLED)
        self.map_color = tk.StringVar(value='hot')
        self.optionmenu_map_color = tk.OptionMenu(frame_plot, self.map_color,
                                                  *sorted(['viridis', 'plasma', 'inferno', 'magma', 'cividis',
                                                           'Wistia', 'hot', 'binary', 'bone', 'cool', 'copper',
                                                           'gray', 'pink', 'spring', 'summer', 'autumn', 'winter',
                                                           'RdBu', 'Spectral', 'bwr', 'coolwarm', 'hsv', 'twilight',
                                                           'CMRmap', 'cubehelix', 'brg', 'gist_rainbow', 'rainbow',
                                                           'jet', 'nipy_spectral', 'gist_ncar']),
                                                  command=self.imshow)
        self.optionmenu_map_color.config(state=tk.DISABLED)
        self.autoscale = tk.BooleanVar(value=True)
        checkbox_autoscale = tk.Checkbutton(frame_plot, text='Auto Scale', variable=self.autoscale)

        self.optionmenu_map_range.grid(row=0, column=0, columnspan=3)
        entry_map_range_1.grid(row=1, column=0)
        entry_map_range_2.grid(row=1, column=1)
        self.button_apply.grid(row=1, column=2)
        self.optionmenu_map_color.grid(row=2, column=0, columnspan=3)
        checkbox_autoscale.grid(row=3, column=0, columnspan=3)

        # canvas_drop
        self.canvas_drop = tk.Canvas(self.master, width=self.width_master, height=self.height_master)
        self.canvas_drop.create_rectangle(0, 0, self.width_master, self.height_master / 2, fill='lightgray')
        self.canvas_drop.create_rectangle(0, self.height_master / 2, self.width_master, self.height_master, fill='gray')
        self.canvas_drop.create_text(self.width_master / 2, self.height_master / 4, text='2D Map .wdf File',
                                     font=('Arial', 30))
        self.canvas_drop.create_text(self.width_master / 2, self.height_master * 3 / 4, text='Reference .wdf File',
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
        if event.xdata is None or event.ydata is None:
            return
        if not self.calibrator.is_inside(event.xdata, event.ydata):
            return
        self.row, self.col = self.calibrator.coord2idx(event.xdata, event.ydata)
        self.update_plot()

    def key_pressed(self, event: matplotlib.backend_bases.KeyEvent) -> None:
        if event.key == 'enter':
            self.imshow()
            return
        row, col = self.calibrator.row2col(self.row, self.col)
        if event.key == 'up' and row < self.calibrator.shape[0] - 1:
            row += 1
        elif event.key == 'down' and 0 < row:
            row -= 1
        elif event.key == 'right' and col < self.calibrator.shape[1] - 1:
            col += 1
        elif event.key == 'left' and 0 < col:
            col -= 1
        else:
            return
        self.row, self.col = self.calibrator.col2row(row, col)
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
        self.horizontal_line = self.ax[0].axhline(color='k', lw=0.8, ls='--')
        self.vertical_line = self.ax[0].axvline(color='k', lw=0.8, ls='--')
        self.horizontal_line.set_visible(True)
        self.vertical_line.set_visible(True)
        self.calibrator.imshow(self.ax[0], [self.map_range_1.get(), self.map_range_2.get()], self.map_color.get())
        self.canvas.draw()

    def update_plot(self) -> None:
        x, y = self.calibrator.idx2coord(self.row, self.col)
        self.horizontal_line.set_ydata(y)
        self.vertical_line.set_xdata(x)
        if 0 <= self.row < self.calibrator.shape[0] and 0 <= self.col < self.calibrator.shape[1]:
            if self.autoscale.get():
                plt.autoscale(True)
                self.ax[1].cla()
            else:
                if self.line is not None:
                    plt.autoscale(False)  # The very first time requires autoscale
                    self.line[0].remove()
                else:  # for after calibration
                    self.ax[1].cla()
            idx = self.calibrator.row2col(self.row, self.col)
            self.line = self.ax[1].plot(
                self.calibrator.xdata,
                self.calibrator.map_data[self.row][self.col],
                label=str(idx), color='r', linewidth=0.8)
            self.ax[1].legend()
            self.canvas.draw()

    def drop(self, event: TkinterDnD.DnDEvent=None) -> None:
        self.canvas_drop.place_forget()

        filename = event.data.split()[0]

        if filename.split('.')[-1] != 'wdf':
            messagebox.showerror('Error', 'Only .wdf files are acceptable.')
            return

        master_geometry = list(map(int, self.master.winfo_geometry().split('+')[1:]))
        dropped_place = (event.y_root - master_geometry[1] - 30) / self.height_canvas

        if os.name == 'posix':
            threshold = 1
        else:
            threshold = 0.5

        if dropped_place > threshold:  # reference data
            self.calibrator.load_ref(filename)
            self.filename_ref.set(os.path.split(filename)[-1])
            for material in self.calibrator.get_material_list():
                if material in filename:
                    self.material.set(material)
            self.button_calibrate.config(state=tk.ACTIVE)
        else:  # raw data
            ok = self.calibrator.load_raw(filename)
            if not ok:
                messagebox.showerror('Error', 'Choose map data.')
                return
            self.filename_raw.set(os.path.basename(filename))
            self.folder = os.path.dirname(filename)
            self.ready_to_show = True

        if self.ready_to_show:
            self.optionmenu_map_range.config(state=tk.ACTIVE)
            self.button_apply.config(state=tk.ACTIVE)
            self.optionmenu_map_color.config(state=tk.ACTIVE)
            self.imshow()
            self.update_plot()

    def drop_enter(self, event: TkinterDnD.DnDEvent) -> None:
        self.canvas_drop.place(anchor='nw', x=0, y=0)

    def drop_leave(self, event: TkinterDnD.DnDEvent) -> None:
        self.canvas_drop.place_forget()

    def add(self) -> None:
        indices = self.file_to_download.get()
        if indices == '':
            indices = []
        else:
            indices = list(indices)
        index = list(self.calibrator.row2col(self.row, self.col))
        indices.append(index)
        self.file_to_download.set(indices)

    def add_all(self) -> None:
        all_indices = [(idx1, idx2) for idx2 in range(self.calibrator.shape[1]) for idx1 in
                       range(self.calibrator.shape[0])]
        self.file_to_download.set(all_indices)

    def delete(self, event=None) -> None:
        if not messagebox.askyesno('Confirmation', 'Delete these?'):
            return
        for idx in sorted(list(self.listbox.curselection()), reverse=True):
            self.listbox.delete(idx)

    def save(self) -> None:
        if not self.file_to_download.get():
            return

        folder_to_save = filedialog.askdirectory(initialdir=self.folder)
        if not folder_to_save:
            return

        xdata = self.calibrator.xdata
        for i, (idx1, idx2) in enumerate(self.file_to_download.get()):
            row, col = self.calibrator.col2row(idx1, idx2)
            map_data = self.calibrator.map_data[row][col]
            data = np.vstack((xdata.T, map_data.T)).T
            abs_path_raw = os.path.join(self.folder, self.filename_raw.get())
            if self.filename_ref.get() == 'please drag & drop!':
                abs_path_ref = ''
            else:
                abs_path_ref = os.path.join(self.folder, self.filename_ref.get())
            filename = os.path.join(folder_to_save, f'{str(idx1)}_{str(idx2)}.txt')
            with open(filename, 'w') as f:
                f.write(f'# abs_path_raw: {abs_path_raw}\n')
                f.write(f'# abs_path_ref: {abs_path_ref}\n')
                f.write(f'# calibration: {self.calibrator.calibration_info}\n\n')

                for x, y in data:
                    f.write(f'{x},{y}\n')

    def quit(self) -> None:
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
