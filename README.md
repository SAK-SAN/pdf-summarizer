# 🎓 論文解析 & Notionコピペツール (Paper Analyzer & Notion Copier)

Gemini APIのマルチモーダル機能（File API）を活用し、アップロードされた学術論文PDFを直接解析して、Notionへそのまま貼り付けられる構造化された解説文を生成するStreamlitアプリケーションです。

## ✨ 特徴

- **自動モデルアップデート（動的フェッチ）**: 起動時にGemini APIから現在利用可能なモデル一覧（`gemini-1.5`、`gemini-2.5`、将来の新モデルなど）を自動取得し、セレクトボックスへ反映します。モデルのバージョンが変わってもアプリのコード変更は不要です。
- **Notion特化型フォーマット**: 専門外の初心者でも理解できるように専門用語の補足説明を付け加えつつ、論文を「研究目的」や「提案内容」など8項目に分かりやすく構造化します。
- **ハイブリッドUI（個別＆一括コピペ）**: 各項目ごとに個別にコピーできるタブと、Notionのページへ一発で貼り付けられる「見出し（#）付き一括コピー用コードブロック」を提供するタブの2つを搭載しています。
- **完全な同期・セッション状態管理**: Streamlitのセッション状態（`st.session_state`）を利用し、AIの生成が100%完了したタイミングで確定データを画面に描写。操作やタブ切り替えによる画面のチラつきやデータの消失、APIへの無駄な再リクエストを防ぎます。

## 🛠 必要条件

- Python 3.9 以上
- Gemini API キー

## 🚀 セットアップ

### 1. リポジトリのクローン
```bash
git clone [https://github.com/YOUR_GITHUB_ID/paper-analyzer-notion.git](https://github.com/YOUR_GITHUB_ID/paper-analyzer-notion.git)
cd paper-analyzer-notion
```

### 2. 依存ライブラリのインストール
```bash
pip install -r requirements.txt
```

### 3. 環境変数の設定
プロジェクトのルートディレクトリに `.env` ファイルを作成し、以下のようにご自身のGemini APIキーを記述してください。

```text
GEMINI_API_KEY="あなたのGemini_APIキー"
```
#### 🌐 Streamlit Community Cloudへのデプロイ時
Web上に公開する場合は、デプロイ先の管理画面にある **Advanced settings -> Secrets** に、TOML形式で以下のように登録してください。

```toml
GEMINI_API_KEY = "あなたのGemini_APIキー"
```

## 🏃‍♂️ 起動方法

以下のコマンドを実行して、ローカルサーバーを起動します。

```bash
streamlit run app.py
```
起動後、ブラウザで `http://localhost:8501` に自動アクセスされます。

## 📂 プロジェクト構成

```text
paper-analyzer-notion/
│
├── .env                  # ローカル開発用の環境変数ファイル（Git管理外）
├── .gitignore            # GitHubにコミットしないファイルを指定
├── README.md             # 本ドキュメント
├── requirements.txt      # 外部ライブラリ一覧
└── app.py                # アプリケーション本体
```

## 📄 免責事項

- 本ツールはGemini APIを利用します。APIの利用量に応じた料金、または無料枠のクォータ制限（1分あたりのリクエスト数やモデルごとの制限）に注意してください。
- アップロードされたPDFファイルは処理完了後にAPIセッションおよびローカルの一時フォルダから自動的に削除されます。
