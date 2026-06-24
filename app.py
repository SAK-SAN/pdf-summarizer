import streamlit as st
import google.generativeai as genai
import os
import tempfile
import time
from dotenv import load_dotenv

# 1. 環境変数の読み込みとAPIキーの取得
load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")

# 2. ページの基本設定
st.set_page_config(page_title="PDF構造化要約ツール", layout="centered", page_icon="📄")
st.title("📄 PDF構造化要約ツール")
st.write("PDFを直接AIにアップロードし、指定した役割に応じた高品質な要約を生成します。")

# APIキーの存在チェックと初期化
if not api_key:
    st.error("🔑 APIキーが設定されていません。ローカル環境では `.env` ファイル、Streamlit Cloudでは `Secrets` を設定してください。")
    st.stop()

genai.configure(api_key=api_key)

# 3. サイドバーによるモデル切り替え
st.sidebar.title("🛠 アプリ設定")
model_choice = st.sidebar.selectbox(
    "使用するAIモデルを選択してください",
    options=["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.5-pro"],
    index=0,
    help="通常の要約には高速な flash、深い論文解釈には pro が推奨されます。"
)

# 4. ユーザー入力エリア
uploaded_file = st.file_uploader("PDFファイルを選択（アップロード）してください", type=["pdf"])

user_role_prompt = st.text_area(
    "AIに与える役割や追加の指示（任意）",
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

            # GeminiのFile APIを利用してPDFをアップロード
            st.info("ファイルをGemini APIのセッションへ転送中...")
            gemini_file = genai.upload_file(path=tmp_path, mime_type="application/pdf")
            
            # ファイルの処理完了（ACTIVE状態）を待機する（非同期エラーハンドリング）
            while gemini_file.state.name == "PROCESSING":
                time.sleep(2)
                gemini_file = genai.get_file(gemini_file.name)

            if gemini_file.state.name == "FAILED":
                raise ValueError("Gemini API上でのPDF解析に失敗しました。")

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

            # モデルの呼び出しと生成
            model = genai.GenerativeModel(model_name=model_choice)
            response = model.generate_content([gemini_file, base_prompt])

            st.success("🎉 要約の生成が完了しました！")
            
            # 6. 出力デザイン（可読性とコピーのしやすさを両立）
            st.subheader("📝 生成された要約（プレビュー）")
            st.markdown(response.text)
            
            st.divider()
            
            # ワンクリックでMarkdownとしてコピー可能な枠を出力
            st.write("👇 以下のコードブロック右上にあるボタンから、Markdownテキストを一発でコピーできます")
            st.code(response.text, language="markdown")

            # 7. クリーンアップ処理
            genai.delete_file(gemini_file.name)
            os.unlink(tmp_path)

        except Exception as e:
            st.error(f"❌ 処理中にエラーが発生しました: {str(e)}")