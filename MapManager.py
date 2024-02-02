import numpy as np
from PIL import Image
import matplotlib
from matplotlib.colors import Normalize
from dataclasses import dataclass, field
from utils import subtract_baseline


@dataclass
class MapInfo:  # マッピングの情報をまとめたクラス，複数のクラスにまたがる情報のみをまとめる
    xdata: np.ndarray
    map_data: np.ndarray
    shape: tuple
    map_origin: tuple
    map_pixel: tuple
    map_size: tuple
    img: Image
    img_origin: tuple
    img_size: tuple
    map_data_4d: np.ndarray = field(default_factory=lambda: np.array([[[[]]]]))
    map_data_mean: np.ndarray = field(default_factory=lambda: np.array([[[]]]))
    map_data_crr: np.ndarray = field(default_factory=lambda: np.array([[[]]]))


class MapManager:
    def __init__(self, keep_ax=False):
        if not keep_ax:  # reset時にaxを保持するかどうか
            self.ax: matplotlib.Axes = None
        self.axes_img: matplotlib.image.AxesImage = None
        self.axes_map: matplotlib.image.AxesImage = None
        # RenishawCalibratorから渡される情報
        self.map_info: MapInfo = None
        # マップの横軸範囲
        self.map_range: tuple = (0, 0)
        # マップの横軸範囲のプリセット
        self.map_range_list = (
            '120~250',
            '510~530',
            '1350~1380',
            '1570~1610',
            '2550~2750',
        )
        # カラーマップ
        self.cmap: str = 'hot'
        # カラーマップのリスト
        self.cmap_list = sorted(['viridis', 'plasma', 'inferno', 'magma', 'cividis',
                                 'Wistia', 'hot', 'binary', 'bone', 'cool', 'copper',
                                 'gray', 'pink', 'spring', 'summer', 'autumn', 'winter',
                                 'RdBu', 'Spectral', 'bwr', 'coolwarm', 'hsv', 'twilight',
                                 'CMRmap', 'cubehelix', 'brg', 'gist_rainbow', 'rainbow',
                                 'jet', 'nipy_spectral', 'gist_ncar'])
        # カラーマップの範囲
        self.cmap_range: tuple = (0, 0)
        # カラーマップの範囲の自動調整をするかどうか
        self.cmap_range_auto: bool = True
        # カラーマップの範囲を自動調整した結果を保存
        self.cmap_range_auto_result: tuple = (0, 0)
        # 透明度
        self.alpha: float = 1.0
        # 選択した点のインデックス
        self.row: int = 0
        self.col: int = 0
        # クロスヘア
        self.horizontal_line = None
        self.vertical_line = None
        self.show_crosshair = True
        # データが存在するかどうか
        self.is_loaded = False

    def reset(self):
        self.__init__(keep_ax=True)

    def set_ax(self, ax: matplotlib.pyplot.Axes) -> None:
        self.ax = ax

    def update_xdata(self, xdata: np.ndarray) -> None:
        # キャリブレーションによって更新されたとき
        self.map_info.xdata = xdata

    def load(self, map_info: MapInfo) -> None:
        # マッピングファイルを読み込む
        self.map_info = map_info
        self.is_loaded = True

    def clear_and_show(self) -> None:
        # マップをクリア
        self.ax.cla()
        self.ax.set_title('Raman Map', fontsize=30)
        # 光学像の表示
        self.show_optical_img()
        # ラマンマッピングの描画
        self.show_map()
        # クロスヘアの作成
        self.create_crosshair()

    def show_optical_img(self):
        # 光学像の位置、サイズを取り出す
        x0 = self.map_info.img_origin[0]
        y0 = self.map_info.img_origin[1]
        x1 = self.map_info.img_origin[0] + self.map_info.img_size[0]
        y1 = self.map_info.img_origin[1] + self.map_info.img_size[1]
        self.ax.set_xlim(x0, x1)
        self.ax.set_ylim(y1, y0)
        # 光学像を描画
        self.axes_img = self.ax.imshow(self.map_info.img, extent=(x0, x1, y1, y0))

    def _calc_map_data(self):
        if len(self.map_info.map_data.shape) != 3:
            return np.array([[]])
        # マッピングの描画に必要なデータを計算
        map_range_idx = (self.map_range[0] < self.map_info.xdata) & (self.map_info.xdata < self.map_range[1])
        data = self.map_info.map_data[:, :, map_range_idx]
        if data.shape[2] == 0:
            return np.array([[]])
        data = np.array([[subtract_baseline(d).sum() for d in dat] for dat in data])
        return data

    def show_map(self):
        # マップの位置、サイズを取り出す
        x0 = self.map_info.map_origin[0]
        y0 = self.map_info.map_origin[1]
        x1 = self.map_info.map_origin[0] + self.map_info.map_size[0]
        y1 = self.map_info.map_origin[1] + self.map_info.map_size[1]
        # マッピング作成
        data = self._calc_map_data()
        if len(data.shape) != 2:
            return
        # カラーマップ範囲
        cmap_range = (data.min(), data.max()) if self.cmap_range_auto else self.cmap_range
        # カラーマップ範囲の自動調整のために値を保存しておく
        self.cmap_range_auto_result = (data.min(), data.max())
        # 光学像の上にマッピングを描画
        self.axes_map = self.ax.imshow(
            data,
            alpha=self.alpha,
            extent=(x0, x1, y0, y1),
            origin='lower',
            cmap=self.cmap,
            norm=Normalize(vmin=cmap_range[0], vmax=cmap_range[1]))

    def update_map(self, map_range: tuple = None, cmap: str = None, cmap_range: tuple = None, cmap_range_auto: bool = None, alpha: float = None) -> [float, float]:
        if map_range is not None:  # マップ範囲の更新はマップデータの再計算が必要なので処理を分けておく
            self.map_range = map_range
            data = self._calc_map_data()
            if data.shape[1] > 0 and (self.cmap_range_auto or cmap_range_auto):  # カラーマップ範囲の自動調整のために値を保存しておく
                self.cmap_range_auto_result = (data.min(), data.max())
            self.axes_map.set(data=data)
        # カラーマップ関連の設定
        self.cmap = cmap if cmap is not None else self.cmap
        self.cmap_range = cmap_range if cmap_range is not None else self.cmap_range
        self.cmap_range_auto = cmap_range_auto if cmap_range_auto is not None else self.cmap_range_auto
        if self.cmap_range_auto or cmap_range_auto:  # カラーマップ範囲の自動調整，処理を減らすため保存されていた値を用いる
            self.cmap_range = self.cmap_range_auto_result
        self.alpha = alpha if alpha is not None else self.alpha
        self.axes_map.set(alpha=self.alpha, cmap=self.cmap, norm=Normalize(vmin=self.cmap_range[0], vmax=self.cmap_range[1]))
        return self.cmap_range

    def coord2idx(self, x_pos: float, y_pos: float) -> [int, int]:
        # 座標からインデックスに変換
        col = round((x_pos - self.map_info.map_origin[0]) // self.map_info.map_pixel[0])
        row = round((y_pos - self.map_info.map_origin[1]) // self.map_info.map_pixel[1])
        return row, col

    def idx2coord(self, row: int, col: int) -> [float, float]:
        # インデックスから座標に変換
        x = self.map_info.map_origin[0] + self.map_info.map_pixel[0] * (col + 0.5)
        y = self.map_info.map_origin[1] + self.map_info.map_pixel[1] * (row + 0.5)
        return x, y

    def is_inside(self, x: float, y: float) -> bool:
        # 選択した点がマップ範囲内か判別
        xmin, xmax = sorted([self.map_info.map_origin[0], self.map_info.map_origin[0] + self.map_info.map_size[0]])
        ymin, ymax = sorted([self.map_info.map_origin[1], self.map_info.map_origin[1] + self.map_info.map_size[1]])
        if (xmin <= x <= xmax) and (ymin <= y <= ymax):
            return True
        else:
            return False

    def set_index(self, row: int, col: int) -> None:
        # 選択した点のインデックスを設定（マップデータのインデックスから）
        if not (0 <= row < self.map_info.shape[0] and 0 <= col < self.map_info.shape[1]):
            return
        self.row = row
        self.col = col
        # クロスヘアを更新
        self.update_crosshair()

    def set_coord(self, x: float, y: float) -> None:
        # 選択した点のインデックスを設定（座標から）
        # ピクセルの中心にスナップするためset_indexを使う
        self.set_index(*self.coord2idx(x, y))

    def on_click(self, x: float, y: float) -> None:
        if not self.is_inside(x, y):
            return
        self.set_coord(x, y)

    def on_key_press(self, key: str) -> None:
        if key == 'down':
            self.row = max(self.row - 1, 0)
        elif key == 'up':
            self.row = min(self.row + 1, self.map_info.shape[0] - 1)
        elif key == 'left':
            self.col = max(self.col - 1, 0)
        elif key == 'right':
            self.col = min(self.col + 1, self.map_info.shape[1] - 1)
        else:
            return
        self.update_crosshair()

    def get_spectrum(self) -> [np.ndarray, np.ndarray]:
        # 選択した点のスペクトルを取得
        return self.map_info.xdata, self.map_info.map_data[self.row, self.col]

    def create_crosshair(self) -> None:
        self.horizontal_line = self.ax.axhline(color='k', lw=2, ls=(0, (5, 5)), gapcolor='w')
        self.vertical_line = self.ax.axvline(color='k', lw=2, ls=(0, (5, 5)), gapcolor='w')
        self.update_crosshair()

    def update_crosshair(self) -> None:
        # マッピング上のクロスヘアを移動
        x, y = self.idx2coord(self.row, self.col)
        self.horizontal_line.set_ydata(y)
        self.vertical_line.set_xdata(x)

        if self.show_crosshair:
            self.horizontal_line.set_visible(True)
            self.vertical_line.set_visible(True)
        else:
            self.horizontal_line.set_visible(False)
            self.vertical_line.set_visible(False)
