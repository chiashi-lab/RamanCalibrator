from pathlib import Path
import numpy as np
from calibrator import Calibrator
from MapManager import MapInfo


# Calibratorは自作ライブラリ。Rayleigh, Raman用のデータとフィッティングの関数等が含まれている。
class CalibrationManager(Calibrator):
    def __init__(self, *args, keep_ax=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.reader_raw = None
        self.reader_ref = None

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
        pass

    def load_ref(self, p: Path) -> bool:
        pass

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
            raise ValueError('Load raw data before reset.')
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
