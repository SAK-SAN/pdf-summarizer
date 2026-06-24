import streamlit as st
import google.generativeai as genai
import os
import tempfile
import time
import requests
import json
import re
from dotenv import load_dotenv

# 1. 環境変数の読み込みとAPIキーの取得
load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")

# APIから利用可能なGeminiモデルを動的に取得する関数
def get_gemini_models(api_key):
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        res = requests.get(list_url)
        if res.status_code == 200:
            data = res.json()
            models = [
                m["name"] for m in data.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            return models
        else:
            return []
    except Exception:
        return []

# 【新規】 取得したモデル一覧から「最も高性能なモデル」のインデックスを自動で割り出す関数
def find_best_model_index(models):
    best_index = 0
    max_score = -1.0
    
    for i, model in enumerate(models):
        score = 0.0
        
        # 1. バージョン数値の抽出 (例: gemini-2.5 なら 2.5、gemini-1.5 なら 1.5)
        version_match = re.search(r'gemini-(\d+\.?\d*)', model)
        if version_match:
            # バージョンが高いほどスコアを大きく加算 (例: 2.5 -> +25.0点)
            score += float(version_match.group(1)) * 10
            
        # 2. 性能ティア(pro か flash か)の判定
        if "pro" in model:
            score += 5.0   # 思考力・解析力が高い pro を最優先
        elif "flash" in model:
            score += 1.0   # 高速軽量な flash はベース点
            
        # 3. プレビュー版や実験用モデル(exp)は安定性を考慮して微減
        if "exp" in model:
            score -= 0.5

        # 最高得点を更新したらインデックスを記憶
        if score > max_score:
            max_score = score
            best_index = i
            
    return best_index

# 2. ページの基本設定
st.set_page_config(page_title="論文解析 & Notionコピペツール", layout="centered", page_icon="🎓")
st.title("🎓 論文解析 & Notionコピペツール")
st.write("論文PDFを解析し、Notionへそのまま貼り付けられる構造化された解説を生成します。")

if not api_key:
    st.error("🔑 APIキーが設定されていません。")
    st.stop()

genai.configure(api_key=api_key)

# st.session_state（セッション状態）の初期化
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None  # 解析完了後のJSONデータを保存
if "is_analyzing" not in st.session_state:
    st.session_state.is_analyzing = False    # 解析中フラグ

# 3. サイドバーによるモデル切り替え
st.sidebar.title("🛠 アプリ設定")
with st.sidebar:
    with st.spinner("利用可能なGeminiモデルを確認中..."):
        available_models = get_gemini_models(api_key)
    
    if available_models:
        # 【変更】動的アルゴリズムによって最強モデルの初期位置を自動計算
        default_index = find_best_model_index(available_models)
        
        model_choice = st.selectbox(
            "使用するAIモデルを選択",
            options=available_models,
            index=default_index,
            help="APIから取得したモデルの中で、最も高性能なモデル（最新のpro等）が自動的に初期選択されています。"
        )
    else:
        st.warning("モデル一覧の取得に失敗しました。")
        model_choice = "models/gemini-1.5-flash"

# 4. ユーザー入力エリア
uploaded_file = st.file_uploader("論文のPDFファイルを選択してください", type=["pdf"])

# 5. メイン処理ロジック（ボタンが押されたとき）
if st.button("論文を解析して構造化する", type="primary", disabled=st.session_state.is_analyzing or not uploaded_file):
    st.session_state.is_analyzing = True
    st.session_state.analysis_result = None  # 前回の結果をクリア
    
    with st.spinner("専門リサーチャーが論文を深く読み解いています。これ以上画面を動かさずにお待ちください..."):
        try:
            # 一時ファイルへの書き出し
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            # GeminiのFile APIを利用してPDFを直接アップロード
            gemini_file = genai.upload_file(path=tmp_path, mime_type="application/pdf")
            
            while gemini_file.state.name == "PROCESSING":
                time.sleep(2)
                gemini_file = genai.get_file(gemini_file.name)

            if gemini_file.state.name == "FAILED":
                raise ValueError("Gemini API上でのPDF解析に失敗しました。")

            # メタプロンプトの組み立て
            analysis_prompt = """
            # Role
            あなたは、最先端の学術論文を誰にでもわかる言葉で解説する「専門リサーチャー兼テクニカルライター」です。複雑な概念を噛み砕き、論理的かつ構造的に整理するスキルに長けています。

            # Context
            提供された論文の内容を、Notionに直接貼り付けて管理・活用できるように整理する必要があります。専門知識がない読者でも内容を理解できるよう、平易な表現を用いつつ、情報の正確性を担保して出力してください。

            # Task
            提供された論文PDFに基づき、指定された8つの項目について詳細な解説を作成してください。
            内容は、専門外の初心者でも理解できるように、技術用語には簡潔な補足説明を付け加えてください。結論や考察は客観的に記述してください。

            # Output Format
            必ず、以下のキーを完全に持った単一のJSONオブジェクトとして出力してください。
            余計な前置きやマークダウンのマークアップ（```json などの囲み）は含めず、純粋なJSON形式の文字列のみを返してください。

            {
              "research_purpose": "研究目的の詳細な解説（平易な表現・補足付き）",
              "proposed_content": "提案内容の詳細な解説",
              "evaluation_method": "評価方法の詳細な解説",
              "research_results": "研究成果の詳細な解説",
              "strengths": "長所の詳細な解説",
              "weaknesses": "短所の詳細な解説",
              "technical_challenges": "技術的課題の詳細な解説",
              "summary": "全体の要約"
            }
            """

            # モデルの呼び出し（JSON出力を明示的に指定）
            model = genai.GenerativeModel(model_name=model_choice)
            response = model.generate_content(
                [gemini_file, analysis_prompt],
                generation_config={"response_mime_type": "application/json"}
            )

            # AIレスポンスから純粋なJSON部分を抽出してパース
            response_text = response.text.strip()
            response_text = re.sub(r'^```json\s*|```$', '', response_text, flags=re.MULTILINE).strip()
            
            # 成功したらデータをセッション状態に格納
            st.session_state.analysis_result = json.loads(response_text)

            # クリーンアップ処理
            genai.delete_file(gemini_file.name)
            os.unlink(tmp_path)

        except json.JSONDecodeError:
            st.error("❌ AIからのデータ構造（JSON）のパースに失敗しました。もう一度お試しください。")
        except Exception as e:
            st.error(f"❌ 処理中にエラーが発生しました: {str(e)}")
        finally:
            st.session_state.is_analyzing = False
            st.rerun()  # 状態を確定させて画面をリフレッシュ

# 6. 完全にデータが読み込み終わったタイミングでUIを表示
if st.session_state.analysis_result is not None:
    st.success("🎉 論文の解析が完了しました！")

    # 表記用の項目マッピング辞書
    items_mapping = {
        "research_purpose": "1. 研究目的",
        "proposed_content": "2. 提案内容",
        "evaluation_method": "3. 評価方法",
        "research_results": "4. 研究成果",
        "strengths": "5. 長所",
        "weaknesses": "6. 短所",
        "technical_challenges": "7. 技術的課題",
        "summary": "8. 要約"
    }

    # タブ切り替え
    tab1, tab2 = st.tabs(["📋 各項目ごとに個別にコピペ", "🚀 Notion用一括コピペ"])

    # ---- タブ1: 個別コピペUI ----
    with tab1:
        st.write("💡 各項目の右上にあるボタンから、その内容だけを個別にコピーできます。")
        for key, display_name in items_mapping.items():
            content = st.session_state.analysis_result.get(key, "（データが生成されませんでした）")
            st.subheader(display_name)
            st.code(content, language="text")

    # ---- タブ2: 一括コピペUI ----
    with tab2:
        st.write("💡 以下の枠の右上ボタンを押すと、すべての項目がNotion用フォーマットで一括コピーされます。")
        
        formatted_bulk_text = ""
        for key, display_name in items_mapping.items():
            content = st.session_state.analysis_result.get(key, "")
            # 見出し（#）とコードブロック（```）の構造を連結
            formatted_bulk_text += f"# {display_name}\n```\n{content}\n```\n\n"
        
        st.code(formatted_bulk_text.strip(), language="markdown")