# About
Renishaw inVia顕微ラマンで測定した **.wdf** データまたは488Ramanで測定した **.hdf5** データのキャリブレーションができます．\
488Ramanのデータに関してはバックグラウンドの引き算，宇宙線除去も可能です．
Python3.10に対応しています．

# Installation(Windows)
```commandline
git clone https://github.com/chiashi-lab/RamanCalibrator.git
cd RamanCalibratior
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

# 起動
```commandline
venv\Scripts\activate
python main.py
```
またはrun.batをダブルクリック

# Usage
- ファイルをドラッグ&ドロップで読み込みます.
  - Renishaw
    - 上： キャリブレーションするデータ
    - 下： リファレンスデータ
  - 488Raman（キャリブレーションするデータを読み込むとモードが変わります）
    - 上： キャリブレーションするデータ
    - 中： リファレンスデータ
    - 下： バックグラウンドデータ
- 画面左のマッピングをクリックまたは矢印キーを押してスペクトルを確認します.
- キャリブレーションのための参照物質を選択します.
  - ['sulfur', 'naphthalene', 'acetonitrile']から選択できます.
- **CALIBRATE**を押します.
  - キャリブレーションの結果が右下のグラフに表示されます.
- **ADD**を押してダウンロードするデータを追加します.
  - 追加したインデックスがボックスに表示されます.
  - 右クリックで削除できます.
  - **SAVE**を押すとデータが保存されます.