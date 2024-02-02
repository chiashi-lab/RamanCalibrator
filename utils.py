import numpy as np


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


def is_num(s):
    try:
        float(s)
    except ValueError:
        return False
    else:
        return True
