import streamlit as st
import pandas as pd

# 1. 페이지 기본 설정
st.set_page_config(page_title="채널별 재고 검색 엔진", layout="wide")
st.title("📦 채널 및 제품별 재고 검색 엔진")

# 2. 깃허브에 업로드된 데이터 로드 (캐싱하여 속도 향상)
@st.cache_data
def load_data():
    # 깃허브 레포지토리에 있는 파일명과 정확히 일치해야 합니다.
    try:
        df_stock = pd.read_csv("Sales_Stock_260513.xlsx - 재고현황.csv")
        df_channel = pd.read_csv("Sales_Stock_260513.xlsx - 담당자 및 채널.csv")
    except FileNotFoundError:
        st.error("데이터 파일을 찾을 수 없습니다. 깃허브 레포지토리에 파일이 정상적으로 올라갔는지 확인해주세요.")
        st.stop()
    
    # 데이터 병합 (Left Join)
    df_merged = pd.merge(
        df_stock, 
        df_channel[['Customer', '제품코드']], 
        left_on="상품코드", 
        right_on="제품코드", 
        how="left"
    )
    
    # 납품처 컬럼명 변경
    df_merged.rename(columns={'Customer': '납품처'}, inplace=True)
    return df_merged

df_merged = load_data()

# 최종 화면에 보여줄 컬럼 지정 및 이름 변경 매핑
display_columns = ['납품처', '상품바코드', '상품코드', '상품명', '화주LOT', '잔여일수', '유효일자', '입수량(BOX)', '합계수량']
rename_dict = {
    '상품코드': '제품코드',
    '화주LOT': '로트번호',
    '입수량(BOX)': '박스입수',
    '합계수량': '환산(재고 수)'
}

# 3. 화면 구성: 두 개의 탭으로 나누어 UI 분리
tab1, tab2 = st.tabs(["🏢 납품처(채널) 기준 검색", "🔍 제품 기준 검색"])

# --- 탭 1: 납품처(올리브영 등) 기준 검색 ---
with tab1:
    st.subheader("납품처별 재고 조회")
    
    # 납품처 목록 추출
    customer_list = df_merged['납품처'].dropna().unique().tolist()
    
    # 자동완성 지원 셀렉트박스
    selected_customer = st.selectbox(
        "납품처를 검색하거나 선택하세요 (예: 올리브영, 쿠팡로켓)", 
        ["선택하세요"] + customer_list
    )
    
    if selected_customer != "선택하세요":
        filtered_df = df_merged[df_merged['납품처'] == selected_customer]
        show_df = filtered_df[display_columns].rename(columns=rename_dict)
        st.dataframe(show_df, use_container_width=True, hide_index=True)

# --- 탭 2: 제품코드 또는 상품명 기준 검색 ---
with tab2:
    st.subheader("제품명/제품코드 기준 검색")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        search_type = st.radio("검색 기준", ["상품명", "제품코드"])
    with col2:
        search_keyword = st.text_input(f"검색할 {search_type}을(를) 입력하세요 (일부만 입력해도 검색됨)")
    
    if search_keyword:
        if search_type == "상품명":
            filtered_df2 = df_merged[df_merged['상품명'].str.contains(search_keyword, case=False, na=False)]
        else:
            filtered_df2 = df_merged[df_merged['상품코드'].str.contains(search_keyword, case=False, na=False)]
            
        if not filtered_df2.empty:
            show_df2 = filtered_df2[display_columns].rename(columns=rename_dict)
            st.dataframe(show_df2, use_container_width=True, hide_index=True)
        else:
            st.warning("검색 결과가 없습니다. 입력하신 내용을 다시 확인해주세요.")
