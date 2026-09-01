# 管理チェックリスト

この文書は`management`ブランチで管理する。

- 四半期ごとに依存ライブラリのWindows/Python対応範囲を確認する。
- バージョン更新時は`pip check`、Ruff、全テスト、OpenVINO診断を実行する。
- PaddleOCR更新時は日本語モデルを再取得し、実画像でoneDNN互換性を確認する。
- OpenVINO更新時は`AUTO`、`CPU`と、利用可能なら`GPU`/`NPU`を確認する。
- リリース前に複数カメラ番号、QR連続検出、OCR切替、終了処理を実機確認する。
