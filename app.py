import streamlit as st
import pandas as pd
import os

# 1. 페이지 설정 (가로로 넓게, 타이틀 깔끔하게)
st.set_page_config(page_title="멘소래담 재고 검색 엔진", layout="wide")

# CSS로 표 스타일 살짝 조정 (한눈에 더 잘 들어오게)
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 채널 및 제품별 실시간 재고 조회")

# 2. 데이터 로드 및 자동 전처리 함수
@st.cache_data
def load_data_safe():
    stock_file = "Sales_Stock_260513.xlsx"
    mapping_file = "매핑용.xlsx"
    
    try:
        # --- 1) 재고 데이터 로드 ---
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        df_stock.columns = df_stock.columns.astype(str).str.strip() # 컬럼명 공백 제거
        
        # --- 2) 매핑 데이터 로드 (에러 방지 로직) ---
        # 일단 읽어보고 '제품코드'가 컬럼에 없으면 헤더 위치를 조정하며 재시도
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2")
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        
        if '제품코드' not in df_channel.columns:
            df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2", header=1)
            df_channel.columns = df_channel.columns.astype(str).str.strip()

        # --- 3) 데이터 병합 ---
        # 매핑 파일에서 필요한 것만 따오기
        mapping_sub = df_channel[['Customer', '제품코드']].dropna(subset=['제품코드'])
        
        df_merged = pd.merge(
            df_stock, 
            mapping_sub, 
            left_on="상품코드", 
            right_on="제품코드", 
            how="left"
        )
        
        # 컬럼명 정리
        df_merged.rename(columns={
            'Customer': '납품처',
            '상품코드': '제품코드_원본', # 중복 방지
            '화주LOT': '로트번호',
            '입수량(BOX)': '박스입수',
            '합계수량': '환산(재고 수)'
        }, inplace=True)
        
        # 유효일자 형식 정리 (YYYY-MM-DD)
        if '유효일자' in df_merged.columns:
            df_merged['유효일자'] = pd.to_datetime(df_merged['유효일자']).dt.strftime('%Y-%m-%d')
            
        return df_merged
    
    except Exception as e:
        st.error(f"❌ 데이터 처리 중 오류 발생: {e}")
        # 어떤 컬럼들이 인식되었는지 보여줘서 수정하기 편하게 함
        if 'df_channel' in locals():
            st.info("현재 매핑 파일에서 인식된 제목들:")
            st.write(list(df_channel.columns))
        st.stop()

df = load_data_safe()

# 3. 화면 구성 및 검색 로직
display_cols = ['납품처', '상품바코드', '상품코드', '상품명', '로트번호', '잔여일수', '유효일자', '박스입수', '환산(재고 수)']

tab1, tab2 = st.tabs(["🏢 채널(납품처) 기준", "🔍 제품명/코드 기준"])

# --- 탭 1: 채널별 검색 ---
with tab1:
    col_input, col_info = st.columns([1, 2])
    with col_input:
        # 검색창에 자동완성 기능 (st.selectbox)
        all_customers = df['납품처'].dropna().unique().tolist()
        # 여러 업체가 섞여 있는 경우 분리해서 유니크하게 추출
        unique_customers = sorted(list(set([c.strip() for sublist in [str(x).split(',') for x in all_customers] for c in sublist])))
        
        target = st.selectbox("어디로 나갈 제품을 찾으시나요?", ["업체 선택"] + unique_customers)
    
    if target != "업체 선택":
        result = df[df['납품처'].str.contains(target, na=False)]
        
        # 한눈에 들어오게 요약 정보 제공
        st.metric("검색 결과", f"{len(result)} 건")
        st.dataframe(result[display_cols], use_container_width=True, hide_index=True, height=500)

# --- 탭 2: 제품별 상세 검색 ---
with tab2:
    search_input = st.text_input("제품명이나 코드를 입력하고 엔터를 눌러주세요 (예: 아크네스, ME...)")
    
    if search_input:
        result_q = df[
            df['상품명'].str.contains(search_input, case=False, na=False) |
            df['상품코드'].str.contains(search_input, case=False, na=False)
        ]
        
        if not result_q.empty:
            st.metric("찾은 제품", f"{len(result_q)} 건")
            st.dataframe(result_q[display_cols], use_container_width=True, hide_index=True, height=500)
        else:
            st.warning("일치하는 제품 정보가 없습니다.")
