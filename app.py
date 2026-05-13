import streamlit as st
import pandas as pd
import os

# 1. 페이지 설정
st.set_page_config(page_title="SCM 재고 검색 엔진", layout="wide")
st.title("📦 채널 및 제품별 실시간 재고 조회")

# 2. 데이터 로드 및 전처리
@st.cache_data
def load_data():
    # 📌 원본 파일명을 여기에 정확히 입력해 주세요. (아래는 예시입니다)
    # 깃허브에 올린 파일의 띄어쓰기, 대소문자, 하이픈 위치까지 완벽히 똑같아야 합니다.
    stock_file = "매핑용.xlsx - 재고현황.csv" 
    mapping_file = "매핑용.xlsx - Sheet2.csv"
    
    try:
        # 파일 최상단 빈 줄을 무시하기 위해 header=1 설정
        df_stock = pd.read_csv(stock_file, encoding='utf-8-sig', header=1)
        df_channel = pd.read_csv(mapping_file, encoding='utf-8-sig', header=1)
        
        # 데이터 병합 (상품코드 기준)
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
    
    except FileNotFoundError:
        # 💡 에러 발생 시, 현재 서버(깃허브)에 있는 파일 목록을 화면에 보여줍니다.
        st.error("❌ 코드가 찾는 파일명과 깃허브에 올라간 파일명이 다릅니다.")
        st.warning(f"코드가 찾고 있는 파일: \n1. `{stock_file}`\n2. `{mapping_file}`")
        st.info("📂 현재 깃허브 서버에 인식되어 있는 파일 목록은 아래와 같습니다. 아래 목록에 있는 이름과 코드를 똑같이 맞춰주세요!")
        st.write(os.listdir('.'))
        st.stop()

df = load_data()

# 3. 화면에 보여줄 컬럼 순서
display_cols = ['납품처', '상품바코드', '제품코드', '상품명', '로트번호', '잔여일수', '유효일자', '박스입수', '환산(재고 수)']

# 4. UI 구성 (탭)
tab1, tab2 = st.tabs(["🏢 채널(납품처) 기준 검색", "🔍 제품명/코드 기준 검색"])

# --- 탭 1: 채널별 검색 ---
with tab1:
    st.subheader("납품처별 재고 현황")
    
    # Sheet2의 Customer 컬럼에 콤마(,)로 여러 채널이 적힌 경우를 위해 분리
    raw_channels = df['납품처'].dropna().str.split(',').explode().str.strip().unique()
    channel_list = sorted(list(raw_channels))
    
    selected_channel = st.selectbox(
        "출고할 납품처(채널)를 검색하거나 선택하세요", 
        ["선택하세요"] + channel_list
    )
    
    if selected_channel != "선택하세요":
        # 선택한 채널이 포함된 행 검색
        filtered = df[df['납품처'].str.contains(selected_channel, na=False)]
        st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

# --- 탭 2: 제품명/코드 검색 ---
with tab2:
    st.subheader("제품 상세 검색")
    search_q = st.text_input("찾으시는 제품명 또는 제품코드를 입력하세요 (일부만 입력해도 검색됨)")
    
    if search_q:
        filtered_q = df[
            df['상품명'].str.contains(search_q, case=False, na=False) |
            df['제품코드'].str.contains(search_q, case=False, na=False)
        ]
        
        if not filtered_q.empty:
            st.dataframe(filtered_q[display_cols], use_container_width=True, hide_index=True)
        else:
            st.warning("검색 결과가 없습니다.")
