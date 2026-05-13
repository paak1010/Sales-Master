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

# --- 엑셀 변환 헬퍼 함수 ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='재고조회결과')
    return output.getvalue()

# 2. 데이터 로드 및 전처리 (클렌징 로직 추가)
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

        # --- 2) 데이터 병합 ---
        mapping_sub = df_channel[['Customer', '제품코드']].dropna(subset=['제품코드'])
        df_merged = pd.merge(df_stock, mapping_sub, left_on="상품코드", right_on="제품코드", how="left")
        
        if '제품코드' in df_merged.columns:
            df_merged.drop(columns=['제품코드'], inplace=True)
        
        df_merged.rename(columns={
            'Customer': '납품처',
            '상품코드': '제품코드', 
            '화주LOT': '로트번호',
            '입수량(BOX)': '박스입수',
            '합계수량': '환산(재고 수)'
        }, inplace=True)

        # --- 3) 핵심 필터링 및 클렌징 ---
        # 로트번호 필터링 (NaN 제거 및 '폐기' 제외)
        df_merged = df_merged.dropna(subset=['로트번호'])
        df_merged = df_merged[~df_merged['로트번호'].astype(str).str.contains('폐기', na=False)]
        
        # ✨ 상품바코드 클렌징 (추가된 부분)
        if '상품바코드' in df_merged.columns:
            # 결측치는 빈 문자열로 처리하고, 모두 문자형으로 변환
            df_merged['상품바코드'] = df_merged['상품바코드'].fillna('').astype(str)
            # 숫자로 인식되어 .0이 붙는 경우 제거
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'\.0$', '', regex=True)
            # 끝에 붙은 '?' 기호들을 모두 제거
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'\?+$', '', regex=True)

        # 유효일자 형식 정리
        if '유효일자' in df_merged.columns:
            df_merged['유효일자'] = pd.to_datetime(df_merged['유효일자']).dt.strftime('%Y-%m-%d')
            
        return df_merged
    except Exception as e:
        st.error(f"❌ 에러 발생: {e}")
        st.stop()

df = load_filtered_data()

# 3. 화면 구성 및 검색 로직
display_cols = ['납품처', '상품바코드', '제품코드', '상품명', '로트번호', '잔여일수', '유효일자', '박스입수', '환산(재고 수)']

tab1, tab2 = st.tabs(["🏢 채널(납품처) 기준", "🔍 제품명/코드 기준"])

# --- 탭 1: 채널별 검색 ---
with tab1:
    col_input, col_down = st.columns([3, 1])
    with col_input:
        all_customers = df['납품처'].dropna().unique().tolist()
        unique_customers = sorted(list(set([c.strip() for sublist in [str(x).split(',') for x in all_customers] for c in sublist])))
        target = st.selectbox("어디로 나갈 제품을 찾으시나요?", ["업체 선택"] + unique_customers)
    
    if target != "업체 선택":
        result = df[df['납품처'].str.contains(target, na=False)]
        
        with col_down:
            st.write("") 
            st.write("")
            excel_bin = to_excel(result[display_cols])
            st.download_button(
                label="📥 엑셀 다운로드",
                data=excel_bin,
                file_name=f"{target}_재고조회.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        st.metric("가용 재고 건수", f"{len(result)} 건")
        st.dataframe(result[display_cols], use_container_width=True, hide_index=True, height=550)

# --- 탭 2: 제품별 검색 ---
with tab2:
    col_search, col_down2 = st.columns([3, 1])
    with col_search:
        search_input = st.text_input("제품명 또는 코드를 입력하세요 (예: 아크네스, ME...)")
        
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
                st.download_button(
                    label="📥 결과 다운로드",
                    data=excel_bin_q,
                    file_name="검색결과_재고현황.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            st.metric("검색 결과", f"{len(result_q)} 건")
            st.dataframe(result_q[display_cols], use_container_width=True, hide_index=True, height=550)
        else:
            st.warning("가용한 제품 정보가 없습니다. (로트번호가 없거나 폐기된 제품일 수 있습니다)")
