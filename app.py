import streamlit as st
import google.generativeai as genai
import os
import tempfile
import time
import requests
from dotenv import load_dotenv

# 1. 環境変数の読み込みとAPIキーの取得
load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")

# 【重要】APIから利用可能なGeminiモデルを動的に取得する関数
def get_gemini_models(api_key):
    try:
        # モデル一覧を取得するAPIエンドポイント
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        res = requests.get(list_url)
        if res.status_code == 200:
            data = res.json()
            # 取得したモデルの中から、テキスト生成（generateContent）に対応しているものだけを抽出
            models = [
                m["name"] for m in data.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            return models
        else:
            return []
    except Exception:
        return []

# 2. ページの基本設定
st.set_page_config(page_title="PDF構造化要約ツール", layout="centered", page_icon="📄")
st.title("📄 PDF構造化要約ツール")
st.write("PDFを直接AIにアップロードし、指定した役割（ペルソナ）に応じた高品質な要約を生成します。")

# APIキーの存在チェックと初期化
if not api_key:
    st.error("🔑 APIキーが設定されていません。ローカル環境では `.env` ファイル、Streamlit Cloudでは `Secrets` を設定してください。")
    st.stop()

genai.configure(api_key=api_key)

# 3. サイドバーによるモデル切り替え（動的フェッチ実装）
st.sidebar.title("🛠 アプリ設定")

with st.sidebar:
    with st.spinner("利用可能なGeminiモデルをAPIから確認中..."):
        available_models = get_gemini_models(api_key)
    
    if available_models:
        # 新しいモデル（例: gemini-2.5-flash や gemini-1.5-flash）を自動で初期選択にするロジック
        default_index = 0
        for i, m in enumerate(available_models):
            if "gemini-2.5-flash" in m:
                default_index = i
                break
            elif "gemini-1.5-flash" in m:
                default_index = i
        
        model_choice = st.selectbox(
            "使用するAIモデルを選択してください（APIから自動取得）",
            options=available_models,
            index=default_index,
            help="APIから現在利用可能なすべてのモデルを動的に取得しています。バージョンが新しくなっても自動でここに表示されます。"
        )
    else:
        st.warning("モデル一覧の取得に失敗しました。デフォルトのモデル名を使用します。")
        model_choice = "models/gemini-1.5-flash"

# 4. ユーザー入力エリア
uploaded_file = st.file_uploader("PDFファイルを選択（アップロード）してください", type=["pdf"])

user_role_prompt = st.text_area(
    "AIに与える役割や追加の指示（ペルソナ指定など）",
    placeholder="例：技術マーケターの視点で、新規性とビジネスへの影響を中心に要約してください。箇条書きを多めでお願いします。",
    height=100
)

# 5. メイン処理ロジック
if st.button("要約を生成する", type="primary", disabled=not uploaded_file):
    with st.spinner("AIがPDFを解析しています。しばらくお待ちください..."):
        try:
            # Streamlitのメモリ上のバイナリを、Gemini File APIへ渡すため一時ファイルに書き出す
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            # GeminiのFile APIを利用してPDFを直接アップロード（マルチモーダル処理）
            st.info("ファイルをGemini APIの処理セッションへ転送中...")
            gemini_file = genai.upload_file(path=tmp_path, mime_type="application/pdf")
            
            # ファイルの処理完了（ACTIVE状態）をバックグラウンドで待機する
            while gemini_file.state.name == "PROCESSING":
                time.sleep(2)
                gemini_file = genai.get_file(gemini_file.name)

            if gemini_file.state.name == "FAILED":
                raise ValueError("Gemini API上でのPDF解析・前処理に失敗しました。")

            # プロンプトの組み立て
            base_prompt = """
            与えられたPDFファイルの内容を深く解析し、以下の構成で構造化された要約を出力してください。
            
            # 構成案
            1. 概要（全体で何を伝えているか）
            2. 重要なキーポイント（箇条書き）
            3. 特筆すべき新規性や知見
            
            ※出力はすべて日本語で行い、Markdown形式で綺麗に整えてください。
            """
            
            if user_role_prompt.strip():
                base_prompt += f"\n\n【追加の指示・ペルソナ】\n{user_role_prompt}"

            # 動的に選択されたモデルを呼び出して生成
            model = genai.GenerativeModel(model_name=model_choice)
            response = model.generate_content([gemini_file, base_prompt])

            st.success("🎉 要約の生成が完了しました！")
            
            # 6. 出力デザイン（可読性とコピーのしやすさを両立）
            st.subheader("📝 生成された要約")
            st.markdown(response.text)
            
            st.divider()
            
            # st.codeブロックを配置することで、右上に「一発コピーボタン」が自動出現する
            st.write("👇 以下のコードブロック右上にあるボタンから、Markdownテキストを一発でコピーできます")
            st.code(response.text, language="markdown")

            # 7. クリーンアップ処理（クラウド側とローカル一時ファイルの削除）
            genai.delete_file(gemini_file.name)
            os.unlink(tmp_path)

        except Exception as e:
            st.error(f"❌ 処理中にエラーが発生しました: {str(e)}")