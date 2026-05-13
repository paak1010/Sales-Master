import streamlit as st
import pandas as pd
from io import BytesIO

# 1. 페이지 설정
st.set_page_config(page_title="멘소래담 재고 검색 엔진", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    .stDownloadButton > button { width: 100%; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 가용 재고 실시간 조회 시스템")

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='재고조회결과')
    return output.getvalue()

@st.cache_data
def load_filtered_data():
    stock_file = "Sales_Stock_260513.xlsx"
    mapping_file = "매핑용.xlsx"
    
    try:
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2")
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        
        if '제품코드' not in df_channel.columns:
            df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2", header=1)
            df_channel.columns = df_channel.columns.astype(str).str.strip()

        mapping_sub = df_channel[['Customer', '제품코드', 'Remarks']].dropna(subset=['제품코드'])
        df_merged = pd.merge(df_stock, mapping_sub, left_on="상품코드", right_on="제품코드", how="left")
        
        if '제품코드' in df_merged.columns:
            df_merged.drop(columns=['제품코드'], inplace=True)
        
        df_merged.rename(columns={
            'Customer': '납품처',
            '상품코드': '제품코드', 
            '화주LOT': '로트번호',
            '입수량(BOX)': '박스입수',
            '합계수량': '환산(재고 수)',
            'Remarks': '특이사항'
        }, inplace=True)

        df_merged['로트번호'] = df_merged['로트번호'].fillna('').astype(str).str.strip()
        df_merged = df_merged[df_merged['로트번호'] != '']
        df_merged = df_merged[df_merged['로트번호'].str.lower() != 'nan']
        df_merged = df_merged[~df_merged['로트번호'].str.contains('폐기', na=False)]
        
        if '상품바코드' in df_merged.columns:
            df_merged['상품바코드'] = df_merged['상품바코드'].fillna('').astype(str)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'\.0$', '', regex=True)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'[?？]', '', regex=True)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.strip()

        if '유효일자' in df_merged.columns:
            df_merged['유효일자'] = pd.to_datetime(df_merged['유효일자'], errors='coerce').dt.strftime('%Y-%m-%d')
            
        return df_merged
    except Exception as e:
        st.error(f"❌ 데이터 로드 중 오류 발생: {e}")
        st.stop()

df_raw = load_filtered_data()

# --- 검색 설정: 단독 납품(전용) 필터 토글 ---
st.markdown("---")
col_setting, col_blank = st.columns([1, 2])
with col_setting:
    st.markdown("### ⚙️ 검색 설정")
    is_exclusive = st.toggle("🌟 단독 납품(전용) 제품만 보기")

if is_exclusive:
    df = df_raw[~df_raw['납품처'].astype(str).str.contains(',', na=False)]
    st.info("💡 단일 채널 전용 제품만 표시 중입니다.")
else:
    df = df_raw.copy()
st.markdown("---")

display_cols = ['납품처', '제품코드', '상품명', '로트번호', '유효일자', '잔여일수', '환산(재고 수)', '특이사항', '상품바코드']

# ✨ 대시보드 시각화 설정 (st.column_config) ✨
# 숫자로만 보이던 답답한 데이터들에 디자인 요소를 입힙니다.
dashboard_config = {
    "잔여일수": st.column_config.ProgressColumn(
        "잔여일수 (위험도)",
        help="유효일자까지 남은 일수입니다.",
        format="%d 일",
        min_value=0,
        max_value=1095, # 최대 3년 기준으로 게이지 바 표시
    ),
    "환산(재고 수)": st.column_config.NumberColumn(
        "가용 재고",
        help="현재 출고 가능한 재고 수량",
        format="%d 개"
    ),
    "유효일자": st.column_config.DateColumn(
        "유효일자 📅",
        format="YYYY-MM-DD"
    ),
    "상품바코드": st.column_config.TextColumn(
        "바코드 🏷️"
    ),
    "특이사항": st.column_config.TextColumn(
        "특이사항 📝"
    )
}

tab1, tab2 = st.tabs(["🏢 채널(납품처) 기준", "🔍 제품명/코드 기준"])

# --- 탭 1: 채널별 검색 ---
with tab1:
    col_input, col_down = st.columns([3, 1])
    with col_input:
        all_customers = df['납품처'].dropna().unique().tolist()
        unique_customers = sorted(list(set([c.strip() for sublist in [str(x).split(',') for x in all_customers] for c in sublist])))
        target = st.selectbox("업체를 선택하세요", ["업체 선택"] + unique_customers)
    
    if target != "업체 선택":
        result = df[df['납품처'].str.contains(target, na=False)]
        
        with col_down:
            st.write("") 
            st.write("")
            excel_bin = to_excel(result[display_cols])
            st.download_button(label="📥 엑셀 다운로드", data=excel_bin, file_name=f"{target}_재고.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
        st.metric("가용 재고 건수", f"{len(result)} 건")
        
        # 🚨 column_config를 적용하여 예쁘게 출력
        st.dataframe(
            result[display_cols], 
            use_container_width=True, 
            hide_index=True, 
            height=550,
            column_config=dashboard_config
        )

# --- 탭 2: 제품별 검색 ---
with tab2:
    col_search, col_down2 = st.columns([3, 1])
    with col_search:
        search_input = st.text_input("제품명 또는 코드를 입력하세요")
        
    if search_input:
        result_q = df[
            df['상품명'].str.contains(search_input, case=False, na=False) |
            df['제품코드'].str.contains(search_input, case=False, na=False)
        ]
        
        if not result_q.empty:
            with col_down2:
                st.write("") 
                st.write("")
                excel_bin_q = to_excel(result_q[display_cols])
                st.download_button(label="📥 엑셀 다운로드", data=excel_bin_q, file_name="검색결과.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
            st.metric("검색 결과", f"{len(result_q)} 건")
            
            # 🚨 column_config를 적용하여 예쁘게 출력
            st.dataframe(
                result_q[display_cols], 
                use_container_width=True, 
                hide_index=True, 
                height=550,
                column_config=dashboard_config
            )
        else:
            st.warning("가용한 제품 정보가 없습니다.")
