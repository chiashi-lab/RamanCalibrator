import json
import numpy as np
import PIL
import matplotlib.pyplot as plt
from renishawWiRE import WDFReader
from calibrator import Calibrator


class RenishawCalibrator:
    def __init__(self):
        with open('./data/reference.json', 'r') as f:
            self.database = json.load(f)
        self.reader_raw: WDFReader = None
        self.reader_ref: WDFReader = None

        self.xdata: np.ndarray = None
        self.ydata: np.ndarray = None

        self.base_calibrator = Calibrator()
        self.base_calibrator.set_measurement('Raman')

    def load_raw(self, filename: str) -> bool:
        self.reader_raw = WDFReader(filename)
        self.xdata = self.reader_raw.xdata.copy()
        self.ydata = self.reader_raw.spectra.copy()
        if len(self.ydata.shape) != 3:
            return False
        self.shape = self.ydata.shape[:2]
        self.x_start = self.reader_raw.map_info['x_start']
        self.y_start = self.reader_raw.map_info['y_start']
        self.x_pad = self.reader_raw.map_info['x_pad']
        self.y_pad = self.reader_raw.map_info['y_pad']
        self.x_span = self.reader_raw.map_info['x_span']
        self.y_span = self.reader_raw.map_info['y_span']
        return True

    def load_ref(self, filename: str) -> None:
        self.reader_ref = WDFReader(filename)
        if len(self.reader_ref.spectra.shape) == 3:  # when choose 2D data for reference
            self.reader_ref.spectra = self.reader_ref.spectra[0]  # TODO: enable user to choose
            self.base_calibrator.set_data(self.reader_ref.xdata, self.reader_ref.spectra[0])
        else:
            self.base_calibrator.set_data(self.reader_ref.xdata, self.reader_ref.spectra)

    def show_fit_result(self, ax: plt.Axes) -> None:
        ax.plot(self.reader_ref.xdata, self.reader_ref.spectra, color='k')
        ymin, ymax = ax.get_ylim()

        # for fitted_x in self.fitted_x_ref:
        for fitted_x in self.base_calibrator.fitted_x:
            ax.vlines(fitted_x, ymin, ymax, color='r', linewidth=1)

    def calibrate(self, dimension: int, material: str, function: str) -> bool:
        self.base_calibrator.set_dimension(dimension)
        self.base_calibrator.set_material(material)
        self.base_calibrator.set_function(function)
        return self.base_calibrator.calibrate()

    def imshow(self, ax: plt.Axes, map_range: list[float], cmap: str) -> None:
        img_x0, img_y0 = self.reader_raw.img_origins
        img_w, img_h = self.reader_raw.img_dimensions
        img = PIL.Image.open(self.reader_raw.img)
        extent = (img_x0, img_x0 + img_w, img_y0 + img_h, img_y0)

        ax.set_xlim(img_x0, img_x0 + img_w)
        ax.set_ylim(img_y0 + img_h, img_y0)

        ax.imshow(img, extent=extent)

        extent = (self.x_start, self.x_start + self.x_span, self.y_start, self.y_start + self.y_span)

        map_range_idx = (map_range[0] < self.xdata) & (self.xdata < map_range[1])
        data = self.ydata[:, :, map_range_idx]
        if data.shape[2] == 0:
            return
        data = data.sum(axis=2) - data.mean(axis=2)
        data = data.reshape(data.shape[::-1]).T

        ax.imshow(data, alpha=0.9, extent=extent, origin='lower', cmap=cmap)

    def col2row(self, row: int, col: int) -> [int, int]:
        idx = col * self.shape[0] + row
        # row major
        row = idx // self.shape[1]
        col = idx % self.shape[1]

        return row, col

    def row2col(self, row: int, col: int) -> [int, int]:
        idx = row * self.shape[1] + col
        # column major
        col = idx // self.shape[0]
        row = idx % self.shape[0]

        return row, col

    def coord2idx(self, x_pos: float, y_pos: float) -> [int, int]:
        # column major
        col = int((x_pos - self.x_start) // self.x_pad)
        row = int((y_pos - self.y_start) // self.y_pad)

        return self.col2row(row, col)

    def idx2coord(self, row: int, col: int) -> [float, float]:
        row, col = self.row2col(row, col)
        return self.x_start + self.x_pad * (col + 0.5), self.y_start + self.y_pad * (row + 0.7)

    def is_inside(self, x: float, y: float) -> bool:
        if (self.x_start <= x <= self.x_start + self.x_span) and (self.y_start + self.y_span <= y <= self.y_start):
            return True
        else:
            return False
