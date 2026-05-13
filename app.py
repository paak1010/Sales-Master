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

# 2. 데이터 로드 및 정밀 전처리
@st.cache_data
def load_filtered_data():
    stock_file = "Sales_Stock_260513.xlsx"
    mapping_file = "매핑용.xlsx"
    
    try:
        # --- 1) 데이터 로드 ---
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2")
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        
        if '제품코드' not in df_channel.columns:
            df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2", header=1)
            df_channel.columns = df_channel.columns.astype(str).str.strip()

        # --- 2) ✨ 매핑 키(Key) 정규화 (누락 방지 핵심) ---
        # 양쪽 파일의 코드를 대문자 변환 + 공백 제거하여 매칭 확률 100%로 상향
        df_stock['상품코드_key'] = df_stock['상품코드'].astype(str).str.strip().str.upper()
        df_channel['제품코드_key'] = df_channel['제품코드'].astype(str).str.strip().str.upper()

        # --- 3) 데이터 병합 ---
        mapping_sub = df_channel[['Customer', '제품코드_key', 'Remarks']].dropna(subset=['제품코드_key'])
        
        # 중복 매핑 방지를 위해 제품코드_key 기준 중복 제거
        mapping_sub = mapping_sub.drop_duplicates('제품코드_key')
        
        df_merged = pd.merge(
            df_stock, 
            mapping_sub, 
            left_on="상품코드_key", 
            right_on="제품코드_key", 
            how="left"
        )
        
        # 불필요한 임시 키 컬럼 삭제
        df_merged.drop(columns=['상품코드_key', '제품코드_key'], inplace=True)
        
        df_merged.rename(columns={
            'Customer': '납품처',
            '상품코드': '제품코드', 
            '화주LOT': '로트번호',
            '입수량(BOX)': '박스입수',
            '합계수량': '환산(재고 수)',
            'Remarks': '특이사항'
        }, inplace=True)

        # --- 4) 필터링 및 클렌징 ---
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
        st.error(f"❌ 데이터 처리 중 오류: {e}")
        st.stop()

df_raw = load_filtered_data()

# --- 검색 설정: 단독 납품(전용) 필터 토글 ---
st.markdown("---")
col_setting, col_blank = st.columns([1, 2])
with col_setting:
    st.markdown("### ⚙️ 검색 설정")
    is_exclusive = st.toggle("🌟 단독 납품(전용) 제품만 보기")

# 데이터 필터링 (토글 여부에 따라)
if is_exclusive:
    # 콤마가 없는 행만 선택
    df = df_raw[~df_raw['납품처'].astype(str).str.contains(',', na=False)]
else:
    df = df_raw.copy()
st.markdown("---")

# 시각화 설정
display_cols = ['납품처', '제품코드', '상품명', '로트번호', '유효일자', '잔여일수', '환산(재고 수)', '특이사항', '상품바코드']
dashboard_config = {
    "잔여일수": st.column_config.ProgressColumn("잔여일수 (위험도)", format="%d 일", min_value=0, max_value=1095),
    "환산(재고 수)": st.column_config.NumberColumn("가용 재고", format="%d 개"),
    "유효일자": st.column_config.DateColumn("유효일자 📅"),
    "특이사항": st.column_config.TextColumn("특이사항 📝")
}

tab1, tab2 = st.tabs(["🏢 채널(납품처) 기준", "🔍 제품명/코드 기준"])

# --- 탭 1: 채널별 검색 ---
with tab1:
    col_input, col_down = st.columns([3, 1])
    with col_input:
        all_customers = df['납품처'].dropna().unique().tolist()
        # 납품처 리스트 정리 (콤마 분리 및 공백 제거)
        customer_set = set()
        for c in all_customers:
            for part in str(c).split(','):
                customer_set.add(part.strip())
        unique_customers = sorted(list(customer_set))
        
        target = st.selectbox("업체를 선택하세요", ["업체 선택"] + unique_customers)
    
    if target != "업체 선택":
        # ✨ 핵심 수정: regex=False를 추가하여 (TrD) 같은 괄호를 문자 그대로 검색
        result = df[df['납품처'].str.contains(target, na=False, regex=False)]
        
        with col_down:
            st.write("") 
            st.write("")
            excel_bin = to_excel(result[display_cols])
            st.download_button(label="📥 엑셀 다운로드", data=excel_bin, file_name=f"{target}_재고.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
        st.metric("가용 재고 건수", f"{len(result)} 건")
        st.dataframe(result[display_cols], use_container_width=True, hide_index=True, height=550, column_config=dashboard_config)

# --- 탭 2: 제품별 검색 ---
with tab2:
    search_input = st.text_input("제품명 또는 코드를 입력하세요")
    if search_input:
        # 제품 검색도 안전하게 대소문자 구분 없이 검색
        result_q = df[
            df['상품명'].str.contains(search_input, case=False, na=False, regex=False) |
            df['제품코드'].str.contains(search_input, case=False, na=False, regex=False)
        ]
        if not result_q.empty:
            excel_bin_q = to_excel(result_q[display_cols])
            st.download_button(label="📥 엑셀 다운로드", data=excel_bin_q, file_name="검색결과.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.metric("검색 결과", f"{len(result_q)} 건")
            st.dataframe(result_q[display_cols], use_container_width=True, hide_index=True, height=550, column_config=dashboard_config)
        else:
            st.warning("가용한 제품 정보가 없습니다. 검색어나 필터 설정을 확인해주세요.")
