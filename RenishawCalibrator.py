import json
import numpy as np
from scipy.special import wofz
from scipy.signal import find_peaks
from scipy.optimize import curve_fit
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import PIL
import matplotlib.pyplot as plt
from renishawWiRE import WDFReader


def voigt(xval, *params):
    center, intensity, lw, gw, baseline = params
    # lw : HWFM of Lorentzian
    # gw : sigma of Gaussian
    z = (xval - center + 1j*lw) / (gw * np.sqrt(2.0))
    w = wofz(z)
    model_y = w.real / (gw * np.sqrt(2.0*np.pi))
    intensity /= model_y.max()
    return intensity * model_y + baseline


def is_wdf(filename):
    extension = filename.split('.')[-1]
    if extension == 'wdf':
        return True
    else:
        return False


class RenishawCalibrator:
    def __init__(self):
        with open('./data/reference.json', 'r') as f:
            self.database = json.load(f)
        self.reader_raw: WDFReader = None
        self.reader_ref: WDFReader = None
        self.material: str = None
        self.pf: PolynomialFeatures = None
        self.lr: LinearRegression = None

        self.fitted_x_ref = None
        self.found_x_ref_true = None

        self.xdata: np.ndarray = None
        self.ydata: np.ndarray = None

        self.calibration_info = []

    def load_raw(self, filename):
        if not is_wdf(filename):
            print('Only .wdf file is acceptable.')
            return
        self.reader_raw = WDFReader(filename)
        self.xdata = self.reader_raw.xdata
        self.ydata = self.reader_raw.spectra
        self.shape = self.ydata.shape[:2]
        self.x_start = self.reader_raw.map_info['x_start']
        self.y_start = self.reader_raw.map_info['y_start']
        self.x_pad = self.reader_raw.map_info['x_pad']
        self.y_pad = self.reader_raw.map_info['y_pad']
        self.x_span = self.reader_raw.map_info['x_span']
        self.y_span = self.reader_raw.map_info['y_span']

    def load_ref(self, filename, material=None):
        if not is_wdf(filename):
            print('Only .wdf file is acceptable.')
            return
        self.reader_ref = WDFReader(filename)
        if material is not None:
            self.set_material(material)

    def set_material(self, material):
        if material not in ['sulfur', 'naphthalene', 'acetonitrile']:
            raise ValueError('Unsupported material.')
        self.material = material

    def find_peaks(self):
        x_ref = self.reader_ref.xdata
        y_ref = self.reader_ref.spectra

        x_ref_true = np.array(self.database[self.material])
        x_ref_true = x_ref_true[(x_ref_true > x_ref.min()) & (x_ref_true < x_ref.max())]  # crop
        search_ranges = [[x-15, x+15] for x in x_ref_true]

        fitted_x_ref = []
        found_x_ref_true = []
        for x_ref_true, search_range in zip(x_ref_true, search_ranges):
            # Crop
            partial = (search_range[0] < x_ref) & (x_ref < search_range[1])
            x_ref_partial = x_ref[partial]
            y_ref_partial = y_ref[partial]

            # Begin with finding the maximum position
            found_peaks, properties = find_peaks(y_ref_partial, prominence=50)
            if len(found_peaks) != 1:
                print('Some peaks were not detected.')
                continue

            # Fit with Voigt based on the found peak
            p0 = [x_ref_partial[found_peaks[0]], y_ref_partial[found_peaks[0]], 3, 3, y_ref_partial.min()]

            popt, pcov = curve_fit(voigt, x_ref_partial, y_ref_partial, p0=p0)

            fitted_x_ref.append(popt[0])
            found_x_ref_true.append(x_ref_true)

        # if no peak found
        if len(fitted_x_ref) == 0:
            print('Training failed.')
            return

        self.fitted_x_ref = np.array(fitted_x_ref)
        self.found_x_ref_true = np.array(found_x_ref_true)

    def train(self, dimension: int):
        self.pf = PolynomialFeatures(degree=dimension)
        fitted_x_ref_poly = self.pf.fit_transform(self.fitted_x_ref.reshape(-1, 1))

        # Train the linear model
        self.lr = LinearRegression()
        self.lr.fit(fitted_x_ref_poly, np.array(self.found_x_ref_true).reshape(-1, 1))

    def show_fit_result(self, ax):
        ax.plot(self.reader_ref.xdata, self.reader_ref.spectra, color='k')
        ymin, ymax = plt.ylim()

        for fitted_x in self.fitted_x_ref:
            plt.vlines(fitted_x, ymin, ymax, color='r', linewidth=1)

    def calibrate(self, dimension: int):
        self.find_peaks()
        self.train(dimension)
        x_raw = self.reader_raw.xdata
        x = self.pf.fit_transform(x_raw.reshape(-1, 1))
        self.xdata = np.ravel(self.lr.predict(x))

        self.calibration_info.append([self.material, dimension, self.found_x_ref_true])

    def imshow(self, ax, map_range, cmap):
        img_x0, img_y0 = self.reader_raw.img_origins
        img_w, img_h = self.reader_raw.img_dimensions
        img = PIL.Image.open(self.reader_raw.img)
        extent = (img_x0, img_x0 + img_w, img_y0 + img_h, img_y0)

        ax.set_xlim([img_x0, img_x0 + img_w])
        ax.set_ylim([img_y0 + img_h, img_y0])

        ax.imshow(img, extent=extent)

        extent = (self.x_start, self.x_start + self.x_span, self.y_start, self.y_start + self.y_span)

        map_range_idx = (map_range[0] < self.xdata) & (self.xdata < map_range[1])
        data = self.ydata[:, :, map_range_idx]
        if data.shape[2] == 0:
            return
        data = data.sum(axis=2) - data.mean(axis=2)
        data = data.reshape(data.shape[::-1]).T

        ax.imshow(data, alpha=0.9, extent=extent, origin='lower', cmap=cmap)

    def col2row(self, row, col):
        idx = col * self.shape[0] + row
        # row major
        row = idx // self.shape[1]
        col = idx % self.shape[1]

        return row, col

    def row2col(self, row, col):
        idx = row * self.shape[1] + col
        # row major
        col = idx // self.shape[0]
        row = idx % self.shape[0]

        return row, col

    def coord2idx(self, x_pos, y_pos):
        # column major
        col = int((x_pos - self.x_start) // self.x_pad)
        row = int((y_pos - self.y_start) // self.y_pad)

        return self.col2row(row, col)

    def idx2coord(self, row, col):
        row, col = self.row2col(row, col)
        return self.x_start + self.x_pad * (col + 0.5), self.y_start + self.y_pad * (row + 0.7)


def main():
    rc = RenishawCalibrator()
    # rc.load_raw('/Users/kanedaryoutarou/Library/CloudStorage/GoogleDrive-rkaneda896@g.ecc.u-tokyo.ac.jp/マイドライブ/kaneda/Data_M1/221226/Raman/x50_532_2300.wdf')
    # rc.load_ref('/Users/kanedaryoutarou/Library/CloudStorage/GoogleDrive-rkaneda896@g.ecc.u-tokyo.ac.jp/マイドライブ/kaneda/Data_M1/221226/Raman/acetonitrile_2300.wdf', 'acetonitrile')
    rc.load_raw('/Users/kanedaryoutarou/Library/CloudStorage/GoogleDrive-rkaneda896@g.ecc.u-tokyo.ac.jp/マイドライブ/kaneda/Data_M1/221226/Raman/x50_532_1000.wdf')
    rc.load_ref('/Users/kanedaryoutarou/Library/CloudStorage/GoogleDrive-rkaneda896@g.ecc.u-tokyo.ac.jp/マイドライブ/kaneda/Data_M1/221226/Raman/naphthalene_1000.wdf', 'naphthalene')
    rc.calibrate(3)


if __name__ == '__main__':
    main()
