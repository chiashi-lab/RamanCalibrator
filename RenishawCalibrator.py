from pathlib import Path
from PIL import Image
from renishawWiRE import WDFReader
from CalibrationManager import CalibrationManager
from MapManager import MapInfo
from utils import column_to_row


# Calibratorは自作ライブラリ。Rayleigh, Raman用のデータとフィッティングの関数等が含まれている。
class RenishawCalibrator(CalibrationManager):
    def __init__(self, *args, keep_ax=False, **kwargs):
        super().__init__(*args, keep_ax=keep_ax, **kwargs)
        self.reader_raw: WDFReader | None = None
        self.reader_ref: WDFReader | None = None

    def load_raw(self, p: Path) -> [bool, MapInfo]:
        # 二次元マッピングファイルを読み込む
        self.reader_raw = WDFReader(p)
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

    def load_ref(self, p: Path) -> bool:
        # 標準サンプルのファイルを読み込む
        self.reader_ref = WDFReader(p)
        if len(self.reader_ref.spectra.shape) == 3:  # when choose 2D data for reference
            self.reader_ref.spectra = self.reader_ref.spectra[0][0]  # TODO: allow user to choose
            print('Warning: Reference file contains multiple spectra. Only the first one is used.')
        if not self.is_xdata_correct():
            return False
        self.set_data(self.reader_ref.xdata, self.reader_ref.spectra)
        self.is_ref_loaded = True
        return True
