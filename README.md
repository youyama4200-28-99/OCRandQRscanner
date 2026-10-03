# SmartScan for Windows

Webカメラ映像からQRコードと文字を自動判別する、Windows 10/11向けPythonデスクトップアプリです。

## 主な機能

- QRコードを優先検出し、見つからない場面ではOCRへ自動切替
- PaddleOCRによる日本語・英数字の文字認識
- OpenVINO `AUTO`デバイス上の軽量エッジ推論で、OCRをかける価値のあるフレームだけを選別
- OCRはCPUスレッド数を制限した別プロセスで実行し、カメラ表示への影響を抑制
- 認識文字列の表示、コピー、クリア
- 接続されている複数カメラのバックグラウンド検索と画面上での切替
- カメラ取得を専用スレッドで行い、画面側は待たずに最新フレームを30Hzで描画
- カメラの不均一な到着間隔でも取りこぼさないよう、画面側は目標FPSの4倍の周期で新着フレームを確認
- QR検出とOpenVINOゲート推論を専用ワーカースレッドへ分離し、プレビュー描画を待たせない
- モード表示の再描画と画像コピーを必要時だけに抑え、UI更新コストを削減
- OpenCV側で表示寸法へ直接縮小し、Qt側の色変換とPixmap拡縮を省略
- 起動・カメラ・推論時間・停止箇所を記録するローテーションログ
- カメラ番号・解像度・認識間隔・言語・閾値をJSONで設定
- カメラ画像や認識結果をディスクへ保存しないプライバシー優先設計

## 必要環境

- Windows 10/11 64-bit
- Python 3.10〜3.13 64-bit（3.13で開発）
- Webカメラ
- 初回OCR時にモデルを取得できるインターネット接続

## セットアップ

PowerShellでリポジトリ直下から実行します。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\run.ps1
```

初回のOCRはPaddleOCRモデルのダウンロードと初期化のため時間がかかります。以降はローカルキャッシュが使われます。
モデルはリポジトリ直下の`.cache/paddlex`（Git管理外）に保存されます。Windows CPUでのPP-OCRv6互換性を優先し、PaddleOCR側のoneDNNは無効化しています。

## 診断とテスト

```powershell
.\.venv\Scripts\python.exe -m smartscan --diagnose
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## ログ

通常のログは`%LOCALAPPDATA%\SmartScan\logs\smartscan.log`へ保存されます。OCRワーカーのログは同じ場所の`smartscan-ocr-worker.log`です。画面右側の「ログフォルダーを開く」から直接確認できます。各ログは5 MBごとに切り替わり、過去5ファイルまで保持します。

次の内容を記録します。

- 起動、設定読込、終了
- カメラの接続・切断・連続読取失敗
- OpenVINOとPaddleOCRの初期化時間、推論時間、例外
- UI処理が3秒以上戻らなかった場合の停止候補箇所
- QR/OCR結果の件数と平均信頼度

カメラ画像と認識文字列そのものはログへ保存しません。詳細調査時は`--log-level DEBUG`、保存先を変える場合は`--log-dir <フォルダー>`を指定できます。

## Windows EXEの作成（PyInstaller）

依存環境をセットアップした後、次を実行します。

```powershell
.\scripts\build.ps1
```

出力は`dist\SmartScan\SmartScan.exe`です。`config\settings.json`もEXEの隣へコピーされるため、配布後も設定を変更できます。AIランタイムのDLL競合を避ける専用specとフックを`packaging`に用意しています。

ビルド後には、生成したEXE自身でOpenVINO、QR、PaddleOCRの実推論テストが自動実行されます。テストを省略する場合は`-SkipSmokeTest`、ZIPも作る場合は`-Archive`を指定します。

```powershell
.\scripts\build.ps1 -Archive
```

標準は`onedir`形式です。フォルダ内の`_internal`やDLLを削除せず、`SmartScan`フォルダ単位で配布してください。OCRモデルは初回利用時に`%LOCALAPPDATA%\SmartScan\paddlex`へダウンロードされます。

## 設定

設定は [config/settings.json](config/settings.json) にあります。日本語は`japan`、英語は`en`です。`openvino_device`は通常`AUTO`を使い、固定する場合は`CPU`、`GPU`、`NPU`を指定します。`ocr_cpu_threads`はOCRワーカーが使うCPUスレッド数、`ocr_interval_seconds`はOCR完了後の待機秒数、`qr_max_width`はQR検出用縮小画像の最大幅です。`camera.scan_max_index`は画面の「再検索」で確認するカメラインデックスの上限、`ui.preview_max_width`は認識解像度を変えずに画面へ転送するプレビューの最大幅です。

起動後、利用可能なカメラは画面右側のプルダウンから切り替えられます。「再検索」を押すと、現在使用中のカメラを維持したままバックグラウンドで再検出します。画面での選択は現在の起動中だけ有効です。次回起動時の既定値は`camera.index`で指定します。

WindowsではMedia Foundationを優先し、初期化失敗時は一度再試行してからDirectShow＋MJPEGへフォールバックします。Media Foundationのハードウェア変換は、仮想カメラとの初期化を安定させるため無効化しています。画面右側の「プレビュー」表示とログの`Camera capture rate`で実測FPSを確認できます。カメラが要求した解像度・FPSに対応していない場合、実測値はデバイス側の上限になります。

## 自動切替ルール

1. QRを縮小画像で優先探索します。
2. QR検出時は即座にQRモードへ移り、短時間保持します。
3. QRがなければOpenVINOで文字エッジスコアを推論します。
4. スコアが閾値以上ならOCRモードへ移り、別プロセスでPaddleOCRを実行します。
5. OCR完了後は設定されたクールダウン時間を置き、連続実行を防ぎます。
6. どちらにも該当しなければ探索モードになります。

## Gitブランチ

- `main`: 検証済みの配布可能コード
- `debug`: 実装・デバッグ・統合試験
- `management`: CI、依存更新、ドキュメントなどの管理作業

詳細は [docs/BRANCHING.md](docs/BRANCHING.md) を参照してください。

## ライセンス

SmartScanのソースコードは[MIT License](LICENSE)で公開しています。依存ライブラリと
初回起動時に取得するOCRモデルには、それぞれのライセンスが適用されます。詳細は
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を参照してください。

Windows版はQt/PySide6をLGPL-3.0条件で動的に読み込む`onedir`形式です。配布時は
`SmartScan.exe`だけを取り出さず、ライセンス文書と交換可能なQt DLLを含む
`SmartScan`フォルダー全体を配布してください。

## 注意事項

- GPU/NPU利用には対応するIntelドライバーが必要です。利用できない場合、`AUTO`は通常CPUへフォールバックします。
- QRだけはOCR初期化前でも利用できます。OpenVINOまたはPaddleOCRの初期化失敗は画面に表示されます。
