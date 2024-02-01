import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
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
        self.__init__()

    def load_raw(self, filename: str) -> bool:
        # 二次元マッピングファイルを読み込む
        self.reader_raw = WDFReader(filename)
        self.xdata = self.reader_raw.xdata.copy()
        self.map_data = self.reader_raw.spectra.copy()
        map_new = np.zeros_like(self.map_data)
        for i1 in range(self.map_data.shape[0]):
            for j1 in range(self.map_data.shape[1]):
                index = i1 * self.map_data.shape[1] + j1
                i2 = index % self.map_data.shape[0]
                j2 = index // self.map_data.shape[0]
                map_new[i2, j2] = self.map_data[i1, j1]
        self.map_data = np.array(map_new)
        if len(self.map_data.shape) == 1:  # 点測定データ
            self.map_data = self.map_data.reshape(1, 1, -1)
            # 仮のデータを入れる
            self.shape = self.map_data.shape[:2]
            # マッピングの一番右下の座標
            self.x_start = 0
            self.y_start = 0
            # マッピングの1ピクセルあたりのサイズ
            self.x_pad = 1
            self.y_pad = 1
            # マッピングの全体のサイズ
            self.x_span = 1
            self.y_span = 1
            # 空の画像を作る
            self.img = Image.new('RGB', (1, 1), (200, 200, 200))
            self.reader_raw.img_origins = (-0.1, -0.1)
            self.reader_raw.img_dimensions = (1.2, 1.2)
            return True
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
        self.img = Image.open(self.reader_raw.img)
        return True

    def load_ref(self, filename: str) -> bool:
        # 標準サンプルのファイルを読み込む
        self.reader_ref = WDFReader(filename)
        if len(self.reader_ref.spectra.shape) == 3:  # when choose 2D data for reference
            self.reader_ref.spectra = self.reader_ref.spectra[0][0]  # TODO: allow user to choose
            print('Reference data is supposed to be single measurement, but map data was loaded.')
        if not self.is_xdata_correct():
            return False
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra)
        return True

    def is_xdata_correct(self):
        if self.reader_raw is None:
            return True
        # xdataが同じかどうか確認する
        if not np.all(self.reader_raw.xdata == self.reader_ref.xdata):
            return False
        return True

    def reset_data(self):
        # キャリブレーションを複数かけることのないよう、毎度リセットをかける
        if self.reader_raw is None or self.reader_ref is None:
            raise ValueError('Load data before reset.')
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra)

    def imshow(self, ax: plt.Axes, map_range: list, cmap: str, cmap_range: list[float], alpha: float) -> None:
        if self.reader_raw is None:
            raise ValueError('Load data before imshow.')
        # マッピングの表示
        # 光学像の位置、サイズを取り出す
        img_x0, img_y0 = self.reader_raw.img_origins
        img_w, img_h = self.reader_raw.img_dimensions
        extent_optical = (img_x0, img_x0 + img_w, img_y0 + img_h, img_y0)
        ax.set_xlim(img_x0, img_x0 + img_w)
        ax.set_ylim(img_y0 + img_h, img_y0)
        # まずは光学像を描画
        ax.imshow(self.img, extent=extent_optical)
        # ラマンマッピングの描画
        extent_mapping = (self.x_start, self.x_start + self.x_span, self.y_start, self.y_start + self.y_span)
        map_range_idx = (map_range[0] < self.xdata) & (self.xdata < map_range[1])
        data = self.map_data[:, :, map_range_idx]
        if data.shape[2] == 0:
            return
        data = np.array([[subtract_baseline(d).sum() for d in dat] for dat in data])
        # カラーマップ範囲
        cmap_range = [data.min(), data.max()] if cmap_range is None else cmap_range
        # 光学像の上にマッピングを描画
        ax.imshow(data, alpha=alpha, extent=extent_mapping, origin='lower', cmap=cmap, norm=Normalize(vmin=cmap_range[0], vmax=cmap_range[1]))

    def coord2idx(self, x_pos: float, y_pos: float) -> [int, int]:
        col = round((x_pos - self.x_start) // self.x_pad)
        row = round((y_pos - self.y_start) // self.y_pad)
        return row, col

    def idx2coord(self, row: int, col: int) -> [float, float]:
        return self.x_start + self.x_pad * (col + 0.5), self.y_start + self.y_pad * (row + 0.5)

    def is_inside(self, x: float, y: float) -> bool:
        # check if the selected position is inside the mapping
        xmin, xmax = sorted([self.x_start, self.x_start + self.x_span])
        ymin, ymax = sorted([self.y_start, self.y_start + self.y_span])
        if (xmin <= x <= xmax) and (ymin <= y <= ymax):
            return True
        else:
            return False

    def close(self):
        if self.reader_raw is not None:
            self.reader_raw.close()
        if self.reader_ref is not None:
            self.reader_ref.close()
