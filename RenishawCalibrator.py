import numpy as np
import PIL
import matplotlib.pyplot as plt
from renishawWiRE import WDFReader
from calibrator import Calibrator


def subtract_baseline(data: np.ndarray):
    baseline = np.linspace(data[0], data[-1], data.shape[0])
    return data - baseline


# Calibratorは自作ライブラリ。Rayleigh, Raman用のデータとフィッティングの関数等が含まれている。
class RenishawCalibrator(Calibrator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reader_raw: WDFReader = None
        self.reader_ref: WDFReader = None

        self.map_data: np.ndarray = None

        self.set_measurement('Raman')

    def reset(self):
        self.reader_raw = None
        self.reader_ref = None
        self.map_data = None

    def load_raw(self, filename: str) -> bool:
        # 二次元マッピングファイルを読み込む
        self.reader_raw = WDFReader(filename)
        self.xdata = self.reader_raw.xdata.copy()
        self.map_data = self.reader_raw.spectra.copy()
        # 二次元じゃない場合False (x座標) x (y座標) x (スペクトル) の3次元のはず
        if len(self.map_data.shape) != 3:
            return False
        self.shape = self.map_data.shape[:2]
        # マッピングの一番右下の座標
        self.x_start = self.reader_raw.map_info['x_start']
        self.y_start = self.reader_raw.map_info['y_start']
        # マッピングの1ピクセルあたりのサイズ
        self.x_pad = self.reader_raw.map_info['x_pad']
        self.y_pad = self.reader_raw.map_info['y_pad']
        # マッピングの全体のサイズ
        self.x_span = self.reader_raw.map_info['x_span']
        self.y_span = self.reader_raw.map_info['y_span']
        return True

    def load_ref(self, filename: str) -> None:
        # 標準サンプルのファイルを読み込む
        self.reader_ref = WDFReader(filename)
        if len(self.reader_ref.spectra.shape) == 3:  # when choose 2D data for reference
            self.reader_ref.spectra = self.reader_ref.spectra[0][0]  # TODO: allow user to choose
            print('Reference data is supposed to be single measurement, but map data was loaded.')
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra)

    def reset_data(self):
        # キャリブレーションを複数かけることのないよう、毎度リセットをかける
        if self.reader_raw is None or self.reader_ref is None:
            raise ValueError('Load data before reset.')
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra)

    def imshow(self, ax: plt.Axes, map_range: list, cmap: str) -> None:
        if self.reader_raw is None:
            raise ValueError('Load data before imshow.')
        # マッピングの表示
        # 光学像の位置、サイズを取り出す
        img_x0, img_y0 = self.reader_raw.img_origins
        img_w, img_h = self.reader_raw.img_dimensions
        img = PIL.Image.open(self.reader_raw.img)
        extent_optical = (img_x0, img_x0 + img_w, img_y0 + img_h, img_y0)
        ax.set_xlim(img_x0, img_x0 + img_w)
        ax.set_ylim(img_y0 + img_h, img_y0)
        # まずは光学像を描画
        ax.imshow(img, extent=extent_optical)

        extent_mapping = (self.x_start, self.x_start + self.x_span, self.y_start, self.y_start + self.y_span)
        map_range_idx = (map_range[0] < self.xdata) & (self.xdata < map_range[1])
        data = self.map_data[:, :, map_range_idx]
        if data.shape[2] == 0:
            return
        data = np.array([[subtract_baseline(d).sum() for d in dat] for dat in data])
        data = data.reshape(data.shape[::-1]).T
        # 光学像の上にマッピングを描画
        ax.imshow(data, alpha=0.9, extent=extent_mapping, origin='lower', cmap=cmap)

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
        # get index of column major
        col = round((x_pos - self.x_start) // self.x_pad)
        row = round((y_pos - self.y_start) // self.y_pad)
        # change to row major and return it
        return self.col2row(row, col)

    def idx2coord(self, row: int, col: int) -> [float, float]:
        # get column major index
        row, col = self.row2col(row, col)
        return self.x_start + self.x_pad * (col + 0.5), self.y_start + self.y_pad * (row + 0.5)

    def is_inside(self, x: float, y: float) -> bool:
        # check if the selected position is inside the mapping
        if (self.x_start <= x <= self.x_start + self.x_span) and (self.y_start + self.y_span <= y <= self.y_start):
            return True
        else:
            return False

    def close(self):
        if self.reader_raw is not None:
            self.reader_raw.close()
        if self.reader_ref is not None:
            self.reader_ref.close()
