import streamlit as st
import pandas as pd
import os

# 1. 페이지 설정
st.set_page_config(page_title="SCM 재고 검색 엔진", layout="wide")
st.title("📦 엑셀 기반 실시간 재고 조회 시스템")

# 2. 데이터 로드 함수 (엑셀 직접 읽기)
@st.cache_data
def load_data_from_excel():
    # 사용자가 정한 원본 파일명 그대로 사용
    stock_file = "Sales_Stock_260513.xlsx" 
    mapping_file = "매핑용.xlsx"
    
    try:
        # 엑셀 파일 읽기 (pd.read_excel 사용)
        # sheet_name을 통해 필요한 시트만 정확히 가져옵니다.
        # 데이터 시작 위치에 따라 header 값을 조절하세요 (0이 첫 줄)
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2")
        
        # 데이터 병합 (상품코드 기준)
        df_merged = pd.merge(
            df_stock, 
            df_channel[['Customer', '제품코드']], 
            left_on="상품코드", 
            right_on="제품코드", 
            how="left"
        )
        
        # 컬럼명 정리 및 시각화용 이름 변경
        df_merged.rename(columns={
            'Customer': '납품처',
            '상품코드': '제품코드',
            '화주LOT': '로트번호',
            '입수량(BOX)': '박스입수',
            '합계수량': '환산(재고 수)'
        }, inplace=True)
        
        return df_merged
    
    except Exception as e:
        st.error(f"❌ 엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")
        st.info("깃허브에 업로드된 파일명과 코드 내 파일명이 일치하는지, 시트 이름이 맞는지 확인해주세요.")
        # 파일 목록 확인용 디버깅 도구
        st.write("현재 경로 내 파일 목록:", os.listdir('.'))
        st.stop()

df = load_data_from_excel()

# 3. 화면에 출력할 핵심 컬럼
display_cols = ['납품처', '상품바코드', '제품코드', '상품명', '로트번호', '잔여일수', '유효일자', '박스입수', '환산(재고 수)']

# 4. 검색 UI 구성
tab1, tab2 = st.tabs(["🏢 채널별 검색", "🔍 제품별 검색"])

with tab1:
    st.subheader("납품처별 재고")
    raw_channels = df['납품처'].dropna().str.split(',').explode().str.strip().unique()
    channel_list = sorted(list(raw_channels))
    
    selected_channel = st.selectbox("조회할 납품처를 선택하세요", ["선택하세요"] + channel_list)
    
    if selected_channel != "선택하세요":
        filtered = df[df['납품처'].str.contains(selected_channel, na=False)]
        st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

with tab2:
    st.subheader("제품 상세 검색")
    search_q = st.text_input("제품명 또는 제품코드를 입력하세요")
    
    if search_q:
        filtered_q = df[
            df['상품명'].str.contains(search_q, case=False, na=False) |
            df['제품코드'].str.contains(search_q, case=False, na=False)
        ]
        
        if not filtered_q.empty:
            st.dataframe(filtered_q[display_cols], use_container_width=True, hide_index=True)
        else:
            st.warning("검색 결과가 없습니다.")
