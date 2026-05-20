import streamlit as st
from pypdf import PdfReader, PdfWriter
import io
import zipfile

# --- ページ設定とデザインの強制上書き ---
st.set_page_config(page_title="PDF Booklet Creator", layout="centered", page_icon="📙")

# ボタンの文字色を「黒」で太字にするためのカスタムCSS
st.markdown("""
<style>
div.stButton > button[kind="primary"] {
    color: black !important;
    font-weight: bold !important;
    font-size: 1.2rem !important;
}
</style>
""", unsafe_allow_html=True)

# --- ページ順序を計算するアルゴリズム ---
def build_virtual_array(reader, excluded_pages, blank_mode, up_mode):
    valid_indices = [i for i in range(len(reader.pages)) if (i + 1) not in excluded_pages]
    v_list = []
    if blank_mode == "front1":
        v_list.append("BLANK")
    elif blank_mode == "front2":
        v_list.extend(["BLANK", "BLANK"])
        
    v_list.extend(valid_indices)
    
    L = len(v_list)
    if up_mode == "2up":
        T = L + (4 - L % 4) % 4
    else:
        T = L + (8 - L % 8) % 8
        
    while len(v_list) < T:
        v_list.append("BLANK")
        
    return v_list

def get_2up_indices(total_pages):
    indices = []
    for k in range(1, (total_pages // 4) + 1):
        indices.extend([total_pages - 2*(k-1) - 1, 2*k - 2, 2*k - 1, total_pages - 2*(k-1) - 2])
    return indices

def get_4up_indices(total_pages):
    indices = []
    for k in range(1, (total_pages // 8) + 1):
        indices.extend([
            total_pages - 4*(k-1) - 2, total_pages - 4*(k-1) - 1, 
            4*(k-1), 4*(k-1) + 1, 4*(k-1) + 2, 4*(k-1) + 3, 
            total_pages - 4*(k-1) - 4, total_pages - 4*(k-1) - 3
        ])
    return indices

def create_sorted_pdf_writer(reader, virtual_list, booklet_indices):
    writer = PdfWriter()
    width = reader.pages[0].mediabox.width if len(reader.pages) > 0 else 595
    height = reader.pages[0].mediabox.height if len(reader.pages) > 0 else 842
    
    for idx in booklet_indices:
        v_page = virtual_list[idx]
        if v_page == "BLANK":
            writer.add_blank_page(width=width, height=height)
        else:
            writer.add_page(reader.pages[v_page])
            
    return writer

# --- UIとWebアプリの動作 ---
st.title("📙 PDF小冊子印刷ツール")
st.write("iPadから複数ファイルを一括で面付け処理します。")

# 1. ファイルのアップロード (複数対応)
uploaded_files = st.file_uploader("① PDFファイルを選択 (複数可)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    st.info(f"選択中: {len(uploaded_files)} 個のファイル")

    # 2. 除きたいページ
    exclude_str = st.text_input("② 除きたいページ (カンマ区切り):", placeholder="例: 3,8,12 (除外しない場合は空欄)")
    
    # 3. 白紙の追加位置
    blank_options = {
        "end": "末尾のみ (標準)",
        "front1": "先頭に1枚 ＋ 末尾",
        "front2": "先頭に2枚 ＋ 末尾"
    }
    blank_mode = st.radio("③ 白紙の追加位置:", list(blank_options.keys()), format_func=lambda x: blank_options[x])

    # 4. 出力モード
    mode_options = {
        "2up": "2枚用 (小冊子)",
        "4up": "4枚用 (小冊子)",
        "both": "2枚用と4枚用の両方作成"
    }
    up_mode = st.radio("④ 出力モード:", list(mode_options.keys()), format_func=lambda x: mode_options[x])

    # 5. 実行ボタン (type="primary" にすることでテーマのアクセントカラーが適用されます)
    if st.button("⑤ 並び替えて作成", type="primary"):
        excluded_pages = []
        if exclude_str:
            try:
                excluded_pages = [int(p.strip()) for p in exclude_str.split(",") if p.strip()]
            except ValueError:
                st.error("エラー: 除きたいページは半角数字とカンマのみで入力してください。")
                st.stop()

        generated_files = {}
        error_messages = []

        for uploaded_file in uploaded_files:
            try:
                reader = PdfReader(uploaded_file)
                original_total = len(reader.pages)
                base_name = uploaded_file.name

                invalid_excludes = [p for p in excluded_pages if p < 1 or p > original_total]
                if invalid_excludes:
                    error_messages.append(f"スキップ: {base_name} (存在しないページ {invalid_excludes} を除外しようとしました)")
                    continue
                if len(excluded_pages) >= original_total:
                    error_messages.append(f"スキップ: {base_name} (全ページが除外されます)")
                    continue

                if up_mode == "both":
                    v2 = build_virtual_array(reader, excluded_pages, blank_mode, "2up")
                    writer2 = create_sorted_pdf_writer(reader, v2, get_2up_indices(len(v2)))
                    out2 = io.BytesIO()
                    writer2.write(out2)
                    generated_files[f"《２枚用》{base_name}"] = out2.getvalue()
                    
                    v4 = build_virtual_array(reader, excluded_pages, blank_mode, "4up")
                    writer4 = create_sorted_pdf_writer(reader, v4, get_4up_indices(len(v4)))
                    out4 = io.BytesIO()
                    writer4.write(out4)
                    generated_files[f"《４枚用》{base_name}"] = out4.getvalue()
                else:
                    prefix = "《２枚用》" if up_mode == "2up" else "《４枚用》"
                    v = build_virtual_array(reader, excluded_pages, blank_mode, up_mode)
                    indices = get_2up_indices(len(v)) if up_mode == "2up" else get_4up_indices(len(v))
                    writer = create_sorted_pdf_writer(reader, v, indices)
                    out = io.BytesIO()
                    writer.write(out)
                    generated_files[f"{prefix}{base_name}"] = out.getvalue()
                    
            except Exception as e:
                error_messages.append(f"エラー: {uploaded_file.name} ({e})")

        if error_messages:
            for err in error_messages:
                st.warning(err)

        num_generated = len(generated_files)
        if num_generated == 1:
            filename, file_data = list(generated_files.items())[0]
            st.success("✅ 完了しました！以下のボタンからダウンロードしてください。")
            st.download_button(
                label=f"📥 {filename} をダウンロード",
                data=file_data,
                file_name=filename,
                mime="application/pdf",
                type="primary" # ダウンロードボタンもオレンジ×黒になります
            )
        elif num_generated > 1:
            st.success(f"✅ {num_generated} 個のファイルを作成しました！ZIPにまとめています。")
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for filename, file_data in generated_files.items():
                    zip_file.writestr(filename, file_data)
            
            st.download_button(
                label="📦 全ファイルをZIPでダウンロード",
                data=zip_buffer.getvalue(),
                file_name="Booklet_Data.zip",
                mime="application/zip",
                type="primary"
            )