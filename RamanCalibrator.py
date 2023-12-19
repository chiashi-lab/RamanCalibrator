import numpy as np
import matplotlib.pyplot as plt
from dataloader import RamanHDFReader, DataLoader
from calibrator import Calibrator


def subtract_baseline(data: np.ndarray):
    baseline = np.linspace(data[0], data[-1], data.shape[0])
    return data - baseline


def remove_cosmic_ray(spectra: np.ndarray, threshold: float = 0.2):
    mean = spectra.mean(axis=2)
    std = spectra.std()
    deviation = (spectra - mean[:, :, np.newaxis, :]) / std
    mask = np.where(deviation > threshold, 0, 1)
    spectra_removed = spectra * mask
    spectra_average = spectra_removed.sum(axis=2)[:, :, np.newaxis, :] / mask.sum(axis=2)[:, :, np.newaxis, :] * (1 - mask)
    return spectra_removed + spectra_average


# Calibratorは自作ライブラリ。Rayleigh, Raman用のデータとフィッティングの関数等が含まれている。
class RamanCalibrator(Calibrator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reader_raw: RamanHDFReader = None
        self.reader_ref: RamanHDFReader = None
        self.reader_bg: RamanHDFReader = None

        self.map_data: np.ndarray = None
        self.bg_data: np.ndarray = None

        self.subtracted: bool = False
        self.cosmic_ray_removed: bool = False

        self.set_measurement('Raman')

    def clear(self):
        self.reader_raw = None
        self.reader_ref = None
        self.reader_bg = None
        self.map_data = None
        self.bg_data = None
        self.subtracted = False
        self.cosmic_ray_removed = False

    def load_raw(self, filename: str) -> bool:
        # 二次元マッピングファイルを読み込む
        self.reader_raw = RamanHDFReader(filename)
        self.xdata = self.reader_raw.xdata.copy()
        self.map_data = self.reader_raw.spectra.mean(axis=2).transpose(1, 0, 2)
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
        self.reader_ref = RamanHDFReader(filename)
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra[0][0][0])

    def load_bg(self, filename: str) -> None:
        # 背景のファイルを読み込む
        self.reader_bg = RamanHDFReader(filename)
        self.bg_data = self.reader_bg.spectra[0][0][0]

    def reset_data(self):
        # キャリブレーションを複数かけることのないよう、毎度リセットをかける
        if self.reader_raw is None or self.reader_ref is None:
            raise ValueError('Load data before reset.')
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra[0][0][0])

    def subtract_bg(self):
        if self.reader_bg is None:
            raise ValueError('Load background before subtracting.')
        if self.subtracted:
            return
        self.map_data -= self.bg_data
        self.subtracted = True

    def undo_subtract_bg(self):
        if not self.subtracted:
            return
        self.map_data += self.bg_data
        self.subtracted = False

    def remove_cosmic_ray(self, threshold):
        if self.reader_raw is None:
            raise ValueError('Load data before removing cosmic ray.')
        if self.cosmic_ray_removed:
            return
        self.map_data = remove_cosmic_ray(self.reader_raw.spectra, threshold).mean(axis=2).transpose(1, 0, 2)
        self.subtracted = False
        self.cosmic_ray_removed = True

    def undo_remove_cosmic_ray(self):
        if not self.cosmic_ray_removed:
            return
        self.map_data = self.reader_raw.spectra.mean(axis=2).transpose(1, 0, 2)
        self.subtracted = False
        self.cosmic_ray_removed = False

    def imshow(self, ax: plt.Axes, map_range: list, cmap: str) -> None:
        if self.reader_raw is None:
            raise ValueError('Load data before imshow.')
        # マッピングの表示
        extent_mapping = (
            self.x_start, self.x_start + self.x_span + self.x_pad,
            self.y_start, self.y_start + self.y_span + self.y_pad)
        map_range_idx = (map_range[0] < self.xdata) & (self.xdata < map_range[1])
        data = self.map_data[:, :, map_range_idx]
        if data.shape[2] == 0:
            return
        data = np.array([[subtract_baseline(d).sum() for d in dat] for dat in data])
        # 光学像の上にマッピングを描画
        ax.imshow(data, alpha=0.9, extent=extent_mapping, origin='lower', cmap=cmap)

    def coord2idx(self, x_pos: float, y_pos: float) -> [int, int]:
        col = round((x_pos - self.x_start) // self.x_pad)
        row = round((y_pos - self.y_start) // self.y_pad)
        return row, col

    def idx2coord(self, row: int, col: int) -> [float, float]:
        return self.x_start + self.x_pad * (col + 0.5), self.y_start + self.y_pad * (row + 0.5)

    def is_inside(self, x: float, y: float) -> bool:
        # check if the selected position is inside the mapping
        if ((self.x_start <= x <= self.x_start + self.x_span + self.x_pad)
                and (self.y_start <= y <= self.y_start + self.y_span + self.y_pad)):
            return True
        else:
            return False

    def close(self):
        if self.reader_raw is not None:
            self.reader_raw.close()
        if self.reader_ref is not None:
            self.reader_ref.close()
