from pathlib import Path
import numpy as np
from PIL import Image
from dataloader import RamanHDFReader, RamanHDFWriter
from calibrator import Calibrator
from MapManager import MapInfo


def subtract_baseline(data: np.ndarray):
    baseline = np.linspace(data[0], data[-1], data.shape[0])
    return data - baseline


def remove_cosmic_ray(spectra: np.ndarray, threshold: float):
    mean = spectra.mean(axis=2)
    std = spectra.std()
    deviation = (spectra - mean[:, :, np.newaxis, :]) / std
    mask = np.where(deviation > threshold, 0, 1)
    spectra_removed = spectra * mask
    spectra_average = spectra_removed.sum(axis=2)[:, :, np.newaxis, :] / mask.sum(axis=2)[:, :, np.newaxis, :] * (1 - mask)
    return spectra_removed + spectra_average


class Raman488DataProcessor:
    def __init__(self, map_info: MapInfo = None):
        self.map_info: MapInfo = map_info
        self.bg_data: np.ndarray = None

        if map_info is not None:
            # TODO: thresholdを指定可能に
            # 宇宙線除去データを生成しておく
            self.map_info.map_data_crr = remove_cosmic_ray(self.map_info.map_data_4d, 0.01).mean(axis=2).transpose(1, 0, 2)
            self.map_info.map_data_mean = self.map_info.map_data_4d.mean(axis=2).transpose(1, 0, 2)

    def reset(self):
        self.__init__()

    def load_bg(self, p: Path) -> None:
        # 背景のファイルを読み込む
        reader_bg = RamanHDFReader(p)
        bg_data = reader_bg.spectra.copy()
        reader_bg.close()
        if bg_data.shape[2] < 3:
            self.bg_data = bg_data.mean(axis=0)[0][0]
        else:  # 3回以上の積算があるなら宇宙線除去を行う
            self.bg_data = remove_cosmic_ray(bg_data, 0.2).mean(axis=2)[0][0]

    def set_processed_data(self, is_bg_subtracted: bool, is_cosmic_ray_removed: bool) -> None:
        if is_cosmic_ray_removed:
            data = self.map_info.map_data_crr
        else:
            data = self.map_info.map_data_mean
        if is_bg_subtracted:
            data = data - self.bg_data
        self.map_info.map_data = data


# Calibratorは自作ライブラリ。Rayleigh, Raman用のデータとフィッティングの関数等が含まれている。
class Raman488Calibrator(Calibrator):
    def __init__(self, *args, keep_ax=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.reader_raw: RamanHDFReader = None
        self.reader_ref: RamanHDFReader = None

        self.processor = Raman488DataProcessor()

        self.is_ref_loaded = False

        if not keep_ax:  # reset時にaxを保持するかどうか
            self.ax = None

        self.set_measurement('Raman')

    def reset(self):
        if self.ax is not None:
            self.ax.cla()
            self.ax.set_title('Reference Spectrum', fontsize=30)
        self.__init__(keep_ax=True)

    def reset_ref(self):
        if self.reader_raw is not None:
            self.reader_raw.close()
        self.reader_ref = None
        self.is_ref_loaded = False
        self.is_calibrated = False

    def set_ax(self, ax):
        self.ax = ax

    def load_raw(self, p: Path) -> [bool, MapInfo]:
        # 二次元マッピングファイルを読み込む
        self.reader_raw = RamanHDFReader(p)
        self.xdata = self.reader_raw.xdata.copy()
        map_data_4d = self.reader_raw.spectra  # 宇宙線除去処理のために4次元でとっておく
        map_data = map_data_4d.mean(axis=2).transpose(1, 0, 2)
        map_info = MapInfo(
            xdata=self.reader_raw.xdata,
            map_data=map_data,
            shape=map_data.shape[:2],
            map_origin=(self.reader_raw.map_info['x_start'], self.reader_raw.map_info['y_start']),
            map_pixel=(self.reader_raw.map_info['x_pad'], self.reader_raw.map_info['y_pad']),
            map_size=(self.reader_raw.map_info['x_span'], self.reader_raw.map_info['y_span']),
            img=Image.new('RGB', (int(self.reader_raw.map_info['x_span']), int(self.reader_raw.map_info['y_span'])), (200, 200, 200)),
            img_origin=(self.reader_raw.map_info['x_start'], self.reader_raw.map_info['y_start'] + self.reader_raw.map_info['y_span']),  # Renishaw側に合わせるため
            img_size=(self.reader_raw.map_info['x_span'], -self.reader_raw.map_info['y_span']),
            map_data_4d=map_data_4d,
        )
        return True, map_info

    def load_ref(self, p: Path) -> bool:
        # 標準サンプルのファイルを読み込む
        self.reader_ref = RamanHDFReader(p)
        if self.reader_ref.spectra.shape[0] > 1 or self.reader_ref.spectra.shape[1] > 1:
            print('Warning: Reference file contains multiple spectra. Only the first one is used.')
        if not self.is_xdata_correct():
            return False
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra[0][0][0])
        self.is_ref_loaded = True
        return True

    def is_xdata_correct(self):  # Raman488では意味ないが一応
        if self.reader_raw is None:
            return True
        # xdataが同じかどうか確認する
        if not np.all(self.reader_raw.xdata == self.reader_ref.xdata):
            return False
        return True

    def reset_data(self):
        # キャリブレーションを複数かけることのないよう、毎度リセットをかける
        if self.reader_raw is None or self.reader_ref is None:
            raise ValueError('Load raw data before reset.')
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra[0][0][0])

    def plot(self):
        self.ax.cla()
        self.ax.set_title('Reference Spectrum', fontsize=30)
        self.ax.autoscale(True)
        if self.is_calibrated:
            self.show_result()
        else:
            self.show_spectrum()

    def show_spectrum(self):
        self.ax.plot(self.xdata, self.ydata, label=self.material, color='k', linewidth=1)
        self.ax.legend(fontsize=15)

    def show_result(self) -> None:
        super().show_fit_result(self.ax)

    def close(self):
        if self.reader_raw is not None:
            self.reader_raw.close()
        if self.reader_ref is not None:
            self.reader_ref.close()
