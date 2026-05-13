import streamlit as st
import pandas as pd
import os

# 1. 페이지 설정
st.set_page_config(page_title="SCM 재고 검색 엔진", layout="wide")
st.title("📦 엑셀 기반 실시간 재고 조회 시스템")

# 2. 데이터 로드 함수
@st.cache_data
def load_data_from_excel():
    stock_file = "Sales_Stock_260513.xlsx" 
    mapping_file = "매핑용.xlsx"
    
    try:
        # 재고현황: 스니펫을 보면 두 번째 줄(index 1)에 '상품코드'가 있습니다.
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        
        # Sheet2: 첫 번째 줄이 비어 있으므로 header=1을 주어 '제품코드', 'Customer'를 찾습니다.
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2", header=1)
        
        # 🔍 디버깅용: 만약 또 에러가 나면 컬럼명을 화면에 찍어줍니다.
        # st.write("재고 컬럼:", df_stock.columns.tolist())
        # st.write("매핑 컬럼:", df_channel.columns.tolist())

        # 데이터 병합
        df_merged = pd.merge(
            df_stock, 
            df_channel[['Customer', '제품코드']], 
            left_on="상품코드", 
            right_on="제품코드", 
            how="left"
        )
        
        # 컬럼명 정리
        df_merged.rename(columns={
            'Customer': '납품처',
            '상품코드': '제품코드',
            '화주LOT': '로트번호',
            '입수량(BOX)': '박스입수',
            '합계수량': '환산(재고 수)'
        }, inplace=True)
        
        return df_merged
    
    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")
        # 파일이 읽혔을 때 컬럼이 어떻게 인식되었는지 확인하기 위해 추가
        if 'df_channel' in locals():
            st.info("매핑 파일(Sheet2)에서 인식된 컬럼명들입니다. 코드가 찾는 이름과 똑같은지 확인하세요.")
            st.write(df_channel.columns.tolist())
        st.stop()

df = load_data_from_excel()

# 3. 화면 출력 컬럼 (파일 구조에 맞게 순서 조정)
display_cols = ['납품처', '상품바코드', '제품코드', '상품명', '로트번호', '잔여일수', '유효일자', '박스입수', '환산(재고 수)']

# 이하 검색 UI 로직 동일...
