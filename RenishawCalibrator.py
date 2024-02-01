import numpy as np
from PIL import Image
from renishawWiRE import WDFReader
from calibrator import Calibrator
from MapManager import MapInfo


def subtract_baseline(data: np.ndarray):
    baseline = np.linspace(data[0], data[-1], data.shape[0])
    return data - baseline


def column_to_row(data: np.ndarray):
    # change data from column major to row major
    data_new = np.zeros_like(data)
    for i1 in range(data.shape[0]):
        for j1 in range(data.shape[1]):
            index = i1 * data.shape[1] + j1
            i2 = index % data.shape[0]
            j2 = index // data.shape[0]
            data_new[i2, j2] = data[i1, j1]
    return data_new


# Calibratorは自作ライブラリ。Rayleigh, Raman用のデータとフィッティングの関数等が含まれている。
class RenishawCalibrator(Calibrator):
    def __init__(self, *args, keep_ax=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.reader_raw: WDFReader = None
        self.reader_ref: WDFReader = None

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

    def load_raw(self, filename: str) -> [bool, MapInfo]:
        # 二次元マッピングファイルを読み込む
        self.reader_raw = WDFReader(filename)
        map_data = self.reader_raw.spectra
        # 点測定データの場合は3次元にreshapeする
        if len(map_data.shape) == 1:
            map_info = MapInfo(
                xdata=self.reader_raw.xdata,
                map_data=map_data.reshape(1, 1, -1),
                shape=(1, 1),
                map_origin=(0, 0),
                map_pixel=(1, 1),
                map_size=(1, 1),
                img=Image.new('RGB', (1, 1), (200, 200, 200)),
                img_origin=(-0.1, -0.1),
                img_size=(1.2, 1.2),
            )
            return True, map_info
        # マップ測定なら(x座標) x (y座標) x (スペクトル) の3次元のはず．そうでなければエラー
        if len(map_data.shape) != 3:
            return False, None
        # WiREのデータはcolumn majorなので、row majorに変換する，MATLABが全て悪い
        map_data = column_to_row(map_data)
        map_info = MapInfo(
            xdata=self.reader_raw.xdata,
            map_data=map_data,
            shape=self.reader_raw.spectra.shape[:2],
            map_origin=(self.reader_raw.map_info['x_start'], self.reader_raw.map_info['y_start']),
            map_pixel=(self.reader_raw.map_info['x_pad'], self.reader_raw.map_info['y_pad']),
            map_size=(self.reader_raw.map_info['x_span'], self.reader_raw.map_info['y_span']),
            img=Image.open(self.reader_raw.img),
            img_origin=self.reader_raw.img_origins,
            img_size=self.reader_raw.img_dimensions,
        )
        return True, map_info

    def load_ref(self, filename: str) -> bool:
        # 標準サンプルのファイルを読み込む
        self.reader_ref = WDFReader(filename)
        if len(self.reader_ref.spectra.shape) == 3:  # when choose 2D data for reference
            self.reader_ref.spectra = self.reader_ref.spectra[0][0]  # TODO: allow user to choose
            print('Warning: Reference file contains multiple spectra. Only the first one is used.')
        if not self.is_xdata_correct():
            return False
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra)
        self.is_ref_loaded = True
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
